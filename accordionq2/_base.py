"""HTTP transport layer for AccordionQ2 API groups (stdlib only).

Uses a persistent ``http.client`` connection so that DNS is resolved only
once per connection lifetime.  This avoids the ~625 ms mDNS (.local)
lookup penalty that ``urllib.request.urlopen`` incurs on every call under
Windows.

Security (accordionq2 7.0): the station API key goes as ``X-Api-Key`` on every
request, and an HTTPS certificate can be pinned by its SHA-256 fingerprint. This
library never logs the key or puts it in an exception message or a repr; the
client keeps it as :class:`_Secret`, so a traceback that shows local variables
prints ``'<api key>'`` for the client's own copies. ``http.client``'s frames
still hold the encoded request, key included, and its ``debuglevel`` prints it.
``http.client`` never follows redirects, so the key goes only to the host in the
base URL.
"""

from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import ssl
import threading
import time
import uuid
from urllib.parse import urlparse

from .certificates import normalize_sha256
from .exceptions import (
    AccordionQ2ApiError,
    AccordionQ2CertificateError,
    AccordionQ2SecurityError,
    AccordionQ2SecurityReason,
)

#: The header that carries the station API key.
API_KEY_HEADER = "X-Api-Key"

# Methods that may be sent twice: they don't change anything on the station.
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# The WebApi (Kestrel) closes a keep-alive connection after two minutes idle. Reopening well before
# that means a request is almost never sent on a connection the server has just closed.
IDLE_REOPEN_SECONDS = 60.0

_BASE_URL_FORM = (
    "The base URL must be an absolute http:// or https:// URL, "
    "e.g. http://station:5000 or http://[fe80::1%eth0]:5000"
)


def _parse_base_url(base_url: str) -> tuple[str, str, int, str]:
    """*base_url* as ``(scheme, host, port, path prefix)``.

    An IPv6 literal is written in brackets; its zone id may be ``%eth0`` or
    RFC 6874's ``%25eth0``. As in the .NET client, ``%25`` followed by more is
    always read as RFC 6874's encoded ``%``: ``%2512`` is zone ``12``, and
    ``%25`` alone is zone ``25``. The host keeps its case (a zone name may need it).
    """
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError("The base URL is empty")
    try:
        parsed = urlparse(base_url.strip())
        port = parsed.port
    except ValueError:
        raise ValueError(_BASE_URL_FORM) from None
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(_BASE_URL_FORM)
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("The base URL must not carry credentials; use api_key= instead")
    netloc = parsed.netloc
    if netloc.startswith("["):
        address, percent, zone = netloc[1 : netloc.index("]")].partition("%")
        if zone.startswith("25") and len(zone) > 2:
            zone = zone[2:]  # RFC 6874: "%25" is the "%" itself
        if percent and not zone:
            raise ValueError(_BASE_URL_FORM)
        host = f"{address}{percent}{zone}"
    else:
        host = parsed.hostname
    return (
        parsed.scheme,
        host,
        port or (443 if parsed.scheme == "https" else 80),
        parsed.path.rstrip("/"),
    )


class _Secret(str):
    """A str that ``repr()`` doesn't show: the API key, as the client holds it.

    It is sent like any str. A header dict, or a traceback that shows local
    variables (``pytest -l``, ``capture_locals=True``, error reporters), then
    prints ``'<api key>'`` instead of the key.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return "'<api key>'"


def _secret(api_key: str | None) -> str | None:
    """*api_key* as a :class:`_Secret` when it is a str; anything else unchanged."""
    return _Secret(api_key) if isinstance(api_key, str) else api_key


def _secret_headers(headers: dict[str, str] | None) -> dict[str, str] | None:
    """A copy of *headers* with an ``X-Api-Key`` value as a :class:`_Secret`."""
    if headers is None:
        return None
    return {
        n: (_Secret(v) if n.lower() == "x-api-key" and isinstance(v, str) else v)
        for n, v in headers.items()
    }


def _validate_api_key(api_key: str | None) -> _Secret | None:
    if api_key is None:
        return None
    # The messages never contain the key itself.
    if not isinstance(api_key, str):
        raise TypeError("The API key is a str")
    api_key = _Secret(api_key)  # before a check that can raise, so the frame shows no key
    if api_key == "":
        raise ValueError("The API key is empty; use None for none")
    if any(not ("!" <= c <= "~") for c in api_key):
        raise ValueError(
            "The API key contains characters a header can't carry (only visible ASCII, no spaces)"
        )
    return api_key


def _tls_server_name(host: str) -> str:
    """The name for TLS (SNI and the name check) of *host*: without an IPv6 zone id.

    ``ssl`` sends no SNI for an IP address, but takes ``fe80::1%eth0`` for a
    name and would send it; RFC 6066 allows no IP address there.
    """
    return host.partition("%")[0]


class _HTTPSConnection(http.client.HTTPSConnection):
    """``http.client.HTTPSConnection`` that leaves an IPv6 zone id out of TLS.

    The TCP connection still goes to the host with its zone.
    """

    def __init__(self, host: str, port: int, timeout: float, context: ssl.SSLContext) -> None:
        super().__init__(host, port, timeout=timeout, context=context)
        self._tls_context = context

    def connect(self) -> None:
        # HTTPSConnection.connect without the zone in server_hostname (the client sets no tunnel).
        http.client.HTTPConnection.connect(self)
        self.sock = self._tls_context.wrap_socket(
            self.sock, server_hostname=_tls_server_name(self.host)
        )


class _PinnedHTTPSConnection(_HTTPSConnection):
    """An HTTPS connection that accepts exactly the certificate with one SHA-256 fingerprint.

    The pin replaces the chain, name and date checks: a station's certificate is
    self-signed, often reached by IP address, and stays pinned until it is
    replaced, even past its expiry date (as in the .NET client). The check runs in
    :meth:`connect`, which ``http.client`` calls before it writes a request, so
    a wrong certificate fails before any header (the API key included) is sent.
    """

    def __init__(self, host: str, port: int, timeout: float, pin: str) -> None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE  # the pin below is the check
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        super().__init__(host, port, timeout, context)
        self._pin = pin
        self._pin_digest = bytes.fromhex(pin)

    def connect(self) -> None:
        super().connect()
        sock = self.sock
        der = sock.getpeercert(binary_form=True) if isinstance(sock, ssl.SSLSocket) else None
        digest = hashlib.sha256(der).digest() if der else None
        if digest is None or not hmac.compare_digest(digest, self._pin_digest):
            self.close()
            raise AccordionQ2CertificateError(
                self._pin, None if digest is None else digest.hex().upper()
            )


class HttpSession:
    """Persistent HTTP(S) connection that reuses a single TCP socket.

    The socket stays open across requests so the hostname is resolved only
    once.  A connection idle for longer than ``IDLE_REOPEN_SECONDS`` is
    reopened before use, since the server may have closed it.

    Retries: a failed request is sent again once only when that can't run it
    twice on the station.  GET, HEAD and OPTIONS are retried on any failure.
    Everything else (value writes, bus transactions, and also the reads sent
    as POST, since reading a byte stream consumes it) is retried only when
    sending failed on a reused connection, so the request never reached the
    server.  A timeout or a dropped connection after sending raises instead:
    the station may have acted on the request, and only the caller knows
    whether doing it again is safe.

    Thread safety: a ``threading.Lock`` serialises all requests through this
    session.  For true request parallelism use one client per thread.

    Args:
        base_url:       Base URL of the WebApi (e.g. ``http://raspberrypi:5000``).
        timeout:        HTTP request timeout in seconds.
        auth:           Optional ``(username, password)`` tuple for HTTP Basic
                        Auth, or a pre-built ``Authorization`` header string.
        verify:         TLS certificate verification.  ``True`` (default) uses
                        the system CA bundle.  ``False`` disables verification
                        (pin a self-signed certificate with *cert_sha256* instead).
                        A string is interpreted as a path to a CA bundle file.
        default_headers: Additional headers merged into every request. An
                        ``X-Api-Key`` here (any case) is taken as *api_key* when
                        that is None, and dropped when it is given.
        api_key:        The station API key, sent as ``X-Api-Key`` with every
                        request.
        cert_sha256:    The SHA-256 fingerprint of the station's HTTPS
                        certificate: exactly that certificate is accepted.

    Raises:
        ValueError: The base URL, key or fingerprint is malformed, or
            *cert_sha256* is given for ``http://`` or with a CA bundle in
            *verify*. The message never contains the key.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float,
        auth: tuple[str, str] | None = None,
        verify: bool | str = True,
        default_headers: dict[str, str] | None = None,
        api_key: str | None = None,
        cert_sha256: str | None = None,
    ) -> None:
        # So a traceback's locals show no key.
        api_key = _secret(api_key)
        default_headers = _secret_headers(default_headers)
        self._scheme, self._host, self._port, self._path_prefix = _parse_base_url(base_url)
        self._timeout = timeout
        self._verify = verify
        self._default_headers: dict[str, str] = dict(default_headers or {})
        # An X-Api-Key in default_headers (the way before 7.0) gets what api_key gets.
        named = [n for n in self._default_headers if n.lower() == API_KEY_HEADER.lower()]
        if api_key is None and len(named) > 1:
            raise ValueError(
                "default_headers has more than one X-Api-Key; pass the key as api_key="
            )
        if api_key is None and named:
            api_key = _secret(self._default_headers[named[0]])
        for name in named:
            del self._default_headers[name]
        self._api_key = _validate_api_key(api_key)
        self._pin: str | None = None
        if cert_sha256 is not None:
            self._pin = normalize_sha256(cert_sha256)
            # A pin must never be silently ignored.
            if self._scheme != "https":
                raise ValueError(
                    "cert_sha256 pins an HTTPS certificate, but the base URL is http://; "
                    "use https://"
                )
            if isinstance(verify, str):
                raise ValueError(
                    "Give either cert_sha256 or a CA bundle in verify, not both: the pin "
                    "accepts exactly one certificate, whatever signed it"
                )
        self._conn: http.client.HTTPConnection | None = None
        self._last_used: float | None = None
        self._lock = threading.Lock()

        if auth is not None:
            import base64

            credentials = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode("ascii")
            self._default_headers["Authorization"] = f"Basic {credentials}"

    def _build_ssl_context(self) -> ssl.SSLContext:
        if self._verify is False:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx
        if isinstance(self._verify, str):
            return ssl.create_default_context(cafile=self._verify)
        return ssl.create_default_context()

    def __repr__(self) -> str:
        # getattr: a traceback may show a session whose __init__ raised part way.
        host = getattr(self, "_host", None)
        if host is None:
            return "HttpSession(<not initialised>)"
        bracketed = f"[{host}]" if ":" in host else host
        has_key = getattr(self, "_api_key", None) is not None
        return (
            f"HttpSession('{getattr(self, '_scheme', '?')}://{bracketed}:"
            f"{getattr(self, '_port', '?')}{getattr(self, '_path_prefix', '')}', "
            f"api_key={'set' if has_key else 'none'}, "
            f"cert_sha256={getattr(self, '_pin', None) or 'none'})"
        )

    @property
    def default_headers(self) -> dict[str, str]:
        """Headers sent with every request (auth, the lease id); not the ``api_key``."""
        return dict(self._default_headers)

    @property
    def has_api_key(self) -> bool:
        """Whether this session sends an ``api_key`` (the key itself is never exposed)."""
        return self._api_key is not None

    def request_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """The headers for one request: the default ones, the API key, then *extra*.

        The ``api_key`` replaces an ``X-Api-Key`` of any case among the default
        headers, also one set later with :meth:`set_default_header`.
        """
        headers = dict(self._default_headers)
        if self._api_key is not None:
            for name in [n for n in headers if n.lower() == API_KEY_HEADER.lower()]:
                del headers[name]
            headers[API_KEY_HEADER] = self._api_key
        if extra:
            headers.update(extra)
        return headers

    def error_for(
        self, status: int, body: bytes, fallback: str | None = None
    ) -> AccordionQ2ApiError:
        """The exception for a refused request with *status* and *body*.

        :class:`AccordionQ2SecurityError` for 401, and for a 403 that names the
        role it needs, with the server's error after the client's own text;
        otherwise :class:`AccordionQ2ApiError` with the server's error, or
        *fallback*, or the body. Server text that would repeat the API key is
        withheld.
        """
        raw = body.decode("utf-8", errors="replace")
        server_message: str | None = None
        requires: str | None = None
        try:
            err = json.loads(raw)
        except ValueError:
            err = None
        if isinstance(err, dict):
            # Common error key names, ASP.NET ProblemDetails fields included
            for key in ("error", "Error", "message", "Message", "detail", "title"):
                if err.get(key):
                    server_message = str(err[key])
                    break
            role = err.get("requires") or err.get("Requires")
            requires = str(role) if role else None
        server_message = self._scrub(server_message)

        if status == 401:
            if self._api_key is not None:
                reason = AccordionQ2SecurityReason.INVALID_API_KEY
                message = (
                    "The station doesn't accept this client's API key (X-Api-Key): it is "
                    "wrong, or was removed on the station"
                )
            else:
                reason = AccordionQ2SecurityReason.MISSING_API_KEY
                message = (
                    "The station needs an API key (X-Api-Key) and this client has none; "
                    "pass api_key= to AccordionQ2Client"
                )
            # The server's own reason too: the 401 may come from something else, e.g. a proxy.
            if server_message is not None:
                message += f" (station: {server_message})"
            return AccordionQ2SecurityError(status, reason, requires, message)
        if status == 403 and requires:
            message = f"This needs the {requires} role, which this client's API key doesn't have"
            if server_message is not None:
                message += f" (station: {server_message})"
            return AccordionQ2SecurityError(
                status, AccordionQ2SecurityReason.ROLE_TOO_LOW, requires, message
            )
        if 300 <= status < 400 and server_message is None:
            # http.client doesn't follow it, and the Location isn't repeated.
            return AccordionQ2ApiError(
                status,
                f"The server answered with a redirect (HTTP {status}), which the station's API "
                "never does; the client doesn't follow it. Check the base URL",
            )
        return AccordionQ2ApiError(
            status, server_message or fallback or self._scrub(raw) or f"HTTP {status}"
        )

    def _scrub(self, text: str | None) -> str | None:
        """*text* from the server, unless it would repeat the API key."""
        if text is None or self._api_key is None or self._api_key not in text:
            return text
        return "(withheld: it contained the API key)"

    def set_default_header(self, name: str, value: str | None) -> None:
        """Send *name* with every request from now on; None stops sending it (the lease id)."""
        with self._lock:
            if value is None:
                self._default_headers.pop(name, None)
            else:
                self._default_headers[name] = value

    def full_path(self, path: str) -> str:
        """*path* under the base URL's path."""
        return "{}/{}".format(self._path_prefix, path.lstrip("/"))

    def new_connection(self, timeout: float | None = None) -> http.client.HTTPConnection:
        """A connection of its own, for a long-lived response such as the event stream.

        It isn't the shared connection, so ordinary requests aren't held up by it.
        """
        return self._open(self._timeout if timeout is None else timeout)

    def _open(self, timeout: float) -> http.client.HTTPConnection:
        """A new, not yet connected connection: plain, pinned HTTPS, or validated HTTPS."""
        if self._scheme != "https":
            return http.client.HTTPConnection(self._host, self._port, timeout=timeout)
        if self._pin is not None:
            return _PinnedHTTPSConnection(self._host, self._port, timeout, self._pin)
        return _HTTPSConnection(self._host, self._port, timeout, self._build_ssl_context())

    def _connect(self) -> None:
        self._last_used = time.monotonic()
        self._conn = self._open(self._timeout)

    def request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes]:
        """Send *method* to *path* and return ``(status, body_bytes)``."""
        # Avoid double slashes when path_prefix is empty or path starts with /
        full_path = "{}/{}".format(self._path_prefix, path.lstrip("/"))
        merged = self.request_headers(headers)
        safe = method.upper() in _SAFE_METHODS
        with self._lock:
            if (
                self._conn is not None
                and self._last_used is not None
                and time.monotonic() - self._last_used > IDLE_REOPEN_SECONDS
            ):
                self._close_conn()
            for attempt in range(2):
                reused = self._conn is not None
                sent = False
                try:
                    if self._conn is None:
                        self._connect()
                    self._conn.request(method, full_path, body=body, headers=merged)  # type: ignore[union-attr]
                    sent = True
                    resp = self._conn.getresponse()  # type: ignore[union-attr]
                    data = resp.read()
                    self._last_used = time.monotonic()
                    return resp.status, data
                except (http.client.HTTPException, OSError) as error:
                    self._close_conn()
                    if isinstance(error, ssl.SSLCertVerificationError):
                        raise  # the same certificate would be refused again
                    # A timeout while sending may still have delivered the request.
                    undelivered = reused and not sent and not isinstance(error, TimeoutError)
                    if attempt > 0 or not (safe or undelivered):
                        raise
        raise http.client.HTTPException("request failed after retry")

    def _close_conn(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def close(self) -> None:
        """Close the persistent connection."""
        with self._lock:
            self._close_conn()


class ApiGroupBase:
    """Base class providing HTTP helpers for API groups."""

    def __init__(self, session: HttpSession) -> None:
        self._session = session

    def _get_json(self, path: str) -> object:
        """Send GET and return parsed JSON."""
        return json.loads(self._request("GET", path))

    def _get_bytes(self, path: str) -> bytes:
        """Send GET and return raw response bytes."""
        return self._request("GET", path)

    def _post(self, path: str, body: object = None) -> None:
        """Send POST (ignore response body)."""
        self._request("POST", path, body=body)

    def _post_json(self, path: str, body: object = None) -> object:
        """Send POST and return parsed JSON response."""
        return json.loads(self._request("POST", path, body=body))

    def _put_json(self, path: str, body: object = None) -> object:
        """Send PUT and return parsed JSON response."""
        return json.loads(self._request("PUT", path, body=body))

    def _post_multipart(self, path: str, filename: str, data: bytes) -> None:
        """Send POST with multipart/form-data file upload."""
        boundary = uuid.uuid4().hex
        # Encode filename per RFC 5987 to handle spaces and non-ASCII safely.
        from urllib.parse import quote as _quote

        encoded_name = _quote(filename, safe="")
        part_header = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; '
            f"filename*=UTF-8''{encoded_name}\r\n"
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        part_footer = f"\r\n--{boundary}--\r\n".encode()
        multipart_body = part_header + data + part_footer
        self._request(
            "POST",
            path,
            body=multipart_body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )

    def _delete(self, path: str) -> None:
        """Send DELETE request."""
        self._request("DELETE", path)

    def _request(
        self,
        method: str,
        path: str,
        body: object = None,
        headers: dict[str, str] | None = None,
    ) -> bytes:
        """Send an HTTP request via the shared persistent session."""
        if headers is None:
            headers = {}
        encoded: bytes | None
        if body is None:
            encoded = None
        elif isinstance(body, bytes):
            encoded = body
        else:
            encoded = json.dumps(body).encode("utf-8")
            headers = {**headers, "Content-Type": "application/json"}
        status, data = self._session.request(method, path, body=encoded, headers=headers)
        if not 200 <= status < 300:
            raise self._session.error_for(status, data)
        return data

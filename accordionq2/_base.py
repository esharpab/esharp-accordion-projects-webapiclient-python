"""HTTP transport layer for AccordionQ2 API groups (stdlib only).

Uses a persistent ``http.client`` connection so that DNS is resolved only
once per connection lifetime.  This avoids the ~625 ms mDNS (.local)
lookup penalty that ``urllib.request.urlopen`` incurs on every call under
Windows.
"""

from __future__ import annotations

import http.client
import json
import ssl
import threading
import uuid
from urllib.parse import urlparse

from .exceptions import AccordionQ2ApiError


class HttpSession:
    """Persistent HTTP(S) connection that reuses a single TCP socket.

    The socket stays open across requests so the hostname is resolved only
    once.  If the connection is dropped by the server the next request
    will automatically reconnect (one retry).

    Thread safety: a ``threading.Lock`` serialises all requests through this
    session.  For true request parallelism use one client per thread.

    Args:
        base_url:       Base URL of the WebApi (e.g. ``http://raspberrypi:5000``).
        timeout:        HTTP request timeout in seconds.
        auth:           Optional ``(username, password)`` tuple for HTTP Basic
                        Auth, or a pre-built ``Authorization`` header string.
        verify:         TLS certificate verification.  ``True`` (default) uses
                        the system CA bundle.  ``False`` disables verification
                        (useful for self-signed certs on embedded devices).
                        A string is interpreted as a path to a CA bundle file.
        default_headers: Additional headers merged into every request.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float,
        auth: tuple[str, str] | None = None,
        verify: bool | str = True,
        default_headers: dict[str, str] | None = None,
    ) -> None:
        parsed = urlparse(base_url)
        self._scheme = parsed.scheme or "http"
        self._host = parsed.hostname
        self._port = parsed.port or (443 if self._scheme == "https" else 80)
        self._path_prefix = parsed.path.rstrip("/")
        self._timeout = timeout
        self._verify = verify
        self._conn: http.client.HTTPConnection | None = None
        self._lock = threading.Lock()

        self._default_headers: dict[str, str] = dict(default_headers or {})
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

    def _connect(self) -> None:
        if self._scheme == "https":
            self._conn = http.client.HTTPSConnection(
                self._host,  # type: ignore[arg-type]
                self._port,
                timeout=self._timeout,
                context=self._build_ssl_context(),
            )
        else:
            self._conn = http.client.HTTPConnection(
                self._host,  # type: ignore[arg-type]
                self._port,
                timeout=self._timeout,
            )

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
        merged = {**self._default_headers, **(headers or {})}
        with self._lock:
            for attempt in range(2):
                try:
                    if self._conn is None:
                        self._connect()
                    self._conn.request(method, full_path, body=body, headers=merged)  # type: ignore[union-attr]
                    resp = self._conn.getresponse()  # type: ignore[union-attr]
                    return resp.status, resp.read()
                except (http.client.HTTPException, OSError):
                    self._close_conn()
                    if attempt > 0:
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
        if status >= 400:
            raw = data.decode("utf-8", errors="replace")
            message = raw
            try:
                err = json.loads(raw)
                if isinstance(err, dict):
                    # Check common error key names including ASP.NET ProblemDetails fields
                    for key in ("error", "Error", "message", "Message", "detail", "title"):
                        if err.get(key):
                            message = str(err[key])
                            break
            except (json.JSONDecodeError, KeyError):
                pass
            raise AccordionQ2ApiError(status, message)
        return data

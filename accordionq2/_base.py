"""HTTP transport layer for AccordionQ2 API groups (stdlib only).

Uses a persistent ``http.client`` connection so that DNS is resolved only
once per connection lifetime.  This avoids the ~625 ms mDNS (.local)
lookup penalty that ``urllib.request.urlopen`` incurs on every call under
Windows.
"""

import http.client
import json
import uuid
from urllib.parse import urlparse

from .exceptions import AccordionQ2ApiError


class HttpSession:
    """Persistent HTTP(S) connection that reuses a single TCP socket.

    The socket stays open across requests so the hostname is resolved only
    once.  If the connection is dropped by the server the next request
    will automatically reconnect (one retry).
    """

    def __init__(self, base_url, timeout):
        parsed = urlparse(base_url)
        self._scheme = parsed.scheme or "http"
        self._host = parsed.hostname
        self._port = parsed.port or (443 if self._scheme == "https" else 80)
        self._path_prefix = parsed.path.rstrip("/")
        self._timeout = timeout
        self._conn = None

    def _connect(self):
        cls = (
            http.client.HTTPSConnection
            if self._scheme == "https"
            else http.client.HTTPConnection
        )
        self._conn = cls(self._host, self._port, timeout=self._timeout)

    def request(self, method, path, body=None, headers=None):
        """Send *method* to *path* and return ``(status, body_bytes)``."""
        full_path = "{}/{}".format(self._path_prefix, path)
        if headers is None:
            headers = {}
        for attempt in range(2):
            try:
                if self._conn is None:
                    self._connect()
                self._conn.request(method, full_path, body=body, headers=headers)
                resp = self._conn.getresponse()
                return resp.status, resp.read()
            except (http.client.HTTPException, OSError):
                self._close_conn()
                if attempt > 0:
                    raise
        raise http.client.HTTPException("request failed after retry")

    def _close_conn(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def close(self):
        """Close the persistent connection."""
        self._close_conn()


class ApiGroupBase:
    """Base class providing HTTP helpers for API groups."""

    def __init__(self, session):
        self._session = session

    def _get_json(self, path):
        """Send GET and return parsed JSON."""
        return json.loads(self._request("GET", path))

    def _get_bytes(self, path):
        """Send GET and return raw response bytes."""
        return self._request("GET", path)

    def _post(self, path, body=None):
        """Send POST (ignore response body)."""
        self._request("POST", path, body=body)

    def _post_json(self, path, body=None):
        """Send POST and return parsed JSON response."""
        return json.loads(self._request("POST", path, body=body))

    def _post_multipart(self, path, filename, data):
        """Send POST with multipart/form-data file upload."""
        boundary = uuid.uuid4().hex
        body = (
            "--{boundary}\r\n"
            "Content-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
            "Content-Type: application/octet-stream\r\n\r\n"
        ).format(boundary=boundary, filename=filename).encode() + data + (
            "\r\n--{}--\r\n".format(boundary)
        ).encode()
        self._request("POST", path, body=body, headers={
            "Content-Type": "multipart/form-data; boundary={}".format(boundary),
        })

    def _delete(self, path):
        """Send DELETE request."""
        self._request("DELETE", path)

    def _request(self, method, path, body=None, headers=None):
        """Send an HTTP request via the shared persistent session."""
        if headers is None:
            headers = {}
        encoded = body
        if body is not None and not isinstance(body, bytes):
            encoded = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        status, data = self._session.request(method, path, body=encoded, headers=headers)
        if status >= 400:
            raw = data.decode("utf-8", errors="replace")
            message = raw
            try:
                err = json.loads(raw)
                if isinstance(err, dict):
                    message = err.get("error") or err.get("Error") or raw
            except (json.JSONDecodeError, KeyError):
                pass
            raise AccordionQ2ApiError(status, message)
        return data

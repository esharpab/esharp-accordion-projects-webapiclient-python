"""HTTP transport layer for AccordionQ2 API groups (stdlib only)."""

import json
import uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .exceptions import AccordionQ2ApiError


class ApiGroupBase:
    """Base class providing HTTP helpers for API groups."""

    def __init__(self, base_url, timeout):
        self._base_url = base_url
        self._timeout = timeout

    def _url(self, path):
        return "{}/{}".format(self._base_url, path)

    def _get_json(self, path):
        """Send GET and return parsed JSON."""
        req = Request(self._url(path))
        return json.loads(self._send(req))

    def _get_bytes(self, path):
        """Send GET and return raw response bytes."""
        req = Request(self._url(path))
        return self._send(req)

    def _post(self, path, body=None):
        """Send POST (ignore response body)."""
        self._send(self._json_request(path, body))

    def _post_json(self, path, body=None):
        """Send POST and return parsed JSON response."""
        return json.loads(self._send(self._json_request(path, body)))

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
        req = Request(
            self._url(path),
            data=body,
            headers={"Content-Type": "multipart/form-data; boundary={}".format(boundary)},
            method="POST",
        )
        self._send(req)

    def _delete(self, path):
        """Send DELETE request."""
        self._send(Request(self._url(path), method="DELETE"))

    def _json_request(self, path, body=None):
        encoded = None
        headers = {}
        if body is not None:
            encoded = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        return Request(self._url(path), data=encoded, headers=headers, method="POST")

    def _send(self, request):
        try:
            with urlopen(request, timeout=self._timeout) as resp:
                return resp.read()
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            message = raw
            try:
                err = json.loads(raw)
                if isinstance(err, dict):
                    message = err.get("error") or err.get("Error") or raw
            except (json.JSONDecodeError, KeyError):
                pass
            raise AccordionQ2ApiError(exc.code, message) from None

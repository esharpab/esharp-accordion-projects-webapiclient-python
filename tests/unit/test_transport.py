"""Unit tests for the HTTP transport layer (_base.py)."""

from __future__ import annotations

import http.client
import json
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from accordionq2._base import ApiGroupBase, HttpSession
from accordionq2.exceptions import AccordionQ2ApiError


def _make_response(status: int, body: bytes) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = body
    return resp


def _make_session(status: int = 200, body: object = None) -> HttpSession:
    """Return a real HttpSession with its internal connection mocked."""
    session = HttpSession("http://localhost:5000", timeout=5.0)
    body_bytes = json.dumps(body).encode() if not isinstance(body, bytes) else body
    mock_conn = MagicMock()
    mock_conn.getresponse.return_value = _make_response(status, body_bytes)
    session._conn = mock_conn
    return session


# ---------------------------------------------------------------------------
# HttpSession – basic request flow
# ---------------------------------------------------------------------------

class TestHttpSession:
    def test_successful_get_returns_body(self):
        session = _make_session(200, {"ok": True})
        status, data = session.request("GET", "api/test")
        assert status == 200
        assert json.loads(data) == {"ok": True}

    def test_path_has_no_double_slash(self):
        session = _make_session(200, b"")
        session.request("GET", "api/test")
        args = session._conn.request.call_args
        path_arg = args[0][1]
        assert "//" not in path_arg, f"Double slash in path: {path_arg!r}"

    def test_path_with_leading_slash(self):
        session = _make_session(200, b"")
        session.request("GET", "/api/test")
        args = session._conn.request.call_args
        path_arg = args[0][1]
        assert not path_arg.startswith("//"), f"Path starts with //: {path_arg!r}"

    def test_reconnects_on_os_error(self):
        session = HttpSession("http://localhost:5000", timeout=5.0)
        body_bytes = json.dumps("ok").encode()
        good_conn = MagicMock()
        good_conn.getresponse.return_value = _make_response(200, body_bytes)

        call_count = 0

        def fail_then_succeed(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OSError("connection reset")

        bad_conn = MagicMock()
        bad_conn.request.side_effect = fail_then_succeed

        with patch.object(HttpSession, "_connect", side_effect=[None, None]) as mock_connect:
            session._conn = bad_conn

            def set_good_conn():
                session._conn = good_conn

            mock_connect.side_effect = set_good_conn
            status, data = session.request("GET", "api/test")
        assert status == 200

    def test_default_headers_merged(self):
        session = HttpSession(
            "http://localhost:5000", timeout=5.0,
            default_headers={"X-Api-Key": "secret"},
        )
        session._conn = MagicMock()
        session._conn.getresponse.return_value = _make_response(200, b'""')
        session.request("GET", "api/test")
        call_headers = session._conn.request.call_args[1].get("headers") or \
                       session._conn.request.call_args[0][3]
        assert call_headers.get("X-Api-Key") == "secret"

    def test_basic_auth_sets_authorization_header(self):
        session = HttpSession("http://localhost:5000", timeout=5.0, auth=("user", "pass"))
        assert "Authorization" in session._default_headers
        assert session._default_headers["Authorization"].startswith("Basic ")

    def test_close_clears_conn(self):
        session = _make_session(200, b'""')
        session.close()
        assert session._conn is None


# ---------------------------------------------------------------------------
# ApiGroupBase – error handling
# ---------------------------------------------------------------------------

class TestApiGroupBaseErrors:
    def _group(self, status: int, body: object) -> ApiGroupBase:
        session = _make_session(status, body)
        return ApiGroupBase(session)

    def test_raises_on_404(self):
        grp = self._group(404, {"error": "Not found"})
        with pytest.raises(AccordionQ2ApiError) as exc_info:
            grp._get_json("api/missing")
        assert exc_info.value.status_code == 404
        assert "Not found" in str(exc_info.value)

    def test_raises_on_500(self):
        grp = self._group(500, {"title": "Internal Server Error"})
        with pytest.raises(AccordionQ2ApiError) as exc_info:
            grp._get_json("api/boom")
        assert exc_info.value.status_code == 500
        assert "Internal Server Error" in str(exc_info.value)

    def test_problem_details_detail_key(self):
        grp = self._group(400, {"detail": "Field X is required"})
        with pytest.raises(AccordionQ2ApiError) as exc_info:
            grp._post_json("api/thing", {})
        assert "Field X is required" in str(exc_info.value)

    def test_problem_details_message_key(self):
        grp = self._group(422, {"message": "Validation failed"})
        with pytest.raises(AccordionQ2ApiError) as exc_info:
            grp._post("api/thing", {})
        assert "Validation failed" in str(exc_info.value)

    def test_non_json_error_body(self):
        grp = self._group(503, b"Service Unavailable")
        with pytest.raises(AccordionQ2ApiError) as exc_info:
            grp._get_json("api/thing")
        assert exc_info.value.status_code == 503
        assert "Service Unavailable" in str(exc_info.value)

    def test_no_error_on_200(self):
        grp = self._group(200, {"result": 42})
        result = grp._get_json("api/thing")
        assert result == {"result": 42}

    def test_no_error_on_201(self):
        grp = self._group(201, b"")
        grp._post("api/thing")  # should not raise

    def test_post_sends_json_content_type(self):
        session = _make_session(200, b"")
        grp = ApiGroupBase(session)
        grp._post("api/thing", {"k": "v"})
        call_headers = session._conn.request.call_args[1].get("headers") or \
                       session._conn.request.call_args[0][3]
        assert "application/json" in call_headers.get("Content-Type", "")


# ---------------------------------------------------------------------------
# ApiGroupBase – multipart upload
# ---------------------------------------------------------------------------

class TestMultipartUpload:
    def test_multipart_content_type_header(self):
        session = _make_session(200, b"")
        grp = ApiGroupBase(session)
        grp._post_multipart("api/upload", "test.bin", b"\x00\x01\x02")
        call_headers = session._conn.request.call_args[1].get("headers") or \
                       session._conn.request.call_args[0][3]
        assert "multipart/form-data" in call_headers.get("Content-Type", "")

    def test_multipart_body_contains_data(self):
        session = _make_session(200, b"")
        grp = ApiGroupBase(session)
        payload = b"\xDE\xAD\xBE\xEF"
        grp._post_multipart("api/upload", "file.bin", payload)
        body_sent = session._conn.request.call_args[1].get("body") or \
                    session._conn.request.call_args[0][2]
        assert payload in body_sent

    def test_multipart_special_filename_encoded(self):
        session = _make_session(200, b"")
        grp = ApiGroupBase(session)
        grp._post_multipart("api/upload", "my file (1).bin", b"data")
        body_sent = session._conn.request.call_args[1].get("body") or \
                    session._conn.request.call_args[0][2]
        # RFC 5987 encoding: spaces become %20
        assert b"%20" in body_sent or b"my%20file" in body_sent

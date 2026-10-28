"""Unit tests for API keys, base URLs, fingerprints, 401/403 and capabilities (FW7 CLI-01).

Connections are mocked here; test_tls.py runs the same against a local HTTPS server.
"""

from __future__ import annotations

import http.client
import json
import pickle
import ssl
import traceback
from unittest.mock import MagicMock, patch

import pytest

from accordionq2 import (
    AccordionQ2ApiError,
    AccordionQ2CertificateError,
    AccordionQ2Client,
    AccordionQ2SecurityError,
    AccordionQ2SecurityReason,
    CapabilitiesDto,
    normalize_sha256,
)
from accordionq2._base import ApiGroupBase, HttpSession, _parse_base_url
from accordionq2.capabilities import CapabilitiesGroup
from accordionq2.events import EventsGroup

KEY = "acc_Sentinel0123456789abcdefKEY"
PIN = "3FA27C" + "00" * 29


def _response(status: int, body: object) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = body if isinstance(body, bytes) else json.dumps(body).encode()
    return resp


def _session(status: int = 200, body: object = "", **kwargs: object) -> HttpSession:
    session = HttpSession("http://localhost:5000", timeout=5.0, **kwargs)  # type: ignore[arg-type]
    session._conn = MagicMock()
    session._conn.getresponse.return_value = _response(status, body)
    return session


def _sent_headers(session: HttpSession) -> dict[str, str]:
    return session._conn.request.call_args.kwargs["headers"]  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Base URLs
# ---------------------------------------------------------------------------


class TestBaseUrl:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("http://station-12:5000", ("http", "station-12", 5000, "")),
            ("https://station-12", ("https", "station-12", 443, "")),
            ("http://10.0.0.5/prefix/", ("http", "10.0.0.5", 80, "/prefix")),
            ("http://[::1]:5000", ("http", "::1", 5000, "")),
            ("https://[2001:db8::12]:5001", ("https", "2001:db8::12", 5001, "")),
            ("http://[fe80::1%eth0]:5000", ("http", "fe80::1%eth0", 5000, "")),
            ("http://[fe80::1%25eth0]:5000", ("http", "fe80::1%eth0", 5000, "")),
            ("http://[fe80::1%25enP4p1s0]:5000", ("http", "fe80::1%enP4p1s0", 5000, "")),
            ("http://[fe80::1%12]:5000", ("http", "fe80::1%12", 5000, "")),
            # As .NET: "%25" followed by more is RFC 6874's "%"; "%25" alone is zone 25.
            ("http://[fe80::1%25]:5000", ("http", "fe80::1%25", 5000, "")),
            ("http://[fe80::1%2525]:5000", ("http", "fe80::1%25", 5000, "")),
            ("http://[fe80::1%2512]:5000", ("http", "fe80::1%12", 5000, "")),
            ("  http://station:5000/  ", ("http", "station", 5000, "")),
        ],
    )
    def test_accepted(self, url, expected):
        assert _parse_base_url(url) == expected

    @pytest.mark.parametrize(
        "url",
        [
            "",
            "   ",
            "station:5000",
            "ftp://station",
            "http://",
            "http://[::1",
            "http://h:x/",
            "http://[fe80::1%]:5000",
        ],
    )
    def test_refused(self, url):
        with pytest.raises(ValueError, match="base URL"):
            _parse_base_url(url)

    def test_credentials_in_the_url_are_refused_without_echoing_them(self):
        with pytest.raises(ValueError) as info:
            AccordionQ2Client(f"http://user:{KEY}@station:5000")
        assert "api_key" in str(info.value)
        assert KEY not in str(info.value)

    def test_the_ipv6_host_is_connected_without_brackets(self):
        session = HttpSession("http://[fe80::1%25eth0]:5000", timeout=1.0)
        conn = session.new_connection()
        assert (conn.host, conn.port) == ("fe80::1%eth0", 5000)

    @pytest.mark.parametrize(
        ("url", "tls_name"),
        [
            ("https://[fe80::1%25eth0]:5001", "fe80::1"),
            ("https://[2001:db8::12]:5001", "2001:db8::12"),
            ("https://station-12:5001", "station-12"),
        ],
    )
    @pytest.mark.parametrize("pinned", [True, False])
    def test_the_zone_id_is_left_out_of_tls(self, url, tls_name, pinned):
        # ssl would send "fe80::1%eth0" as SNI (a name); without the zone it is an address: no SNI.
        session = HttpSession(url, timeout=1.0, cert_sha256=PIN if pinned else None)
        conn = session.new_connection()
        context = MagicMock()
        conn._tls_context = context  # type: ignore[attr-defined]
        with patch.object(http.client.HTTPConnection, "connect"):
            if pinned:  # the mocked socket has no certificate
                with pytest.raises(AccordionQ2CertificateError):
                    conn.connect()
            else:
                conn.connect()
        assert context.wrap_socket.call_args.kwargs["server_hostname"] == tls_name
        assert conn.host == _parse_base_url(url)[1]  # TCP still goes to the zone


# ---------------------------------------------------------------------------
# The API key
# ---------------------------------------------------------------------------


class TestApiKey:
    def test_sent_on_every_request(self):
        session = _session(api_key=KEY)
        group = ApiGroupBase(session)
        group._get_bytes("api/a")
        assert _sent_headers(session)["X-Api-Key"] == KEY
        group._post("api/b", {"x": 1})
        assert _sent_headers(session)["X-Api-Key"] == KEY
        assert _sent_headers(session)["Content-Type"] == "application/json"
        group._post_multipart("api/c", "f.bin", b"data")
        assert _sent_headers(session)["X-Api-Key"] == KEY

    def test_none_sends_no_header(self):
        session = _session()
        ApiGroupBase(session)._get_bytes("api/a")
        assert not any(name.lower() == "x-api-key" for name in _sent_headers(session))
        assert not session.has_api_key

    def test_replaces_one_in_default_headers_whatever_its_case(self):
        session = _session(api_key=KEY, default_headers={"x-api-key": "old", "X-Other": "1"})
        ApiGroupBase(session)._get_bytes("api/a")
        headers = _sent_headers(session)
        assert [n for n in headers if n.lower() == "x-api-key"] == ["X-Api-Key"]
        assert headers["X-Api-Key"] == KEY
        assert headers["X-Other"] == "1"

    def test_default_headers_alone_still_work(self):
        session = _session(default_headers={"X-Api-Key": "by-hand"})
        ApiGroupBase(session)._get_bytes("api/a")
        assert _sent_headers(session)["X-Api-Key"] == "by-hand"

    def test_one_in_default_headers_is_handled_as_the_api_key(self):
        session = _session(default_headers={"x-api-key": KEY, "X-Other": "1"})
        assert session.has_api_key
        assert session.default_headers == {"X-Other": "1"}
        assert "api_key=set" in repr(session)
        ApiGroupBase(session)._get_bytes("api/a")
        headers = _sent_headers(session)
        assert [n for n in headers if n.lower() == "x-api-key"] == ["X-Api-Key"]
        assert headers["X-Api-Key"] == KEY
        echoed = session.error_for(500, json.dumps({"error": f"unknown key {KEY}"}).encode())
        assert KEY not in str(echoed)
        refused = session.error_for(401, b"")
        assert isinstance(refused, AccordionQ2SecurityError)
        assert refused.reason is AccordionQ2SecurityReason.INVALID_API_KEY

    def test_two_in_default_headers_are_refused(self):
        with pytest.raises(ValueError, match="more than one X-Api-Key") as info:
            HttpSession(
                "http://s:5000", 1.0, default_headers={"X-Api-Key": KEY, "x-api-key": "acc_B"}
            )
        assert KEY not in str(info.value)

    def test_a_bad_one_in_default_headers_is_refused_without_echoing_it(self):
        with pytest.raises(ValueError, match="characters a header") as info:
            AccordionQ2Client("http://s:5000", default_headers={"X-Api-Key": KEY + "\n"})
        assert KEY not in str(info.value)

    def test_one_set_later_in_any_case_is_replaced(self):
        session = _session(api_key=KEY)
        session.set_default_header("x-api-key", "acc_B")
        ApiGroupBase(session)._get_bytes("api/a")
        headers = _sent_headers(session)
        assert [n for n in headers if n.lower() == "x-api-key"] == ["X-Api-Key"]
        assert headers["X-Api-Key"] == KEY

    def test_a_traceback_with_locals_shows_no_key_after_a_failed_request(self):
        session = HttpSession("http://localhost:5000", 1.0, api_key=KEY)
        conn = MagicMock()
        conn.request.side_effect = ConnectionRefusedError("refused")
        with (
            patch.object(HttpSession, "_open", return_value=conn),
            pytest.raises(OSError) as info,
        ):
            ApiGroupBase(session)._get_bytes("api/a")
        text = "".join(
            traceback.TracebackException.from_exception(info.value, capture_locals=True).format()
        )
        assert "'X-Api-Key': '<api key>'" in text
        assert KEY not in text
        # The key itself is still what goes on the wire.
        sent = conn.request.call_args.kwargs["headers"]["X-Api-Key"]
        assert sent == KEY and sent.encode("latin-1") == KEY.encode()

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"api_key": KEY + " "},
            {"api_key": KEY, "cert_sha256": "nope"},
            {"default_headers": {"X-Api-Key": KEY + "\n"}},
        ],
    )
    def test_a_traceback_with_locals_shows_no_key_after_a_refused_constructor(self, kwargs):
        with pytest.raises(ValueError) as info:
            AccordionQ2Client("https://station:5001", **kwargs)
        del kwargs  # the test's own argument; the client's frames are what is checked
        text = "".join(
            traceback.TracebackException.from_exception(info.value, capture_locals=True).format()
        )
        assert "<api key>" in text
        assert KEY not in text

    def test_repr_of_a_partly_built_client(self):
        assert repr(AccordionQ2Client.__new__(AccordionQ2Client)) == (
            "AccordionQ2Client(<not initialised>)"
        )
        assert repr(HttpSession.__new__(HttpSession)) == "HttpSession(<not initialised>)"
        session = HttpSession.__new__(HttpSession)
        session._scheme, session._host, session._port, session._path_prefix = (
            "http",
            "s",
            5000,
            "",
        )
        assert repr(session) == "HttpSession('http://s:5000', api_key=none, cert_sha256=none)"

    def test_kept_with_the_lease_id(self):
        session = _session(api_key=KEY)
        session.set_default_header("X-Lease-Id", "L1")
        ApiGroupBase(session)._get_bytes("api/a")
        assert _sent_headers(session)["X-Lease-Id"] == "L1"
        assert _sent_headers(session)["X-Api-Key"] == KEY

    def test_not_among_the_public_default_headers(self):
        session = _session(api_key=KEY)
        assert KEY not in session.default_headers.values()
        assert session.has_api_key

    @pytest.mark.parametrize(
        "bad", ["", " ", f"{KEY} ", f"{KEY}\r\nX-Evil: 1", f"{KEY}\n", f"{KEY}é", f"\t{KEY}"]
    )
    def test_a_key_a_header_cannot_carry_is_refused_without_echoing_it(self, bad):
        with pytest.raises(ValueError) as info:
            AccordionQ2Client("http://station:5000", api_key=bad)
        assert KEY not in str(info.value)
        assert KEY not in repr(info.value)

    def test_a_key_that_is_not_a_str_is_refused(self):
        with pytest.raises(TypeError):
            AccordionQ2Client("http://station:5000", api_key=KEY.encode())  # type: ignore[arg-type]

    def test_repr_shows_only_that_a_key_is_set(self):
        client = AccordionQ2Client("http://[::1]:5000/x", api_key=KEY)
        text = repr(client)
        assert KEY not in text
        assert "api_key=set" in text
        assert "http://[::1]:5000/x" in text
        assert "api_key=none" in repr(AccordionQ2Client("http://station:5000"))

    def test_the_key_is_keyword_only(self):
        with pytest.raises(TypeError):
            AccordionQ2Client("http://s:5000", 30.0, None, True, None, KEY)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Certificate pins: arguments
# ---------------------------------------------------------------------------


class TestPinArguments:
    @pytest.mark.parametrize(
        "text",
        [
            PIN,
            PIN.lower(),
            ":".join(PIN[i : i + 2] for i in range(0, 64, 2)),
            " ".join(PIN[i : i + 2] for i in range(0, 64, 2)).lower(),
            "-".join(PIN[i : i + 2] for i in range(0, 64, 2)),
            f"  {PIN}\n",
        ],
    )
    def test_the_usual_forms_normalize(self, text):
        assert normalize_sha256(text) == PIN

    @pytest.mark.parametrize(
        ("text", "match"),
        [
            (PIN[:-2], "this has 62"),
            (PIN + "00", "this has 66"),
            ("G" + PIN[1:], "hex digits"),
            (f"sha256:{PIN}", "hex digits"),
            ("", "this has 0"),
        ],
    )
    def test_anything_else_is_refused(self, text, match):
        with pytest.raises(ValueError, match=match):
            normalize_sha256(text)

    def test_a_pin_on_http_is_refused_not_ignored(self):
        with pytest.raises(ValueError, match="https://"):
            AccordionQ2Client("http://station:5000", cert_sha256=PIN)

    def test_a_pin_with_a_ca_bundle_is_refused_not_ignored(self):
        with pytest.raises(ValueError, match="not both"):
            AccordionQ2Client("https://station:5001", cert_sha256=PIN, verify="ca.pem")

    def test_a_pin_with_verify_false_still_pins(self):
        session = HttpSession("https://station:5001", 5.0, verify=False, cert_sha256=PIN)
        conn = session.new_connection()
        assert type(conn).__name__ == "_PinnedHTTPSConnection"

    def test_the_shared_and_the_stream_connections_are_both_pinned(self):
        session = HttpSession("https://station:5001", 5.0, cert_sha256=PIN.lower())
        session._connect()
        assert type(session._conn).__name__ == "_PinnedHTTPSConnection"
        assert type(session.new_connection()).__name__ == "_PinnedHTTPSConnection"
        assert f"cert_sha256={PIN}" in repr(session)

    def test_without_a_pin_https_is_validated(self):
        conn = HttpSession("https://station:5001", 5.0).new_connection()
        assert type(conn).__name__ == "_HTTPSConnection"
        context = conn._tls_context  # type: ignore[attr-defined]
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname

    def test_the_certificate_error(self):
        actual = "AB" * 32
        error = AccordionQ2CertificateError(PIN, actual)
        assert isinstance(error, ssl.SSLCertVerificationError)
        assert isinstance(error, OSError)
        assert (error.expected, error.actual) == (PIN, actual)
        assert "AB:AB:AB" in str(error)
        assert "3F:A2:7C" in str(error)
        assert error.verify_message == str(error)
        copy = pickle.loads(pickle.dumps(error))
        assert (copy.expected, copy.actual, str(copy)) == (PIN, actual, str(error))
        assert "no certificate" in str(AccordionQ2CertificateError(PIN, None))

    def test_a_certificate_error_is_not_retried(self):
        session = HttpSession("https://station:5001", 5.0, cert_sha256=PIN)
        conn = MagicMock()
        conn.request.side_effect = AccordionQ2CertificateError(PIN, "AB" * 32)
        with (
            patch.object(HttpSession, "_open", return_value=conn) as opened,
            pytest.raises(AccordionQ2CertificateError),
        ):
            session.request("GET", "api/a")
        assert opened.call_count == 1


# ---------------------------------------------------------------------------
# 401, 403 and redirects
# ---------------------------------------------------------------------------


def _error(status: int, body: object, **kwargs: object) -> AccordionQ2ApiError:
    group = ApiGroupBase(_session(status, body, **kwargs))
    with pytest.raises(AccordionQ2ApiError) as info:
        group._get_bytes("api/a")
    return info.value


class TestSecurityErrors:
    def test_401_without_a_key(self):
        error = _error(
            401,
            {
                "error": "This station needs an API key in X-Api-Key (no API key was sent)",
                "requires": "Operator",
            },
        )
        assert isinstance(error, AccordionQ2SecurityError)
        assert error.status_code == 401
        assert error.reason is AccordionQ2SecurityReason.MISSING_API_KEY
        assert error.required_role == "Operator"
        assert "api_key=" in str(error)
        assert str(error).endswith(
            "(station: This station needs an API key in X-Api-Key (no API key was sent))"
        )

    def test_401_keeps_the_servers_reason(self):
        # A 401 needn't be the station's: here a proxy refuses the 5.x Basic auth.
        error = _error(401, {"error": "Proxy: Basic credentials rejected"}, auth=("bob", "pw"))
        assert isinstance(error, AccordionQ2SecurityError)
        assert "(station: Proxy: Basic credentials rejected)" in str(error)

    def test_401_text_with_the_key_is_withheld(self):
        error = _error(401, {"error": f"unknown key {KEY}"}, api_key=KEY)
        assert KEY not in str(error)
        assert "(station: (withheld: it contained the API key))" in str(error)

    def test_401_with_a_key(self):
        error = _error(401, {"error": "...", "requires": "Viewer"}, api_key=KEY)
        assert isinstance(error, AccordionQ2SecurityError)
        assert error.reason is AccordionQ2SecurityReason.INVALID_API_KEY
        assert "wrong, or was removed" in str(error)
        assert KEY not in str(error)
        assert KEY not in repr(error)

    def test_401_without_a_body(self):
        error = _error(401, b"")
        assert isinstance(error, AccordionQ2SecurityError)
        assert error.required_role is None

    def test_403_with_a_role(self):
        error = _error(
            403,
            {"error": "This needs the Admin role; key 'line-3' is Operator", "requires": "Admin"},
            api_key=KEY,
        )
        assert isinstance(error, AccordionQ2SecurityError)
        assert error.reason is AccordionQ2SecurityReason.ROLE_TOO_LOW
        assert error.required_role == "Admin"
        assert str(error).startswith("This needs the Admin role")
        assert "key 'line-3' is Operator" in str(error)

    def test_403_without_a_role_is_a_plain_api_error(self):
        error = _error(403, {"error": "The folder is read-only"})
        assert type(error) is AccordionQ2ApiError
        assert str(error) == "The folder is read-only"

    def test_server_text_with_the_key_is_withheld(self):
        error = _error(500, {"error": f"bad key {KEY}"}, api_key=KEY)
        assert KEY not in str(error)
        assert "withheld" in str(error)
        error = _error(403, {"error": f"key {KEY}", "requires": "Admin"}, api_key=KEY)
        assert KEY not in str(error)
        error = _error(400, f"plain text {KEY}".encode(), api_key=KEY)
        assert KEY not in str(error)

    def test_a_redirect_is_an_error_not_followed(self):
        error = _error(302, b"")
        assert type(error) is AccordionQ2ApiError
        assert error.status_code == 302
        assert "redirect" in str(error)

    def test_other_errors_are_as_before(self):
        error = _error(404, {"error": "Not found"})
        assert type(error) is AccordionQ2ApiError
        assert str(error) == "Not found"
        assert repr(error) == "AccordionQ2ApiError(404, 'Not found')"


# ---------------------------------------------------------------------------
# The event stream
# ---------------------------------------------------------------------------


class TestEventStreamSecurity:
    def _open(self, response: MagicMock, **kwargs: object) -> tuple[MagicMock, object]:
        session = HttpSession("http://localhost:5000", timeout=5.0, **kwargs)  # type: ignore[arg-type]
        conn = MagicMock()
        conn.getresponse.return_value = response
        with patch.object(HttpSession, "new_connection", return_value=conn):
            try:
                return conn, EventsGroup(session).open()
            except Exception as error:
                return conn, error

    def test_the_key_goes_on_the_stream(self):
        response = MagicMock()
        response.status = 200
        lines = [b"id: 1\n", b"event: hello\n", b'data: {"streamId":"s"}\n', b"\n"]
        response.readline.side_effect = lines
        conn, stream = self._open(response, api_key=KEY)
        headers = conn.request.call_args.kwargs["headers"]
        assert headers["X-Api-Key"] == KEY
        assert headers["Accept"] == "text/event-stream"
        assert stream.stream_id == "s"  # type: ignore[union-attr]

    def test_a_refused_stream_raises_the_security_error(self):
        conn, error = self._open(_response(401, {"error": "x", "requires": "Viewer"}))
        assert isinstance(error, AccordionQ2SecurityError)
        assert error.reason is AccordionQ2SecurityReason.MISSING_API_KEY
        conn.close.assert_called()

    def test_another_failure_is_an_api_error(self):
        conn, error = self._open(_response(404, b""))
        assert type(error) is AccordionQ2ApiError
        assert error.status_code == 404  # type: ignore[union-attr]
        assert "event stream" in str(error)
        conn.close.assert_called()


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class TestCapabilities:
    def _get(self, status: int, body: object) -> CapabilitiesDto:
        session = _session(status, body)
        return CapabilitiesGroup(session).get()

    def test_parsed(self):
        caps = self._get(
            200,
            {
                "apiVersion": 1,
                "webApiVersion": "7.0.0",
                "codecVersion": 3,
                "features": ["channels.encoded", "events", "security.apikey"],
                "securityMode": "Report",
            },
        )
        assert caps.api_version == 1
        assert caps.webapi_version == "7.0.0"
        assert caps.codec_version == 3
        assert caps.security_mode == "Report"
        assert caps.has(CapabilitiesDto.SECURITY_API_KEY)
        assert caps.has(CapabilitiesDto.EVENTS)
        assert not caps.has("instruments")

    def test_an_older_webapi_reports_off(self):
        caps = self._get(200, {"apiVersion": 1, "features": ["events"]})
        assert caps.security_mode == "Off"

    def test_a_webapi_without_it(self):
        assert self._get(404, b"") == CapabilitiesDto()

    def test_on_the_client(self):
        assert isinstance(AccordionQ2Client("http://s:5000").capabilities, CapabilitiesGroup)

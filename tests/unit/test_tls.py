"""The API key, certificate pins and IPv6 against real local servers (FW7 CLI-01).

Every server here listens on the loopback interface only. The certificates are
in data/tls (see make-certs.sh there); their keys are public, so they are fit for
these tests and nothing else.
"""

from __future__ import annotations

import json
import socket
import ssl
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from accordionq2 import (
    AccordionQ2ApiError,
    AccordionQ2CertificateError,
    AccordionQ2Client,
    AccordionQ2SecurityError,
    AccordionQ2SecurityReason,
    sha256_of,
)

TLS = Path(__file__).parent / "data" / "tls"
KEY = "acc_Sentinel0123456789abcdefKEY"


@dataclass
class Station:
    """A local server that records what reached it."""

    url: str
    requests: list[tuple[str, dict[str, str]]] = field(default_factory=list)
    connections: int = 0


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    station: Station
    redirect_to: str | None = None

    def do_GET(self) -> None:
        self.station.requests.append((self.path, dict(self.headers.items())))
        if self.path == "/api/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b'id: 1\nevent: hello\ndata: {"streamId":"s1"}\n\n')
            self.wfile.flush()
            return
        if self.path == "/api/redirect" and self.redirect_to:
            self._send(302, b"", {"Location": self.redirect_to + "/api/connection/status"})
            return
        if self.path.startswith("/api/") and self.headers.get("X-Api-Key") != KEY:
            body = {"error": "This station needs an API key in X-Api-Key", "requires": "Viewer"}
            self._send(
                401, json.dumps(body).encode(), {"WWW-Authenticate": 'ApiKey header="X-Api-Key"'}
            )
            return
        self._send(200, json.dumps({"isConnected": True, "lastError": None}).encode())

    def _send(self, status: int, body: bytes, headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, host: str, family: socket.AddressFamily, station: Station) -> None:
        self.address_family = family
        self.station = station
        handler = type("Handler", (_Handler,), {"station": station})
        super().__init__((host, 0), handler)

    def get_request(self) -> tuple[socket.socket, object]:
        conn, addr = super().get_request()
        self.station.connections += 1
        return conn, addr

    def handle_error(self, request: object, client_address: object) -> None:
        pass  # a refused handshake or a closed connection: expected here


@contextmanager
def _serve(
    certificate: str | None, host: str = "127.0.0.1", redirect_to: str | None = None
) -> Iterator[Station]:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    station = Station(url="")
    server = _Server(host, family, station)
    server.RequestHandlerClass.redirect_to = redirect_to  # type: ignore[attr-defined]
    scheme = "http"
    if certificate is not None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(TLS / f"{certificate}.pem", TLS / f"{certificate}-key.pem")
        # The handshake runs in the handler, so get_request counts every connection.
        server.socket = context.wrap_socket(
            server.socket, server_side=True, do_handshake_on_connect=False
        )
        scheme = "https"
    port = server.server_address[1]
    station.url = f"{scheme}://{f'[{host}]' if ':' in host else host}:{port}"
    thread = threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    try:
        yield station
    finally:
        server.shutdown()
        server.server_close()


def _ipv6_loopback() -> bool:
    if not socket.has_ipv6:
        return False
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
            s.bind(("::1", 0))
        return True
    except OSError:
        return False


needs_ipv6 = pytest.mark.skipif(not _ipv6_loopback(), reason="no IPv6 loopback here")


@pytest.fixture
def self_signed() -> Iterator[Station]:
    with _serve("self-signed") as station:
        yield station


@pytest.fixture
def pin() -> str:
    return sha256_of((TLS / "self-signed.pem").read_text())


def _pin_forms(pin: str) -> list[str]:
    pairs = [pin[i : i + 2] for i in range(0, 64, 2)]
    return [pin.lower(), ":".join(pairs), " ".join(pairs).lower()]


class TestPinnedHttps:
    def test_the_pinned_certificate_is_accepted_in_any_form(self, self_signed, pin):
        for form in _pin_forms(pin):
            with AccordionQ2Client(self_signed.url, api_key=KEY, cert_sha256=form) as client:
                assert client.connection.get_status().is_connected
        assert len(self_signed.requests) == 3
        assert all(headers["X-Api-Key"] == KEY for _, headers in self_signed.requests)

    def test_another_certificate_is_refused_before_anything_is_sent(self, self_signed, pin):
        wrong = ("0" if pin[0] != "0" else "1") + pin[1:]
        with (
            AccordionQ2Client(self_signed.url, api_key=KEY, cert_sha256=wrong) as client,
            pytest.raises(AccordionQ2CertificateError) as info,
        ):
            client.connection.get_status()
        assert self_signed.requests == []  # so the key never left the client
        assert self_signed.connections == 1  # and it wasn't tried again
        assert info.value.actual == pin
        assert info.value.expected == wrong
        assert KEY not in str(info.value)

    def test_without_a_pin_the_self_signed_certificate_is_refused(self, self_signed):
        with (
            AccordionQ2Client(self_signed.url, api_key=KEY) as client,
            pytest.raises(ssl.SSLCertVerificationError) as info,
        ):
            client.connection.get_status()
        assert not isinstance(info.value, AccordionQ2CertificateError)
        assert self_signed.requests == []
        assert self_signed.connections == 1

    def test_the_event_stream_is_pinned_and_carries_the_key(self, self_signed, pin):
        with (
            AccordionQ2Client(self_signed.url, api_key=KEY, cert_sha256=pin) as client,
            client.events.open() as events,
        ):
            assert events.stream_id == "s1"
        path, headers = self_signed.requests[0]
        assert path == "/api/events"
        assert headers["X-Api-Key"] == KEY

    def test_the_event_stream_refuses_another_certificate(self, self_signed, pin):
        wrong = "00" * 32 if pin != "00" * 32 else "11" * 32
        with (
            AccordionQ2Client(self_signed.url, api_key=KEY, cert_sha256=wrong) as client,
            pytest.raises(AccordionQ2CertificateError),
        ):
            client.events.open()
        assert self_signed.requests == []

    def test_a_pinned_certificate_past_its_expiry_date_is_accepted(self):
        # A pin checks identity, not dates (as in .NET): a station's clock may be wrong, and its
        # own certificate stays pinned until it is replaced. docs/security.md says so.
        with _serve("expired") as station:
            expired_pin = sha256_of((TLS / "expired.pem").read_text())
            with AccordionQ2Client(station.url, api_key=KEY, cert_sha256=expired_pin) as client:
                assert client.connection.get_status().is_connected
            with (
                AccordionQ2Client(station.url, api_key=KEY) as client,
                pytest.raises(ssl.SSLCertVerificationError),
            ):
                client.connection.get_status()

    def test_sha256_of_refuses_a_pem_chain(self, pin):
        own = (TLS / "self-signed.pem").read_text()
        with pytest.raises(ValueError, match="holds 2 certificates"):
            sha256_of(own + (TLS / "ca.pem").read_text())
        assert sha256_of(own) == pin

    @needs_ipv6
    def test_ipv6_literal(self, pin):
        with _serve("self-signed", host="::1") as station:
            with AccordionQ2Client(station.url, api_key=KEY, cert_sha256=pin) as client:
                assert client.connection.get_status().is_connected
            assert station.requests[0][1]["Host"].startswith("[::1]:")


class TestTrustedCa:
    """``verify=<CA bundle>``: the chain, the host name and the serverAuth EKU are checked."""

    def test_a_server_certificate_from_the_ca_is_accepted(self):
        with _serve("server") as station:
            with AccordionQ2Client(station.url, verify=str(TLS / "ca.pem"), api_key=KEY) as c:
                assert c.connection.get_status().is_connected

    def test_a_certificate_only_for_tls_clients_is_refused(self):
        with _serve("client-eku") as station:
            with (
                AccordionQ2Client(station.url, verify=str(TLS / "ca.pem"), api_key=KEY) as c,
                pytest.raises(ssl.SSLCertVerificationError) as info,
            ):
                c.connection.get_status()
            assert "purpose" in info.value.verify_message  # not the chain or the name
            assert station.requests == []

    def test_a_self_signed_certificate_is_not_from_the_ca(self, self_signed):
        with (
            AccordionQ2Client(self_signed.url, verify=str(TLS / "ca.pem"), api_key=KEY) as c,
            pytest.raises(ssl.SSLCertVerificationError),
        ):
            c.connection.get_status()
        assert self_signed.requests == []


class TestPlainHttp:
    def test_401_from_a_station_in_security_mode_on(self):
        with _serve(None) as station:
            with (
                AccordionQ2Client(station.url) as client,
                pytest.raises(AccordionQ2SecurityError) as info,
            ):
                client.connection.get_status()
            assert info.value.reason is AccordionQ2SecurityReason.MISSING_API_KEY
            assert info.value.required_role == "Viewer"

    def test_a_redirect_is_not_followed_so_the_key_stays_put(self):
        with _serve(None) as elsewhere:
            with _serve(None, redirect_to=elsewhere.url) as station:
                with (
                    AccordionQ2Client(station.url, api_key=KEY) as client,
                    pytest.raises(AccordionQ2ApiError) as info,
                ):
                    client.connection._get_bytes("api/redirect")
                assert info.value.status_code == 302
                assert "redirect" in str(info.value)
            assert elsewhere.connections == 0

    @needs_ipv6
    def test_ipv6_literal(self):
        with _serve(None, host="::1") as station:
            with AccordionQ2Client(station.url, api_key=KEY) as client:
                assert client.connection.get_status().is_connected
            assert station.requests[0][1]["Host"].startswith("[::1]:")

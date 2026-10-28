"""Unit tests for the FPGA image upload (POST/GET /api/channels/bytestream, firmware 7.0.5)."""

from __future__ import annotations

import http.client
import io
import json

import pytest

from accordionq2 import ByteStreamLoadError, ByteStreamStatus
from accordionq2._base import HttpSession
from accordionq2.channels import ChannelsGroup
from accordionq2.exceptions import AccordionQ2ApiError

CHANNEL = "1.MicroHAPS.JTAG.FPGA_IMAGE"


class FakeSession(HttpSession):
    """Answers from a list and records what was sent (a file body as the bytes it held)."""

    def __init__(self, *responses: tuple[int, object]) -> None:
        super().__init__("http://localhost:5000", timeout=5.0)
        self.responses = list(responses)
        self.sent: list[tuple[str, str, object, dict[str, str]]] = []

    def request(self, method, path, body=None, headers=None):  # type: ignore[override]
        self.sent.append(
            (method, path, body.read() if hasattr(body, "read") else body, headers or {})
        )
        status, payload = self.responses.pop(0)
        return status, payload if isinstance(payload, bytes) else json.dumps(payload).encode()


def test_upload_bytes_posts_octets_with_name_file_and_target():
    session = FakeSession((202, {"state": "loading", "image": {"fileName": "top.bit", "size": 3}}))
    status = ChannelsGroup(session).upload_bytestream(CHANNEL, b"\x01\x02\x03", file_name="top.bit")
    assert status.state == "loading" and status.running
    assert status.image is not None and status.image.file_name == "top.bit"
    method, path, body, headers = session.sent[0]
    assert method == "POST"
    assert path.startswith(
        "api/channels/bytestream?name=1.MicroHAPS.JTAG.FPGA_IMAGE&fileName=top.bit&target=sram"
    )
    assert "force" not in path
    assert body == b"\x01\x02\x03"
    assert headers["Content-Type"] == "application/octet-stream"


def test_upload_a_path_sends_the_open_file_with_its_size_and_name(tmp_path):
    image = tmp_path / "hci_mig_top.bit"
    image.write_bytes(b"x" * 1000)
    session = FakeSession((202, {"state": "loading"}))
    ChannelsGroup(session).upload_bytestream(CHANNEL, image, force=True)
    _, path, body, headers = session.sent[0]
    assert "fileName=hci_mig_top.bit" in path and path.endswith("&force=true")
    assert body == b"x" * 1000
    assert headers["Content-Length"] == "1000"


def test_upload_a_stream_without_a_file_number_goes_chunked():
    session = FakeSession((202, {"state": "loading"}))
    ChannelsGroup(session).upload_bytestream(CHANNEL, io.BytesIO(b"abc"), file_name="a.bit")
    _, _, body, headers = session.sent[0]
    assert body == b"abc"
    assert "Content-Length" not in headers


def test_a_refusal_raises_with_the_station_s_text():
    session = FakeSession((409, {"error": "An FPGA image load is running (top.bit, 42 %)"}))
    with pytest.raises(AccordionQ2ApiError) as caught:
        ChannelsGroup(session).upload_bytestream(CHANNEL, b"x", file_name="x.bit")
    assert caught.value.status_code == 409
    assert "An FPGA image load is running" in str(caught.value)


def test_load_fpga_image_waits_until_done():
    session = FakeSession(
        (202, {"state": "loading", "progress": 0}),
        (200, {"state": "loading", "progress": 42.0, "phase": "Load SRAM"}),
        (
            200,
            {
                "state": "done",
                "progress": 100,
                "message": "Loaded and configured",
                "image": {
                    "fileName": "a.bit",
                    "sha256": "ab" * 32,
                    "result": "ok",
                    "loaded": True,
                    "durationMs": 20750,
                },
            },
        ),
    )
    status = ChannelsGroup(session).load_fpga_image(CHANNEL, b"bits", file_name="a.bit", timeout=10)
    assert status.state == "done" and status.ended
    assert status.image is not None and status.image.result == "ok" and status.image.loaded
    assert status.image.duration_ms == 20750
    assert [s[0] for s in session.sent] == ["POST", "GET", "GET"]


def test_load_fpga_image_raises_on_failed():
    session = FakeSession(
        (202, {"state": "loading"}),
        (
            200,
            {"state": "failed", "message": "openFPGALoader exited 1: Error: device not supported"},
        ),
    )
    with pytest.raises(ByteStreamLoadError) as caught:
        ChannelsGroup(session).load_fpga_image(CHANNEL, b"bits", file_name="a.bit", timeout=10)
    assert "device not supported" in str(caught.value)
    assert caught.value.status.state == "failed"


def test_wait_times_out(monkeypatch):
    session = FakeSession(*[(200, {"state": "loading", "progress": 5})] * 50)
    with pytest.raises(TimeoutError):
        ChannelsGroup(session).wait_bytestream(CHANNEL, timeout=0.02, poll=0.005)


def test_status_parses_defaults():
    status = ByteStreamStatus.from_dict({"state": "idle"})
    assert status.targets == ["sram"] and status.image is None and not status.running


class _Conn:
    """A connection whose first request fails before anything is sent, then answers 202."""

    def __init__(self) -> None:
        self.bodies: list[bytes] = []
        self.calls = 0

    def request(self, method, path, body=None, headers=None):
        self.calls += 1
        self.bodies.append(body.read())
        if self.calls == 1:
            raise http.client.RemoteDisconnected("closed")

    def getresponse(self):
        class R:
            status = 202

            def read(self):
                return b'{"state":"loading"}'

        return R()

    def close(self):
        pass


def test_a_retried_file_body_is_sent_again_from_its_start():
    session = HttpSession("http://localhost:5000", timeout=5.0)
    conn = _Conn()
    session._conn = conn  # type: ignore[assignment]
    session._connect = lambda: setattr(session, "_conn", conn)  # type: ignore[method-assign]
    body = io.BytesIO(b"0123456789")
    status, _ = session.request("POST", "api/channels/bytestream", body=body)
    assert status == 202
    assert conn.bodies == [b"0123456789", b"0123456789"]

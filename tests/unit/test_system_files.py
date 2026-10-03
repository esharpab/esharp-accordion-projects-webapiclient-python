"""Unit tests for the system and file groups (accordionq2 contract sections 9 and 10)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from accordionq2._base import HttpSession
from accordionq2.exceptions import AccordionQ2ApiError
from accordionq2.files import FilesGroup
from accordionq2.system import SystemGroup


class FakeSession(HttpSession):
    """An HttpSession answering from a list and recording what was sent."""

    def __init__(self, *responses: tuple[int, object]) -> None:
        super().__init__("http://localhost:5000", timeout=5.0)
        self.responses = list(responses)
        self.sent: list[tuple[str, str, bytes | None, dict[str, str]]] = []

    def request(self, method, path, body=None, headers=None):  # type: ignore[override]
        self.sent.append((method, path, body, headers or {}))
        status, payload = self.responses.pop(0)
        return status, payload if isinstance(payload, bytes) else json.dumps(payload).encode()


def test_services_are_read_with_their_actions():
    session = FakeSession(
        (
            200,
            [
                {
                    "id": "hardware",
                    "unit": "accordion.service",
                    "description": "Accordion",
                    "installed": True,
                    "activeState": "active",
                    "subState": "running",
                    "enabled": True,
                    "since": "2026-10-03T08:00:00+00:00",
                    "self": False,
                    "actions": ["start", "stop", "restart", "enable", "disable"],
                }
            ],
        )
    )
    (hardware,) = SystemGroup(session).get_services()
    assert hardware.active_state == "active" and hardware.enabled and not hardware.self
    assert "stop" in hardware.actions


def test_service_actions_and_reboot_are_posts():
    session = FakeSession((202, {}), (202, {}))
    system = SystemGroup(session)
    system.service_action("hardware", "restart")
    system.reboot()
    assert [s[:2] for s in session.sent] == [
        ("POST", "api/system/services/hardware/restart"),
        ("POST", "api/system/reboot"),
    ]


def test_set_clock_sends_utc_to_the_millisecond():
    clock = {
        "utc": "2026-10-03T08:15:00.250+00:00",
        "timeZone": "Etc/UTC",
        "ntpEnabled": True,
        "ntpSynchronized": False,
    }
    session = FakeSession((200, clock))
    result = SystemGroup(session).set_clock(
        datetime(2026, 10, 3, 10, 15, 0, 250000, tzinfo=timezone(timedelta(hours=2)))
    )
    method, path, body, _ = session.sent[0]
    assert (method, path) == ("PUT", "api/system/clock")
    assert json.loads(body) == {"utc": "2026-10-03T08:15:00.250+00:00", "force": False}
    assert result.time_zone == "Etc/UTC" and not result.ntp_synchronized


def test_an_ntp_kept_clock_is_a_409():
    session = FakeSession(
        (409, {"error": "The clock is kept by a time server; set it anyway with force"})
    )
    with pytest.raises(AccordionQ2ApiError) as raised:
        SystemGroup(session).set_clock()
    assert raised.value.status_code == 409


def test_listing_and_paths_are_escaped():
    session = FakeSession(
        (
            200,
            {
                "root": "alias",
                "path": "a b",
                "writable": True,
                "entries": [
                    {
                        "name": "x.csv",
                        "directory": False,
                        "size": 3,
                        "modified": "2026-10-03T08:00:00+00:00",
                    },
                    {
                        "name": "sub",
                        "directory": True,
                        "size": None,
                        "modified": "2026-10-03T08:00:00+00:00",
                    },
                ],
            },
        )
    )
    listing = FilesGroup(session).list("alias", "a b")
    assert session.sent[0][1] == "api/files/alias?path=a%20b"
    assert [e.name for e in listing.entries] == ["x.csv", "sub"]
    assert listing.entries[1].size is None


def test_upload_sends_the_bytes_raw():
    session = FakeSession((200, {"name": "x.bin", "directory": False, "size": 3, "modified": ""}))
    entry = FilesGroup(session).upload("media", "x.bin", b"\x00\x01\x02", overwrite=True)
    method, path, body, headers = session.sent[0]
    assert (method, path) == ("PUT", "api/files/media/content?path=x.bin&overwrite=true")
    assert body == b"\x00\x01\x02" and headers["Content-Type"] == "application/octet-stream"
    assert entry.size == 3


def test_move_and_recursive_delete():
    session = FakeSession((200, {}), (204, b""))
    files = FilesGroup(session)
    files.move("alias", "a.csv", "sub/a.csv")
    files.delete("alias", "sub", recursive=True)
    assert json.loads(session.sent[0][2]) == {
        "from": "a.csv",
        "to": "sub/a.csv",
        "overwrite": False,
    }
    assert session.sent[1][:2] == ("DELETE", "api/files/alias?path=sub&recursive=true")

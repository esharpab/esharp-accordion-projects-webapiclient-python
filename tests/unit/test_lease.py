"""Unit tests for the control lease."""

from __future__ import annotations

import json

import pytest

from accordionq2._base import HttpSession
from accordionq2.exceptions import AccordionQ2ApiError
from accordionq2.lease import HEADER, LeaseGroup


class FakeSession(HttpSession):
    """An HttpSession whose requests are answered from a list, recording the headers sent."""

    def __init__(self, *responses: tuple[int, object]) -> None:
        super().__init__("http://localhost:5000", timeout=5.0)
        self.responses = list(responses)
        self.sent: list[tuple[str, str, dict[str, str]]] = []

    def request(self, method, path, body=None, headers=None):  # type: ignore[override]
        self.sent.append((method, path, {**self.default_headers, **(headers or {})}))
        status, payload = self.responses.pop(0)
        return status, json.dumps(payload).encode()


def test_acquire_sends_the_lease_id_from_then_on_and_release_stops():
    session = FakeSession(
        (200, {"leaseId": "L1", "owner": "TAT", "expiresInMs": 30000}),
        (200, {"leaseId": "L1", "owner": "TAT", "expiresInMs": 30000}),
        (204, ""),
    )
    lease = LeaseGroup(session)
    granted = lease.acquire("TAT", 30000)
    assert granted.lease_id == "L1" and granted.held
    assert HEADER not in session.sent[0][2]

    lease.renew()
    assert session.sent[1][:2] == ("PUT", "api/lease/L1")
    assert session.sent[1][2][HEADER] == "L1"

    lease.release()
    assert session.sent[2][:2] == ("DELETE", "api/lease/L1")
    assert lease.held_lease_id is None


def test_a_held_lease_is_a_409_with_the_holder():
    session = FakeSession((409, {"error": "The station is leased by X", "heldBy": "X"}))
    with pytest.raises(AccordionQ2ApiError) as raised:
        LeaseGroup(session).acquire("me")
    assert raised.value.status_code == 409
    assert LeaseGroup(session).held_lease_id is None


def test_hold_releases_even_when_the_block_fails():
    session = FakeSession((200, {"leaseId": "L2", "owner": "TAT"}), (204, ""))
    lease = LeaseGroup(session)
    with pytest.raises(RuntimeError), lease.hold("TAT", ttl_ms=60000):
        raise RuntimeError("sequence failed")
    assert session.sent[-1][:2] == ("DELETE", "api/lease/L2")
    assert lease.held_lease_id is None

"""Unit tests for the event stream, subscriptions and reads with a maximum age."""

from __future__ import annotations

import io
import json
from unittest.mock import MagicMock

import pytest

from accordionq2._base import HttpSession
from accordionq2.events import EventStream
from accordionq2.resources import ResourcesGroup
from accordionq2.subscriptions import SubscriptionsGroup


def _stream(text: str) -> EventStream:
    response = MagicMock()
    response.readline.side_effect = io.BytesIO(text.encode()).readline
    return EventStream(MagicMock(), response)


HELLO = (
    "id: 1\nevent: hello\n"
    'data: {"isConnected":true,"generation":3,"apiVersion":1,"streamId":"abc"}\n\n'
)


class TestEventStream:
    def test_hello_is_read_on_open(self):
        stream = _stream(HELLO)
        assert stream.stream_id == "abc"
        assert stream.hello["generation"] == 3

    def test_events_pings_and_multiline_data(self):
        stream = _stream(
            HELLO
            + ": ping\n\n"
            + 'id: 2\nevent: values\ndata: {"subscription":"s",\ndata: "values":{"A":"1"}}\n\n'
            + 'id: 3\nevent: configuration\ndata: {"changeType":"Changed"}\n\n'
        )
        events = iter(stream)
        values = next(events)
        assert (values.id, values.name, values.data["values"]) == (2, "values", {"A": "1"})
        assert next(events).name == "configuration"
        with pytest.raises(ConnectionError):
            next(events)

    def test_a_stream_without_hello_is_refused(self):
        with pytest.raises(ConnectionError):
            _stream('id: 1\nevent: connection\ndata: {"isConnected":true}\n\n')

    def test_an_old_webapi_has_no_stream_id(self):
        assert _stream('id: 1\nevent: hello\ndata: {"isConnected":true}\n\n').stream_id is None

    def test_silence_raises_timeout(self):
        response = MagicMock()
        lines = iter([*(line.encode() for line in HELLO.splitlines(keepends=True))])

        def readline():
            try:
                return next(lines)
            except StopIteration:
                raise TimeoutError("timed out") from None

        response.readline.side_effect = readline
        stream = EventStream(MagicMock(), response)
        with pytest.raises(TimeoutError):
            next(iter(stream))


def _session(*responses: tuple[int, object]) -> MagicMock:
    session = MagicMock(spec=HttpSession)
    session.request.side_effect = [(s, json.dumps(b).encode()) for s, b in responses]
    return session


class TestSubscriptions:
    def test_create_sends_stream_channels_and_interval(self):
        session = _session((200, {"id": "x1", "expiresInMs": 60000}))
        sub = SubscriptionsGroup(session).create("abc", ["A", "B"], 500)
        method, path = session.request.call_args.args[:2]
        assert (method, path) == ("POST", "api/subscriptions")
        assert json.loads(session.request.call_args.kwargs["body"]) == {
            "StreamId": "abc",
            "Channels": ["A", "B"],
            "IntervalMs": 500,
        }
        assert (sub.id, sub.expires_in_ms) == ("x1", 60000)

    def test_update_is_a_put_and_delete_a_delete(self):
        session = _session((200, {"id": "x1", "expiresInMs": 60000}), (204, ""))
        group = SubscriptionsGroup(session)
        group.update("x1", ["C"], 1000)
        assert session.request.call_args.args[:2] == ("PUT", "api/subscriptions/x1")
        session.request.side_effect = [(204, b"")]
        group.delete("x1")
        assert session.request.call_args.args[:2] == ("DELETE", "api/subscriptions/x1")


class TestMaxAge:
    def test_read_values_sends_max_age_and_returns_ages(self):
        session = _session((200, {"resources": {"A": "1.5"}, "ageMs": {"A": 320}}))
        values, ages = ResourcesGroup(session).read_values(["A"], max_age_ms=1000)
        assert json.loads(session.request.call_args.kwargs["body"]) == {
            "Names": ["A"],
            "MaxAgeMs": 1000,
        }
        assert values == {"A": "1.5"}
        assert ages == {"A": 320.0}

    def test_without_max_age_the_body_is_as_before(self):
        session = _session((200, {"resources": {"A": "1.5"}}))
        assert ResourcesGroup(session).get_values(["A"]) == {"A": "1.5"}
        assert json.loads(session.request.call_args.kwargs["body"]) == {"Names": ["A"]}

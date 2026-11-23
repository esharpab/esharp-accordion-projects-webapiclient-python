"""Unit tests for 429 and Retry-After (FW7_PLAN CLI-05 follow-up): the typed error, the wait."""

from __future__ import annotations

import io
import json
import pickle
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from unittest.mock import MagicMock, patch

import pytest

from accordionq2 import (
    AccordionQ2ApiError,
    AccordionQ2Client,
    AccordionQ2ThrottledError,
    _base,
)
from accordionq2._base import (
    MAX_THROTTLE_RESENDS,
    ApiGroupBase,
    HttpResponse,
    HttpSession,
    header_value,
    parse_retry_after,
)
from accordionq2.events import EventsGroup

KEY = "acc_Sentinel0123456789abcdefKEY"
BLOCKED = {"error": "Too many failed keys from 10.0.0.9; try again in 4 s", "requires": "Viewer"}


def _response(status: int, body: object, headers: dict[str, str] | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = body if isinstance(body, bytes) else json.dumps(body).encode()
    resp.headers = headers or {}
    return resp


def _session(*responses: MagicMock, **kwargs: object) -> HttpSession:
    session = HttpSession("http://localhost:5000", timeout=5.0, **kwargs)  # type: ignore[arg-type]
    session._conn = MagicMock()
    session._conn.getresponse.side_effect = list(responses)
    return session


@pytest.fixture
def slept(monkeypatch):
    waits: list[float] = []
    monkeypatch.setattr(_base, "_sleep", waits.append)
    return waits


class TestRetryAfter:
    def test_seconds(self):
        assert parse_retry_after("4") == 4.0
        assert parse_retry_after(" 900 ") == 900.0

    def test_an_http_date(self):
        now = datetime(2026, 11, 23, 12, 0, 0, tzinfo=UTC)
        when = format_datetime(now + timedelta(seconds=30), usegmt=True)
        assert parse_retry_after(when, now) == 30.0

    def test_a_date_in_the_past_is_zero(self):
        now = datetime(2026, 11, 23, 12, 0, 0, tzinfo=UTC)
        assert parse_retry_after(format_datetime(now - timedelta(hours=1), usegmt=True), now) == 0

    @pytest.mark.parametrize("value", [None, "", "soon", "-3", "1.5", "٣"])
    def test_unreadable_is_none(self, value):
        assert parse_retry_after(value) is None

    def test_header_lookup_in_any_case(self):
        assert header_value({"retry-after": "3"}, "Retry-After") == "3"
        assert header_value(None, "Retry-After") is None
        assert header_value({}, "Retry-After") is None


class TestThrottledError:
    def test_429_is_typed_with_retry_after_and_the_stations_text(self):
        session = _session(_response(429, BLOCKED, {"Retry-After": "4"}))
        with pytest.raises(AccordionQ2ThrottledError) as info:
            ApiGroupBase(session)._get_bytes("api/channels")
        error = info.value
        assert isinstance(error, AccordionQ2ApiError)
        assert error.status_code == 429
        assert error.retry_after == 4.0
        assert error.station_message == BLOCKED["error"]
        assert str(error).startswith(BLOCKED["error"])
        assert "retry after 4 s" in str(error)

    def test_429_without_retry_after(self):
        # The subscriptions' "at most N per stream": no wait to wait out.
        session = _session(_response(429, {"error": "A stream can have at most 64 subscriptions"}))
        with pytest.raises(AccordionQ2ThrottledError) as info:
            ApiGroupBase(session)._post("api/subscriptions", {})
        assert info.value.retry_after is None
        assert "retry after" not in str(info.value)

    def test_429_without_a_body(self):
        error = HttpSession("http://s:5000", 1.0).error_for(429, b"", headers={"Retry-After": "1"})
        assert isinstance(error, AccordionQ2ThrottledError)
        assert error.station_message is None
        assert str(error).startswith("Too many requests")

    def test_the_key_is_withheld_from_it(self):
        session = _session(
            _response(429, {"error": f"blocked {KEY}"}, {"Retry-After": "2"}), api_key=KEY
        )
        with pytest.raises(AccordionQ2ThrottledError) as info:
            ApiGroupBase(session)._get_bytes("api/a")
        assert KEY not in str(info.value)
        assert KEY not in repr(info.value)

    def test_503_carries_retry_after_but_stays_a_plain_error(self):
        busy = {"error": "The station is busy checking passwords; try again in a few seconds"}
        session = _session(_response(503, busy, {"Retry-After": "5"}))
        with pytest.raises(AccordionQ2ApiError) as info:
            ApiGroupBase(session)._post_json("api/security/login", {})
        assert type(info.value) is AccordionQ2ApiError
        assert info.value.retry_after == 5.0

    def test_other_errors_have_no_retry_after(self):
        session = _session(_response(404, {"error": "Not found"}))
        with pytest.raises(AccordionQ2ApiError) as info:
            ApiGroupBase(session)._get_bytes("api/a")
        assert info.value.retry_after is None

    def test_pickles(self):
        error = AccordionQ2ThrottledError("m", 3.0, "s")
        copy = pickle.loads(pickle.dumps(error))
        assert (str(copy), copy.retry_after, copy.station_message) == ("m", 3.0, "s")

    def test_a_plain_tuple_from_a_mocked_session_still_works(self):
        session = MagicMock()
        session.request.return_value = (429, b"")
        session.error_for = HttpSession("http://s:5000", 1.0).error_for
        with pytest.raises(AccordionQ2ThrottledError) as info:
            ApiGroupBase(session)._get_bytes("api/a")
        assert info.value.retry_after is None


class TestThrottleWait:
    def test_off_by_default(self, slept):
        session = _session(_response(429, BLOCKED, {"Retry-After": "1"}))
        with pytest.raises(AccordionQ2ThrottledError):
            ApiGroupBase(session)._get_bytes("api/a")
        assert slept == []
        assert session._conn.request.call_count == 1  # type: ignore[union-attr]

    def test_waits_and_resends(self, slept):
        session = _session(
            _response(429, BLOCKED, {"Retry-After": "2"}),
            _response(200, b"ok"),
            max_throttle_wait=5,
        )
        assert ApiGroupBase(session)._get_bytes("api/a") == b"ok"
        assert slept == [2.0]
        assert session._conn.request.call_count == 2  # type: ignore[union-attr]

    def test_resends_a_post_with_its_body(self, slept):
        # A 429 comes before the station acts on a request, so a write is resent too.
        session = _session(
            _response(429, BLOCKED, {"Retry-After": "1"}),
            _response(200, {"done": True}),
            max_throttle_wait=5,
        )
        assert ApiGroupBase(session)._post_json("api/a", {"x": 1}) == {"done": True}
        bodies = [c.kwargs["body"] for c in session._conn.request.call_args_list]  # type: ignore[union-attr]
        assert bodies == [b'{"x": 1}', b'{"x": 1}']

    def test_not_longer_than_the_limit(self, slept):
        session = _session(_response(429, BLOCKED, {"Retry-After": "900"}), max_throttle_wait=60)
        with pytest.raises(AccordionQ2ThrottledError) as info:
            ApiGroupBase(session)._get_bytes("api/a")
        assert info.value.retry_after == 900.0
        assert slept == []

    def test_not_without_retry_after(self, slept):
        session = _session(_response(429, BLOCKED), max_throttle_wait=60)
        with pytest.raises(AccordionQ2ThrottledError):
            ApiGroupBase(session)._get_bytes("api/a")
        assert slept == []

    def test_a_few_times_at_most(self, slept):
        answers = [
            _response(429, BLOCKED, {"Retry-After": "1"}) for _ in range(MAX_THROTTLE_RESENDS + 1)
        ]
        session = _session(*answers, _response(200, b"never"), max_throttle_wait=5)
        with pytest.raises(AccordionQ2ThrottledError):
            ApiGroupBase(session)._get_bytes("api/a")
        assert slept == [1.0] * MAX_THROTTLE_RESENDS
        assert session._conn.request.call_count == MAX_THROTTLE_RESENDS + 1  # type: ignore[union-attr]

    def test_a_seekable_upload_is_resent_from_its_start(self, slept):
        session = HttpSession("http://localhost:5000", 5.0, max_throttle_wait=5)
        sent: list[bytes] = []
        conn = MagicMock()
        conn.request.side_effect = lambda m, p, body=None, headers=None: sent.append(body.read())
        conn.getresponse.side_effect = [
            _response(429, BLOCKED, {"Retry-After": "1"}),
            _response(202, b"{}"),
        ]
        session._conn = conn
        body = io.BytesIO(b"0123456789")
        body.seek(2)
        status, _ = session.request("POST", "api/channels/bytestream", body=body)
        assert status == 202
        assert sent == [b"23456789", b"23456789"]

    def test_never_a_stream_that_cannot_seek(self, slept):
        class OneWay(io.RawIOBase):
            def readable(self):
                return True

            def seekable(self):
                return False

            def read(self, n=-1):
                return b""

        session = _session(_response(429, BLOCKED, {"Retry-After": "1"}), max_throttle_wait=5)
        response = session.request("POST", "api/files/x", body=OneWay())  # type: ignore[arg-type]
        assert response.status == 429
        assert slept == []

    def test_the_wait_is_outside_the_lock(self, monkeypatch):
        session = _session(
            _response(429, BLOCKED, {"Retry-After": "1"}),
            _response(200, b"ok"),
            max_throttle_wait=5,
        )
        held: list[bool] = []
        monkeypatch.setattr(_base, "_sleep", lambda s: held.append(session._lock.locked()))
        ApiGroupBase(session)._get_bytes("api/a")
        assert held == [False]

    def test_set_on_the_client(self):
        client = AccordionQ2Client("http://s:5000", max_throttle_wait=30)
        assert client._session.max_throttle_wait == 30
        assert AccordionQ2Client("http://s:5000")._session.max_throttle_wait == 0

    def test_the_response_keeps_its_headers(self):
        session = _session(_response(200, b"x", {"Retry-After": "7"}))
        response = session.request("GET", "api/a")
        assert isinstance(response, HttpResponse)
        status, data = response
        assert (status, data) == (200, b"x")
        assert header_value(response.headers, "retry-after") == "7"


class TestEventStreamThrottle:
    def _open(self, *responses: MagicMock, **kwargs: object) -> tuple[list[MagicMock], object]:
        session = HttpSession("http://localhost:5000", timeout=5.0, **kwargs)  # type: ignore[arg-type]
        conns = []
        for response in responses:
            conn = MagicMock()
            conn.getresponse.return_value = response
            conns.append(conn)
        with patch.object(HttpSession, "new_connection", side_effect=conns):
            try:
                return conns, EventsGroup(session).open()
            except Exception as error:
                return conns, error

    @staticmethod
    def _hello() -> MagicMock:
        response = MagicMock()
        response.status = 200
        response.readline.side_effect = [b"event: hello\n", b'data: {"streamId":"s"}\n', b"\n"]
        return response

    def test_a_429_raises_the_throttled_error(self, slept):
        conns, error = self._open(_response(429, BLOCKED, {"Retry-After": "3"}))
        assert isinstance(error, AccordionQ2ThrottledError)
        assert error.retry_after == 3.0
        conns[0].close.assert_called()
        assert slept == []

    def test_waited_out_on_a_new_connection(self, slept):
        conns, stream = self._open(
            _response(429, BLOCKED, {"Retry-After": "3"}), self._hello(), max_throttle_wait=10
        )
        assert stream.stream_id == "s"  # type: ignore[union-attr]
        assert slept == [3.0]
        conns[0].close.assert_called()

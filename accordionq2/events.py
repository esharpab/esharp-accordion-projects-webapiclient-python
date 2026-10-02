"""The WebApi's event stream (``GET /api/events``, accordionq2 contract section 4)."""

from __future__ import annotations

import http.client
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any

from ._base import HttpSession
from .exceptions import AccordionQ2ApiError

#: The contract's limit: no data at all (events or pings) for this long means a dead stream.
SILENCE_LIMIT_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class ServerEvent:
    """One event: ``hello``, ``connection``, ``configuration`` or ``values``."""

    #: Increases by one per event within a stream; a gap means events were dropped.
    id: int
    name: str
    #: The event's data, parsed from JSON.
    data: dict[str, Any] = field(default_factory=dict, hash=False)


class EventStream:
    """An open event stream on a connection of its own.

    Iterate it for events; ``hello`` has already been read when it opens, so
    :attr:`stream_id` is there for :meth:`SubscriptionsGroup.create`::

        with client.events.open() as events:
            sub = client.subscriptions.create(events.stream_id, ["Engine.Uptime"], 1000)
            for event in events:
                if event.name == "values":
                    print(event.data["values"])

    Raises ``TimeoutError`` after :data:`SILENCE_LIMIT_SECONDS` without data,
    and ``ConnectionError`` when the server ends the stream. Reconnecting is
    the caller's: open a new stream, subscribe again, and reload channels, as
    the contract asks. Missed events aren't replayed.
    """

    def __init__(
        self, conn: http.client.HTTPConnection, response: http.client.HTTPResponse
    ) -> None:
        self._conn = conn
        self._response = response
        first = next(self._events(), None)
        if first is None or first.name != "hello":
            self.close()
            raise ConnectionError("The event stream didn't start with hello")
        #: The ``hello`` event's data: ``isConnected``, ``generation``,
        #: ``apiVersion`` and ``streamId``.
        self.hello: dict[str, Any] = first.data

    @property
    def stream_id(self) -> str | None:
        """The id to subscribe this stream to values with.

        None from a WebApi without subscriptions.
        """
        value = self.hello.get("streamId")
        return value if isinstance(value, str) else None

    def __iter__(self) -> Iterator[ServerEvent]:
        return self._events()

    def _events(self) -> Iterator[ServerEvent]:
        event_id, name = 0, "message"
        data: list[str] = []
        while True:
            try:
                raw = self._response.readline()
            except TimeoutError as error:
                raise TimeoutError(
                    f"No data from the event stream for {SILENCE_LIMIT_SECONDS:.0f} s"
                ) from error
            if not raw:
                raise ConnectionError("The event stream ended")
            line = raw.decode("utf-8").rstrip("\r\n")
            if line == "":
                if data:
                    yield ServerEvent(event_id, name, json.loads("\n".join(data)))
                event_id, name = 0, "message"
                data = []
                continue
            if line.startswith(":"):
                continue  # a ping: it only proves the stream is alive
            key, _, value = line.partition(":")
            value = value[1:] if value.startswith(" ") else value
            if key == "id":
                event_id = int(value) if value.isdigit() else 0
            elif key == "event":
                name = value
            elif key == "data":
                data.append(value)

    def close(self) -> None:
        """Close the stream; its subscriptions end with it on the server."""
        try:
            self._conn.close()
        except Exception:
            pass

    def __enter__(self) -> EventStream:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


class EventsGroup:
    """Opens event streams."""

    def __init__(self, session: HttpSession) -> None:
        self._session = session

    def open(self, silence_limit: float = SILENCE_LIMIT_SECONDS) -> EventStream:
        """Open ``GET /api/events`` on a new connection and read its ``hello``."""
        conn = self._session.new_connection(timeout=silence_limit)
        conn.request(
            "GET",
            self._session.full_path("api/events"),
            headers={**self._session.default_headers, "Accept": "text/event-stream"},
        )
        response = conn.getresponse()
        if response.status >= 400:
            body = response.read().decode("utf-8", errors="replace")
            conn.close()
            raise AccordionQ2ApiError(
                response.status, body or "The event stream couldn't be opened"
            )
        return EventStream(conn, response)

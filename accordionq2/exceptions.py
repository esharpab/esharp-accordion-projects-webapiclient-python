"""Exception types for the AccordionQ2 client."""

from __future__ import annotations


class AccordionQ2ApiError(Exception):
    """Raised when the AccordionQ2 API returns a non-success HTTP status code."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code

    def __repr__(self) -> str:
        return f"AccordionQ2ApiError({self.status_code}, {self.args[0]!r})"


class AccordionQ2ShortReadError(Exception):
    """Raised when a bus read reports success but returns fewer bytes than requested.

    This most often indicates an out-of-date webapi/agent whose bus layer silently
    accepts a receive of the wrong length and returns a short (often empty) payload
    instead of failing -- a case that would otherwise be indistinguishable from a
    genuine read.
    """

    def __init__(self, requested_bytes: int, received_bytes: int) -> None:
        super().__init__(
            f"Bus read returned {received_bytes} of {requested_bytes} requested byte(s). "
            "The transaction reported success but delivered a short read. This commonly "
            "means the target webapi/agent is out of date and silently accepts a receive "
            "of the wrong length -- confirm the agent has the bus Receive-length fix deployed."
        )
        self.requested_bytes = requested_bytes
        self.received_bytes = received_bytes

    def __repr__(self) -> str:
        return f"AccordionQ2ShortReadError({self.requested_bytes}, {self.received_bytes})"

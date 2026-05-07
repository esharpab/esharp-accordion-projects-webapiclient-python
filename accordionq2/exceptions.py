"""Exception types for the AccordionQ2 client."""

from __future__ import annotations


class AccordionQ2ApiError(Exception):
    """Raised when the AccordionQ2 API returns a non-success HTTP status code."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code

    def __repr__(self) -> str:
        return f"AccordionQ2ApiError({self.status_code}, {self.args[0]!r})"

"""Exception types for the AccordionQ2 client.

None of them ever carries the API key: not in the message, the repr or an attribute.
"""

from __future__ import annotations

import ssl
from enum import StrEnum


class AccordionQ2ApiError(Exception):
    """Raised when the AccordionQ2 API returns a non-success HTTP status code.

    A refusal for want of an API key or a role is the subclass
    :class:`AccordionQ2SecurityError`; a 429 (slowed down) is
    :class:`AccordionQ2ThrottledError`.
    """

    def __init__(self, status_code: int, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        #: Seconds the station asked the client to wait (its ``Retry-After``), None when it
        #: didn't say: a 429, or a 503 while the station is busy checking passwords.
        self.retry_after = retry_after

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.status_code}, {self.args[0]!r})"


class AccordionQ2SecurityReason(StrEnum):
    """Why a station refused a request (security mode ``On``)."""

    #: 401: the station needs an API key and this client has none.
    MISSING_API_KEY = "MissingApiKey"
    #: 401: the station doesn't know this client's API key (wrong, or removed).
    INVALID_API_KEY = "InvalidApiKey"
    #: 403: the key is known but its role is too low; see ``required_role``.
    ROLE_TOO_LOW = "RoleTooLow"
    #: 401: the station doesn't accept this client's login token (it expired, was logged out,
    #: or isn't valid) and the client sent no API key; log in again (firmware 7.1.0).
    INVALID_TOKEN = "InvalidToken"
    #: 401 from a login call itself (``requires`` ``Anonymous``): a wrong user name or
    #: password, a wrong current password, or a login that can't be renewed any more.
    LOGIN_REFUSED = "LoginRefused"


class AccordionQ2SecurityError(AccordionQ2ApiError):
    """Raised when a station refuses a request for want of a valid API key (401) or a role (403).

    The message names the cause and never contains the key. A 403 that doesn't
    name a role (a change in a read-only folder) stays a plain
    :class:`AccordionQ2ApiError`.
    """

    def __init__(
        self,
        status_code: int,
        reason: AccordionQ2SecurityReason,
        required_role: str | None,
        message: str,
    ) -> None:
        super().__init__(status_code, message)
        #: Why the station refused.
        self.reason = reason
        #: The role the request needs (``Viewer``, ``Operator`` or ``Admin``), if the station said.
        self.required_role = required_role


class AccordionQ2ThrottledError(AccordionQ2ApiError):
    """Raised when the station answers 429: it is slowing this client down (firmware 7.1.0).

    In security mode ``On`` a client address that sent too many wrong API keys, login tokens
    or passwords is blocked for a while (2 s, doubling up to 15 min), and too many requests
    without a credential are limited; :attr:`retry_after` says for how long. The client waits
    and resends by itself only when it was made with ``max_throttle_wait`` (FW7_PLAN CLI-05
    follow-up).
    """

    def __init__(
        self, message: str, retry_after: float | None, station_message: str | None
    ) -> None:
        super().__init__(429, message, retry_after=retry_after)
        #: The station's own text (its ``error``), None when it sent none.
        self.station_message = station_message

    def __reduce__(
        self,
    ) -> tuple[type[AccordionQ2ThrottledError], tuple[str, float | None, str | None]]:
        return (type(self), (self.args[0], self.retry_after, self.station_message))


class AccordionQ2CertificateError(ssl.SSLCertVerificationError):
    """Raised when a station's HTTPS certificate isn't the one pinned with ``cert_sha256``.

    It is raised during the TLS handshake, before any request (and so the API
    key) is sent. It is an ``ssl.SSLCertVerificationError``, as an untrusted
    certificate is without a pin, so ``except ssl.SSLError`` and
    ``except OSError`` catch it too.
    """

    def __init__(self, expected: str, actual: str | None) -> None:
        if actual is None:
            message = (
                "The station sent no certificate, so it can't be the pinned one; nothing was sent"
            )
        else:
            message = (
                f"The station's certificate isn't the pinned one: its SHA-256 fingerprint is "
                f"{_colons(actual)}, the pin is {_colons(expected)}. Nothing was sent. If the "
                "station has a new certificate, check the fingerprint with its administrator "
                "and update cert_sha256"
            )
        # (errno, strerror), as ssl raises its own: str() is then the message alone.
        super().__init__(ssl.SSL_ERROR_SSL, message)
        #: The pinned fingerprint, as 64 upper-case hex digits.
        self.expected = expected
        #: The fingerprint of the certificate the server sent, as 64 upper-case hex digits;
        #: None if it sent none.
        self.actual = actual
        # As ssl's own verification errors have them.
        self.verify_code = 0
        self.verify_message = message

    def __reduce__(self) -> tuple[type[AccordionQ2CertificateError], tuple[str, str | None]]:
        return (type(self), (self.expected, self.actual))


def _colons(hex_digits: str) -> str:
    return ":".join(hex_digits[i : i + 2] for i in range(0, len(hex_digits), 2))


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


class AccordionQ2NotSupportedError(Exception):
    """Raised when the station lacks a feature a call needs, before the call is made.

    *feature* is the capability it lacks (see :class:`CapabilitiesDto`), such as
    ``"values.cacheOnly"``.
    """

    def __init__(self, feature: str, message: str) -> None:
        super().__init__(message)
        self.feature = feature

    def __repr__(self) -> str:
        return f"AccordionQ2NotSupportedError({self.feature!r}, {self.args[0]!r})"

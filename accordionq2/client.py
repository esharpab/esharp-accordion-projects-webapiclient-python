"""Main client for the AccordionQ2 REST API."""

from __future__ import annotations

from ._base import HttpSession
from .application import ApplicationGroup
from .channels import ChannelsGroup
from .comm import CommGroup
from .connection import ConnectionGroup
from .media import MediaGroup
from .modules import ModulesGroup
from .numeric_results import NumericResultsGroup
from .resources import ResourcesGroup


class AccordionQ2Client:
    """Client for the AccordionQ2 Hardware Management REST API.

    Uses a persistent HTTP connection so that DNS is resolved only once
    per client lifetime, avoiding the ~625 ms mDNS penalty on Windows.

    Usage::

        with AccordionQ2Client("http://agent64.local:5000") as client:
            names = client.resources.get_names()
            status = client.application.get_status()

    The client can also be used without a context manager::

        client = AccordionQ2Client("http://agent64.local:5000")
        names = client.resources.get_names()
        client.close()

    Args:
        base_url:        Base URL of the WebApi (e.g. ``http://raspberrypi:5000``).
        timeout:         HTTP request timeout in seconds (default 30).
        auth:            Optional ``(username, password)`` tuple for HTTP Basic Auth.
        verify:          TLS certificate verification.  ``True`` (default) uses the
                         system CA bundle.  ``False`` disables verification (useful for
                         self-signed certs on embedded devices).  A string is treated as
                         a path to a CA bundle file.
        default_headers: Additional HTTP headers merged into every request (e.g. for
                         API keys: ``{"X-Api-Key": "secret"}``).
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        auth: tuple[str, str] | None = None,
        verify: bool | str = True,
        default_headers: dict[str, str] | None = None,
    ) -> None:
        self._session = HttpSession(
            base_url, timeout, auth=auth, verify=verify, default_headers=default_headers
        )
        self.resources = ResourcesGroup(self._session)
        self.channels = ChannelsGroup(self._session)
        self.modules = ModulesGroup(self._session)
        self.application = ApplicationGroup(self._session)
        self.media = MediaGroup(self._session)
        self.connection = ConnectionGroup(self._session)
        self.comm = CommGroup(self._session)
        self.numeric_results = NumericResultsGroup(self._session)

    def __enter__(self) -> AccordionQ2Client:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying persistent HTTP connection."""
        self._session.close()

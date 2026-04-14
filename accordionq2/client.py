"""Main client for the AccordionQ2 REST API."""

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
        base_url: Base URL of the WebApi (e.g. ``http://raspberrypi:5000``).
        timeout:  HTTP request timeout in seconds (default 30).
    """

    def __init__(self, base_url, timeout=30.0):
        self._session = HttpSession(base_url, timeout)
        self.resources = ResourcesGroup(self._session)
        self.channels = ChannelsGroup(self._session)
        self.modules = ModulesGroup(self._session)
        self.application = ApplicationGroup(self._session)
        self.media = MediaGroup(self._session)
        self.connection = ConnectionGroup(self._session)
        self.comm = CommGroup(self._session)
        self.numeric_results = NumericResultsGroup(self._session)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        """Close the underlying persistent HTTP connection."""
        self._session.close()

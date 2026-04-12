"""Main client for the AccordionQ2 REST API."""

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
        base = base_url.rstrip("/")
        self.resources = ResourcesGroup(base, timeout)
        self.channels = ChannelsGroup(base, timeout)
        self.modules = ModulesGroup(base, timeout)
        self.application = ApplicationGroup(base, timeout)
        self.media = MediaGroup(base, timeout)
        self.connection = ConnectionGroup(base, timeout)
        self.comm = CommGroup(base, timeout)
        self.numeric_results = NumericResultsGroup(base, timeout)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def close(self):
        """Close the client (no-op; provided for API symmetry)."""
        pass

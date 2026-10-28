"""Main client for the AccordionQ2 REST API."""

from __future__ import annotations

from ._base import HttpSession, _secret, _secret_headers
from .application import ApplicationGroup
from .audit import AuditGroup
from .calibration import CalibrationGroup
from .capabilities import CapabilitiesGroup
from .channels import ChannelsGroup
from .comm import CommGroup
from .connection import ConnectionGroup
from .events import EventsGroup
from .files import FilesGroup
from .firmware import FirmwareGroup
from .instruments import InstrumentsGroup
from .lease import LeaseGroup
from .media import MediaGroup
from .modules import ModulesGroup
from .numeric_results import NumericResultsGroup
from .resources import ResourcesGroup
from .subscriptions import SubscriptionsGroup
from .system import SystemGroup


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
                         system CA bundle.  A string is a path to a CA bundle file (e.g.
                         a site CA), used instead of the system's: the certificate must
                         chain to it, match the host name and be meant for TLS servers.
                         ``False`` disables verification; for a station's self-signed
                         certificate pin it with *cert_sha256* instead.
        default_headers: Additional HTTP headers merged into every request. An
                         ``X-Api-Key`` here is handled as *api_key* (taken as the key
                         when *api_key* is None, dropped when it is given).
        api_key:        The station API key (``acc_...``), sent as ``X-Api-Key`` with
                         every request, the event stream included. None sends none,
                         which a station in security mode ``Off`` or ``Report`` accepts.
                         Over ``http://`` the key crosses the network in clear text:
                         acceptable only on a trusted intranet segment.
        cert_sha256:     The SHA-256 fingerprint of the station's HTTPS certificate, as
                         hex with or without colons, spaces or dashes, in either case.
                         The client then accepts exactly that certificate, self-signed
                         or reached by IP address, and refuses any other before sending
                         anything. Needs an ``https://`` base URL.

    A station is meant for an intranet. Base URLs may be IPv6 literals in brackets,
    with a zone id as ``%eth0`` or ``%25eth0``: ``http://[fe80::1%eth0]:5000``.
    Bearer tokens are not supported: the station doesn't issue them yet.

    Raises:
        ValueError: The base URL, key or fingerprint is malformed, or *cert_sha256*
            is given for ``http://`` or together with a CA bundle in *verify*. The
            message never contains the key.

    Example::

        client = AccordionQ2Client(
            "https://station-12:5001",
            api_key=os.environ["ACCORDION_API_KEY"],
            cert_sha256="3F:A2:7C:...:9C",
        )
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        auth: tuple[str, str] | None = None,
        verify: bool | str = True,
        default_headers: dict[str, str] | None = None,
        *,
        api_key: str | None = None,
        cert_sha256: str | None = None,
    ) -> None:
        # So a traceback's locals show no key.
        api_key = _secret(api_key)
        default_headers = _secret_headers(default_headers)
        self._session = HttpSession(
            base_url,
            timeout,
            auth=auth,
            verify=verify,
            default_headers=default_headers,
            api_key=api_key,
            cert_sha256=cert_sha256,
        )
        self.resources = ResourcesGroup(self._session)
        self.channels = ChannelsGroup(self._session)
        self.modules = ModulesGroup(self._session)
        self.application = ApplicationGroup(self._session)
        self.media = MediaGroup(self._session)
        self.connection = ConnectionGroup(self._session)
        self.comm = CommGroup(self._session)
        self.numeric_results = NumericResultsGroup(self._session)
        self.calibration = CalibrationGroup(self._session)
        self.audit = AuditGroup(self._session)
        self.capabilities = CapabilitiesGroup(self._session)
        self.instruments = InstrumentsGroup(self._session)
        self.events = EventsGroup(self._session)
        self.subscriptions = SubscriptionsGroup(self._session)
        self.lease = LeaseGroup(self._session)
        self.system = SystemGroup(self._session)
        self.files = FilesGroup(self._session)
        self.firmware = FirmwareGroup(self._session)

    def __repr__(self) -> str:
        # getattr: a traceback may show a client whose __init__ raised.
        session = getattr(self, "_session", None)
        return f"AccordionQ2Client({'<not initialised>' if session is None else repr(session)})"

    def __enter__(self) -> AccordionQ2Client:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying persistent HTTP connection."""
        self._session.close()

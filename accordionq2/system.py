"""The station's services, reboot and clock (accordionq2 contract section 9)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from ._base import ApiGroupBase, HttpSession
from .boot import BootGroup


@dataclass(frozen=True, slots=True)
class ServiceStatus:
    """A service on the station: the hardware app, the WebApi or the dashboard."""

    #: ``hardware``, ``webapi`` or ``dashboard``.
    id: str
    #: The systemd unit, e.g. ``accordion.service``.
    unit: str
    description: str
    #: False when the Pi doesn't have the unit.
    installed: bool
    #: systemd's state: active, inactive, failed, activating, deactivating.
    active_state: str
    #: systemd's detail: running, dead, exited and so on.
    sub_state: str
    #: Starts at boot.
    enabled: bool
    #: When it last became active (ISO 8601), or None.
    since: str | None
    #: The WebApi answering, which can be restarted but not stopped through itself.
    self: bool
    #: What it can be asked for: start, stop, restart, enable, disable.
    actions: tuple[str, ...] = field(default=())

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ServiceStatus:
        return cls(
            id=d.get("id", ""),
            unit=d.get("unit", ""),
            description=d.get("description", ""),
            installed=bool(d.get("installed")),
            active_state=d.get("activeState", ""),
            sub_state=d.get("subState", ""),
            enabled=bool(d.get("enabled")),
            since=d.get("since"),
            self=bool(d.get("self")),
            actions=tuple(d.get("actions") or ()),
        )


@dataclass(frozen=True, slots=True)
class ClockStatus:
    """The station's clock."""

    #: The Pi's time when it answered (ISO 8601).
    utc: str
    time_zone: str
    ntp_enabled: bool
    #: A time server keeps the clock; setting it then needs ``force``.
    ntp_synchronized: bool

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ClockStatus:
        return cls(
            utc=d.get("utc", ""),
            time_zone=d.get("timeZone", ""),
            ntp_enabled=bool(d.get("ntpEnabled")),
            ntp_synchronized=bool(d.get("ntpSynchronized")),
        )


class SystemGroup(ApiGroupBase):
    """The station's services, reboot and clock; ``boot`` is its start-up configuration.

    Changes are writes: while another client holds the lease they raise 423.
    """

    def __init__(self, session: HttpSession) -> None:
        super().__init__(session)
        #: The hardware app's start-up configuration, boot.config (contract section 11).
        self.boot = BootGroup(session)

    def get_services(self) -> list[ServiceStatus]:
        """The hardware app, the WebApi and the dashboard, with their state."""
        data = self._get_json("api/system/services")
        assert isinstance(data, list)
        return [ServiceStatus.from_dict(s) for s in data]

    def service_action(self, service_id: str, action: str) -> None:
        """Start, stop or restart a service, or turn starting it at boot on or off.

        *action* is ``start``, ``stop``, ``restart``, ``enable`` or ``disable``. It
        doesn't wait for the job; follow :meth:`get_services`. Restarting the WebApi
        itself drops every client's connection for a few seconds.
        """
        self._post(f"api/system/services/{quote(service_id, safe='')}/{quote(action, safe='')}")

    def reboot(self) -> None:
        """Reboot the Pi a second after answering; it is back after about a minute."""
        self._post("api/system/reboot")

    def get_clock(self) -> ClockStatus:
        """The Pi's clock."""
        data = self._get_json("api/system/clock")
        assert isinstance(data, dict)
        return ClockStatus.from_dict(data)

    def set_clock(self, utc: datetime | None = None, force: bool = False) -> ClockStatus:
        """Set the Pi's clock, to this computer's when *utc* is None.

        A clock a time server keeps is refused (409) unless *force*. A naive
        *utc* is taken as UTC.
        """
        when = utc or datetime.now(UTC)
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        iso = when.astimezone(UTC).isoformat(timespec="milliseconds")
        data = self._put_json("api/system/clock", {"utc": iso, "force": force})
        assert isinstance(data, dict)
        return ClockStatus.from_dict(data)

"""The station's JTAG ports (firmware with stable module names).

A JTAG port is a JTAG TAP that a module owns the way to: MicroHAPS's FT4232H interface A
(``MicroHAPS.JTAG.A``), an FTDI cable of the JtagPorts module (``JTAG_FTDI.JTAG.A``). One holder at
a time: the owner itself (an FPGA image load, a power cycle), an XVC client (Vivado), or the Drummer
instance bound to it. Each port is two channels: ``<port>.State`` (Register, Unit ``jtag-port``, the
state as JSON) and ``<port>.Xvc`` (the XVC server's switch, Admin)::

    for p in client.jtag_ports.get_all():
        print(p.name, p.state.state if p.state else "?", p.state.bound if p.state else None)
    client.jtag_ports.set_xvc("MicroHAPS.JTAG.A", True)      # an Admin key
    client.drummer.target("Drummer").bind_port("MicroHAPS.JTAG.A")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, ClassVar

from ._base import ApiGroupBase, HttpSession
from .channels import ChannelsGroup
from .resources import ResourcesGroup


@dataclass(frozen=True, slots=True)
class JtagHolder:
    """Who holds a JTAG port."""

    #: ``"borrower"`` (a Drummer instance), ``"xvc"`` (an XVC client) or ``"owner"``.
    kind: str = ""
    #: The borrower's name, the XVC client's address, or the owner.
    name: str = ""
    #: What it does (``"an FPGA image load"``), or None.
    what: str | None = None
    #: When it took the port (ISO 8601), or None.
    since: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JtagHolder:
        return cls(
            kind=str(data.get("kind") or ""),
            name=str(data.get("name") or ""),
            what=data.get("what"),
            since=data.get("since"),
        )


@dataclass(frozen=True, slots=True)
class JtagXvc:
    """A JTAG port's XVC server."""

    #: The switch: the server listens.
    enabled: bool = False
    #: ``"drummer"`` (the station's own server) or ``"openfpgaloader"``.
    engine: str | None = None
    #: Where it listens: ``"0.0.0.0:2542"``.
    listen: str | None = None
    #: The client addresses or CIDR ranges served; empty: every client.
    allow: tuple[str, ...] = ()
    #: The connected client's address, or None.
    client: str | None = None
    #: A client waits for the port (its first shift is held).
    waiting: bool = False
    sessions: int = 0
    #: Why the last session ended.
    last_end: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JtagXvc:
        return cls(
            enabled=bool(data.get("enabled", False)),
            engine=data.get("engine"),
            listen=data.get("listen"),
            allow=tuple(str(a) for a in data.get("allow") or ()),
            client=data.get("client"),
            waiting=bool(data.get("waiting", False)),
            sessions=int(data.get("sessions") or 0),
            last_end=data.get("last_end"),
        )


@dataclass(frozen=True, slots=True)
class JtagPortState:
    """A JTAG port's state: the value of its ``<port>.State`` channel."""

    port: str = ""
    #: The module that owns it: ``"MicroHAPS"``.
    owner: str = ""
    #: What it opens: ``"FT4232H J020324 interface A"``.
    label: str = ""
    #: One more at every change; a value older than one you have is stale.
    seq: int = 0
    #: ``"free"``, ``"held"`` or ``"down"``.
    state: str = ""
    #: Who holds it; None when it is free or down.
    holder: JtagHolder | None = None
    #: Why it is down (the owner's reason), or None.
    why: str | None = None
    #: The Drummer instance bound to it, or None.
    bound: str | None = None
    #: The fastest TCK a holder gets, in Hz.
    max_tck_hz: float = 0.0
    xvc: JtagXvc = field(default_factory=JtagXvc)
    #: When the state last changed (ISO 8601), or None.
    since: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JtagPortState:
        holder = data.get("holder")
        xvc = data.get("xvc")
        return cls(
            port=str(data.get("port") or ""),
            owner=str(data.get("owner") or ""),
            label=str(data.get("label") or ""),
            seq=int(data.get("seq") or 0),
            state=str(data.get("state") or ""),
            holder=JtagHolder.from_dict(holder) if isinstance(holder, dict) else None,
            why=data.get("why"),
            bound=data.get("bound"),
            max_tck_hz=float(data.get("max_tck_hz") or 0.0),
            xvc=JtagXvc.from_dict(xvc) if isinstance(xvc, dict) else JtagXvc(),
            since=data.get("since"),
        )

    @classmethod
    def parse(cls, raw: str) -> JtagPortState | None:
        """The state in a State channel's value, or None when it is not the JSON expected."""
        if not raw or not raw.strip():
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return cls.from_dict(data) if isinstance(data, dict) else None


@dataclass(frozen=True, slots=True)
class JtagPort:
    """One JTAG port, with its state when it was read."""

    #: The port's name, the prefix of its two channels: ``"MicroHAPS.JTAG.A"``.
    name: str
    #: Its state; None when the State channel's value was not the JSON expected.
    state: JtagPortState | None = None
    #: The State channel's value as read.
    raw: str = ""

    @property
    def state_channel(self) -> str:
        return f"{self.name}.State"

    @property
    def xvc_channel(self) -> str:
        return f"{self.name}.Xvc"


def port_name(port: str) -> str:
    """``"MicroHAPS.JTAG.A"`` for itself and for its ``.State`` or ``.Xvc`` channel."""
    p = port.strip() if port else ""
    if not p:
        raise ValueError('give the port\'s name, e.g. "MicroHAPS.JTAG.A"')
    lower = p.lower()
    if lower.endswith(".state"):
        return p[: -len(".state")]
    if lower.endswith(".xvc"):
        return p[: -len(".xvc")]
    return p


class JtagPortsGroup(ApiGroupBase):
    """The station's JTAG ports (``client.jtag_ports``), found by their State channels."""

    #: The Unit of a port's State channel.
    STATE_UNIT: ClassVar[str] = "jtag-port"
    #: The Unit of a port's XVC switch.
    XVC_UNIT: ClassVar[str] = "jtag-port:xvc"

    def __init__(self, session: HttpSession) -> None:
        super().__init__(session)
        self._channels = ChannelsGroup(session)
        self._resources = ResourcesGroup(session)

    def get_all(self) -> list[JtagPort]:
        """Every JTAG port with its state read now, by name. Empty on firmware without ports."""
        states = sorted(
            (
                c.net_name
                for c in self._channels.get_all()
                if c.unit == self.STATE_UNIT and c.net_name.endswith(".State")
            ),
            key=str.lower,
        )
        if not states:
            return []
        values = self._resources.get_values(states)
        ports = []
        for n in states:
            raw = values.get(n, "")
            ports.append(JtagPort(n.removesuffix(".State"), JtagPortState.parse(raw), raw))
        return ports

    def get_state(self, port: str) -> JtagPortState | None:
        """One port's state now (*port* is its name or one of its channels' net names)."""
        return JtagPortState.parse(self._resources.get_value(f"{port_name(port)}.State"))

    def set_xvc(self, port: str, on: bool) -> None:
        """Switch the port's XVC server on or off (``<port>.Xvc``).

        Needs Admin (403 below it); 409 when the TCP port can't be bound. Switching it on takes
        nothing from a holder: a client takes the port at its first shift.
        """
        self._resources.set_value(f"{port_name(port)}.Xvc", "True" if on else "False")

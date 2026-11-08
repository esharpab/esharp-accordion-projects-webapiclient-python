"""Drummer modules: IEEE 1687 instruments in an FPGA over JTAG (Extensions/Drummer in the firmware).

Every instrument operation the station's Web UI has (arm the logic analyser, an I2C transfer,
set an MMCM output, start a memory test) is a transaction on the instrument's Call channel
(``Drummer.MEM.Call``) whose answer is the operation's result, so a script does exactly what
the page does::

    t = client.drummer.target("Drummer")
    r = t.call("CLK", "clock_measure", gate=1_200_000, channel=1)     # {count, hz, ms, seq}
    t.call("MEM", "mem_start", {"pattern": "PRBS31", "count": 65536})
    t.read("CLK.Freq0")                                                 # "233250000"
    t.write("GPIO.GPIO0", "True")
    t.bind_port("MicroHAPS.JTAG.A")                                     # Target.Port
    t.upload_package("build/microhaps_mem.drummer")                     # kept, selected, loaded
    t.library()["packages"]                                             # the station's library
    t.select_package("4f0c1a2b")                                        # back to a known-good build
    t.build()["text"]                                                   # which build the FPGA runs

Errors: 400 the request is wrong; **409 busy, try again** (something else holds the JTAG, named
in the message); 500 an instrument or JTAG fault. All are :class:`AccordionQ2ApiError` with
``status_code``. Needs firmware with the ``resources.transact`` capability.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from os import PathLike
from typing import Any, ClassVar

from ._base import ApiGroupBase, HttpSession
from .capabilities import CapabilitiesDto, CapabilitiesGroup
from .channels import ByteStreamStatus, ChannelsGroup
from .exceptions import AccordionQ2ApiError, AccordionQ2NotSupportedError
from .instruments import InstrumentsGroup
from .resources import ResourcesGroup

#: The instrument type a Drummer module reports (an Instrument channel named "{prefix}.Drummer").
INSTRUMENT_TYPE = "Drummer"


@dataclass(frozen=True, slots=True)
class DrummerModuleRef:
    """A Drummer module found on the station."""

    #: The net name prefix of its channels, the instance's configured name: ``"Drummer"``.
    prefix: str
    #: Its instrument's name, or the prefix.
    name: str


def segment(instrument: str) -> str:
    """``"MEM"`` for ``"MEM"`` and ``"SIB_MEM"``: the leading ``SIB_`` is dropped."""
    s = instrument.strip()
    if s.startswith("SIB_"):
        s = s[4:]
    if not s:
        raise ValueError('give an instrument: a segment ("MEM") or a SIB ("SIB_MEM")')
    return s


class _TransactCheck:
    """Whether the station has ``resources.transact``; asked once a minute and again after a
    failed call (the station may restart into older firmware)."""

    LIFETIME_S: ClassVar[float] = 60.0

    def __init__(self, capabilities: CapabilitiesGroup) -> None:
        self._capabilities = capabilities
        self._checked_at: float | None = None
        self._clock: Callable[[], float] = time.monotonic

    def ensure(self) -> None:
        at = self._checked_at
        if at is not None and self._clock() - at < self.LIFETIME_S:
            return
        self._checked_at = None
        if not self._capabilities.get().has(CapabilitiesDto.RESOURCES_TRANSACT):
            raise AccordionQ2NotSupportedError(
                CapabilitiesDto.RESOURCES_TRANSACT,
                "this station's firmware runs transactions for Admin only, under the engine lock "
                f"(no feature {CapabilitiesDto.RESOURCES_TRANSACT!r}): update it to run Drummer "
                "operations; nothing was sent",
            )
        self._checked_at = self._clock()

    def forget(self) -> None:
        self._checked_at = None


class DrummerTarget:
    """One Drummer module: its Target channels, its instruments' operations and channels.

    An instrument is named by its segment or its SIB (``"MEM"`` or ``"SIB_MEM"``). An
    operation's name and arguments are the Python console's (``web.py``); the answer is its
    result with ``ms`` (time in the module) and ``seq`` (the module's TAP hold number) added.
    Reads need Viewer, operations and writes Operator. Every operation is one line in the
    station's audit log, so poll with :meth:`snapshot` or :meth:`read`, not with operations.
    """

    #: How long one request waits in the module before it answers with a job.
    WAIT_MS: ClassVar[int] = 10_000
    #: The overall timeout of :meth:`call` when none is given, in seconds.
    DEFAULT_TIMEOUT_S: ClassVar[float] = 60.0

    def __init__(
        self,
        prefix: str,
        resources: ResourcesGroup,
        check: _TransactCheck,
        channels: ChannelsGroup | None = None,
    ) -> None:
        self.prefix = prefix
        self._resources = resources
        self._check = check
        self._channels = channels
        self._clock: Callable[[], float] = time.monotonic

    def __repr__(self) -> str:
        return f"DrummerTarget({self.prefix!r})"

    def net(self, name: str) -> str:
        """The full net name of a channel below the module: ``"Drummer." + name``."""
        return f"{self.prefix}.{name}"

    # -- channels -------------------------------------------------------------------------------
    def read(self, name: str) -> str:
        """A field or semantic channel below the module (``"GPIO.GPIO8"``, ``"CLK.Freq0"``).

        A semantic read may scan: the firmware's drummer.md says what each costs.
        """
        return self._resources.get_value(self.net(name))

    def write(self, name: str, value: str) -> None:
        """Write a field or semantic channel below the module (``"GPIO.GPIO0"``, ``"True"``).

        409 when the JTAG stays busy for 250 ms.
        """
        self._resources.set_value(self.net(name), value)

    def port(self) -> str:
        """The JTAG port the instance is bound to now (``Target.Port``, firmware with stable module
        names): ``"MicroHAPS.JTAG.A"``, or ``""`` when it is unbound."""
        return self.read("Target.Port").strip()

    def bind_port(self, port: str | None) -> None:
        """Bind the instance to a JTAG port now (``Target.Port``), giving back the one it held;
        ``""`` or None unbinds.

        409 when another instance claims the port (the message names it), or while a bitfile
        load, the self-test or a job holds the TAP. Not saved: the module's ``Port`` setting stays
        the binding at its next load. The station's ports are ``client.jtag_ports.get_all()``.
        """
        self.write("Target.Port", (port or "").strip())

    # -- the package library and build identity (the firmware's Drummer/PACKAGES.md) -----------------
    def library(self) -> dict[str, Any]:
        """``Target.Library``: the station's package library and this instance's selection, from the
        module's memory (no scan): ``dir``, ``bytes``, ``free_bytes``, ``floor_bytes``, ``selection``
        (``source`` "library", "PackagePath" or "none") and ``packages``, newest upload first.

        404 on firmware without the library.
        """
        return self._object("Target.Library")

    def select_package(self, sha256: str) -> None:
        """Select a library package for this instance (``Target.Select``, Operator): its SHA-256 or 8
        or more of its first hex digits.

        Kept across restarts. The design's channels are built again, and under the module's
        ``LoadOnSelect`` (default ``mismatch``) its bitfile is loaded when the FPGA does not run that
        build or the station can't tell. Returns before the connect: follow :meth:`status` and
        ``Target.LoadStatus``. 400 for an unknown or ambiguous one or a package that does not load
        (the old selection stays); 409 while a bitfile load or the self-test runs or the JTAG is
        held. :class:`ValueError` (nothing sent) unless it is 8 to 64 hex digits.
        """
        self.write("Target.Select", _sha_text(sha256))

    def unselect_package(self) -> None:
        """Unselect (``Target.Select`` = ``""``): the instance falls back to its ``PackagePath`` setting
        (under ``LoadOnSelect``), or to no package (the design's channels go, nothing is loaded)."""
        self.write("Target.Select", "")

    def delete_package(self, sha256: str) -> None:
        """Delete a package from the station's library (``Target.Delete``, Operator).

        409 while a configured instance selects it (the message names the instances); 400 for an
        unknown or ambiguous one. It can't be undone: upload the file again.
        :class:`ValueError` (nothing sent) unless it is 8 to 64 hex digits.
        """
        self.write("Target.Delete", _sha_text(sha256))

    def upload_package(self, path: str | PathLike[str], timeout: float = 60.0) -> ByteStreamStatus:
        """Upload a ``.drummer`` package to this instance (``Target.Package``, the developer flow).

        The station checks it, keeps it in its library, selects it and, under ``LoadOnSelect``
        ``mismatch``, loads its bitfile when the FPGA does not run that build, then discovers and
        connects. Returns when the package is kept and selected (state ``done``) or refused
        (``failed``, returned, not raised, with the reason in ``message``); the connect and any load
        follow: :meth:`status`, :meth:`build`, ``Target.LoadStatus``. :class:`TimeoutError` after
        *timeout* seconds.
        """
        if self._channels is None:
            raise RuntimeError("this DrummerTarget was not made by client.drummer.target(prefix)")
        channel = self.net("Target.Package")
        self._channels.upload_bytestream(channel, path)
        return self._channels.wait_bytestream(channel, timeout=timeout)

    def build(self) -> dict[str, Any] | None:
        """``Target.Status``'s ``build``: which build the FPGA runs and which the selected package has,
        and which rule decided (``fpga``, ``package``, ``marker``, ``held_back``, ``runs_package`` True,
        False or None, ``rule``, ``text``, ``checked``, ``stale``). None on firmware without build
        identity."""
        value = self.status().get("build")
        return value if isinstance(value, dict) else None

    def _json(self, name: str) -> object:
        text = self.read(name)
        try:
            return json.loads(text) if text.strip() else None
        except json.JSONDecodeError as error:
            raise AccordionQ2ApiError(200, f"{name} did not answer JSON: {error}") from None

    def status(self) -> dict[str, Any]:
        """``Target.Status``: connected, the design, the error."""
        return self._object("Target.Status")

    def info(self) -> dict[str, Any]:
        """``Target.Info``: the design, the chain, every instrument with its register map and tool
        facts. No scan."""
        return self._object("Target.Info")

    def attention(self) -> dict[str, Any]:
        """``Target.Attention``: the ATTN word, the instruments asking for attention and why. A read
        keeps the module's ATTN poll going for 2 s."""
        return self._object("Target.Attention")

    def jobs(self) -> list[dict[str, Any]]:
        """``Target.Jobs``: running jobs and ended ones not fetched yet."""
        value = self._json("Target.Jobs")
        return list(value) if isinstance(value, list) else []

    def snapshot(self, instrument: str) -> dict[str, Any]:
        """The instrument's Snapshot channel: its fields, status and why it asks for attention.

        While something else holds the JTAG it answers the last capture with ``stale`` and
        ``age_ms``; ``fields`` is None before a first read.
        """
        return self._object(f"{segment(instrument)}.Snapshot")

    def _object(self, name: str) -> dict[str, Any]:
        value = self._json(name)
        if not isinstance(value, dict):
            raise AccordionQ2ApiError(200, f"{name} did not answer a JSON object: {value!r}")
        return value

    # -- operations -----------------------------------------------------------------------------
    def call(
        self,
        instrument: str,
        name: str,
        args: Mapping[str, object] | None = None,
        /,
        *,
        timeout_s: float = 60.0,
        **kwargs: object,
    ) -> dict[str, Any]:
        """Run operation *name* on the instrument's Call channel and return its result.

        The arguments are *args* and the keyword arguments (``op``, ``name`` and ``sib`` pass
        as any other: this method's own parameters are positional). A job (an operation still
        holding the JTAG 10 s after it arrived) is followed with ``{"call": "job"}`` until it
        has ended; after *timeout_s* a :class:`TimeoutError` names the job's id, and the job
        goes on in the module (its result can be fetched for 5 minutes after it ends).

        Raises :class:`AccordionQ2NotSupportedError` when the station lacks
        ``resources.transact`` (nothing is sent), and :class:`AccordionQ2ApiError` with
        ``status_code`` 400 (the request is wrong), 409 (busy, try again) or 500 (a fault).
        """
        return self._run(f"{segment(instrument)}.Call", name, args, timeout_s, kwargs)

    def module_call(
        self,
        name: str,
        args: Mapping[str, object] | None = None,
        /,
        *,
        timeout_s: float = 60.0,
        **kwargs: object,
    ) -> dict[str, Any]:
        """A module operation on ``Target.Call`` (``attention``, ``attention_detail``,
        ``la_group_*``), or an instrument's with ``sib`` given. Otherwise as :meth:`call`."""
        return self._run("Target.Call", name, args, timeout_s, kwargs)

    def _run(
        self,
        channel: str,
        name: str,
        args: Mapping[str, object] | None,
        timeout_s: float,
        kwargs: Mapping[str, object],
    ) -> dict[str, Any]:
        if not name or not name.strip():
            raise ValueError("give the operation's name")
        body: dict[str, object] = {"call": name}
        for given in (args or {}, kwargs):
            for key, value in given.items():
                if key in ("call", "job"):
                    raise ValueError(f"{key!r} is not an operation argument")
                body[key] = value
        body.setdefault("wait_ms", self.WAIT_MS)
        self._check.ensure()
        net = self.net(channel)
        start = self._clock()
        result = self._transact(net, body)
        while (job := _running_job(result)) is not None:
            left = timeout_s - (self._clock() - start)
            if left <= 0:
                raise TimeoutError(
                    f"{name} on {channel.removesuffix('.Call')} still runs as job {job} after "
                    f"{timeout_s:g} s; it goes on in the module. Its result: a transaction "
                    f'{{"call": "job", "job": "{job}"}} on {net}, within 5 minutes of its end'
                )
            follow: dict[str, object] = {
                "call": "job",
                "job": job,
                "wait_ms": int(min(self.WAIT_MS, left * 1000)),
            }
            result = self._transact(net, follow)
        return result

    def _transact(self, net: str, body: Mapping[str, object]) -> dict[str, Any]:
        try:
            text = self._resources.transact(net, json.dumps(body))
        except Exception:
            self._check.forget()
            raise
        try:
            value = json.loads(text)
        except json.JSONDecodeError as error:
            raise AccordionQ2ApiError(200, f"{net} did not answer JSON: {error}") from None
        if not isinstance(value, dict):
            raise AccordionQ2ApiError(200, f"{net} did not answer a JSON object: {value!r}")
        return value


_SHA_TEXT = re.compile(r"[0-9a-fA-F]{8,64}")


def _sha_text(sha256: str) -> str:
    """A SHA-256 or 8+ of its first hex digits, as Target.Select and Target.Delete take it."""
    s = (sha256 or "").strip()
    if not _SHA_TEXT.fullmatch(s):
        raise ValueError(
            f"{s!r} is not a SHA-256: give the package's SHA-256 or 8 or more of its first hex digits"
        )
    return s


def _running_job(result: dict[str, Any]) -> str | None:
    """A running job's id: ``{"job": id, "state": "running", ...}``; else None."""
    job = result.get("job")
    if isinstance(job, str) and job and result.get("state") == "running":
        return job
    return None


class DrummerGroup(ApiGroupBase):
    """The Drummer modules on the station (``client.drummer``)."""

    def __init__(self, session: HttpSession) -> None:
        super().__init__(session)
        self._resources = ResourcesGroup(session)
        self._instruments = InstrumentsGroup(session)
        self._channels = ChannelsGroup(session)
        self._check = _TransactCheck(CapabilitiesGroup(session))

    def find(self) -> list[DrummerModuleRef]:
        """The Drummer modules: one per Instrument of type ``Drummer``, else one per
        ``Target.Status`` with a ``Target.Package`` beside it, as the Web UI finds them."""
        found: list[DrummerModuleRef] = []
        seen: set[str] = set()
        try:
            instruments = self._instruments.get_all()
        except AccordionQ2ApiError as error:
            if error.status_code != 404:
                raise
            instruments = []
        for i in instruments:
            if i.type != INSTRUMENT_TYPE or "." not in i.net_name:
                continue
            prefix = i.net_name.rsplit(".", 1)[0]
            if prefix and prefix not in seen:
                seen.add(prefix)
                found.append(DrummerModuleRef(prefix, i.instrument_name or prefix))
        if found:
            return found
        names = set(self._resources.get_names())
        status = ".Target.Status"
        for name in sorted(n for n in names if n.endswith(status)):
            prefix = name.removesuffix(status)
            if f"{prefix}.Target.Package" in names and prefix not in seen:
                seen.add(prefix)
                found.append(DrummerModuleRef(prefix, prefix))
        return found

    def target(self, prefix: str) -> DrummerTarget:
        """The instance named *prefix* (``"Drummer"``). Makes no request."""
        p = prefix.strip().rstrip(".")
        if not p:
            raise ValueError('give the module\'s prefix, e.g. "Drummer"')
        return DrummerTarget(p, self._resources, self._check, self._channels)

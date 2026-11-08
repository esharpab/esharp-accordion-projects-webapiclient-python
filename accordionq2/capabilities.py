"""What the WebApi supports (accordionq2 contract section 2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from ._base import ApiGroupBase
from .exceptions import AccordionQ2ApiError


@dataclass(frozen=True, slots=True)
class NamesCapability:
    """The ``names`` of ``api/capabilities``: stable module names and the old names' map.

    With :attr:`stable`, a software module's net names start with its configured name
    (``MicroHAPS.HCI.Scan``) instead of a load-order number (``1.MicroHAPS.HCI.Scan``).
    """

    stable: bool = False
    #: The station still accepts an old name in a request (with a warning line and the header
    #: ``X-Accordion-Old-Names``).
    old_names_accepted: bool = False
    #: Old prefixes (without their number) and what they are now:
    #: ``{"MicroHAPS_PMBUS_LTPP": "MicroHAPS.MicroHAPS_PMBUS_LTPP"}``.
    legacy_prefixes: dict[str, str] = field(default_factory=dict)
    #: Each loaded software module's load position and its name: ``{5: "ModuleForwarder"}``.
    legacy_positions: dict[int, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NamesCapability:
        legacy = data.get("legacy") or {}
        positions: dict[int, str] = {}
        for key, value in (legacy.get("positions") or {}).items():
            try:
                positions[int(key)] = str(value)
            except (TypeError, ValueError):
                continue
        return cls(
            stable=bool(data.get("stable", False)),
            old_names_accepted=bool(data.get("oldNamesAccepted", False)),
            legacy_prefixes={str(k): str(v) for k, v in (legacy.get("prefixes") or {}).items()},
            legacy_positions=positions,
        )


@dataclass(frozen=True, slots=True)
class CapabilitiesDto:
    """The WebApi's contract version, build version, codec version, features and security mode.

    Decide by :attr:`features`, not by version numbers.
    """

    #: Feature: the encoded channel calls work (the .NET client has them; this one doesn't yet).
    CHANNELS_ENCODED: ClassVar[str] = "channels.encoded"
    #: Feature: the event stream (``client.events.open()``) works.
    EVENTS: ClassVar[str] = "events"
    #: Feature: the station checks API keys (``X-Api-Key``) as :attr:`security_mode` says.
    SECURITY_API_KEY: ClassVar[str] = "security.apikey"
    #: Feature: ``values/get`` takes ``cacheOnly`` (``client.resources.read_cached()``). A WebApi
    #: without it ignores the field and reads the hardware.
    VALUES_CACHE_ONLY: ClassVar[str] = "values.cacheOnly"
    #: Feature: ``resources/transact`` works on any channel for Operator (Admin on bus channels),
    #: its answer is not cached, and a busy target answers 409. The Drummer operations need it
    #: (``client.drummer``); older firmware runs transactions for Admin only, under the engine lock.
    RESOURCES_TRANSACT: ClassVar[str] = "resources.transact"

    #: The contract version; 0 for a WebApi that predates it.
    api_version: int = 0
    #: The WebApi build's informational version, e.g. ``"7.0.0"``; empty when unknown.
    webapi_version: str = ""
    #: The server's channel codec version; 0 when unknown.
    codec_version: int = 0
    #: The supported features.
    features: tuple[str, ...] = ()
    #: ``"Off"``, ``"Report"`` or ``"On"``: how the station treats a request without a valid
    #: API key. ``"Off"`` from a WebApi that predates it. A str, so a later mode doesn't break.
    security_mode: str = "Off"
    #: Stable module names and the old names' map; None from a WebApi before them.
    names: NamesCapability | None = None

    def has(self, feature: str) -> bool:
        """Whether the WebApi has *feature*, e.g. :attr:`EVENTS`."""
        return feature in self.features

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CapabilitiesDto:
        return cls(
            api_version=int(data.get("apiVersion", 0)),
            webapi_version=str(data.get("webApiVersion") or ""),
            codec_version=int(data.get("codecVersion", 0)),
            features=tuple(str(f) for f in data.get("features") or ()),
            security_mode=str(data.get("securityMode") or "Off"),
            names=NamesCapability.from_dict(names)
            if isinstance(names := data.get("names"), dict)
            else None,
        )


class CapabilitiesGroup(ApiGroupBase):
    """What the WebApi supports. Needs no API key, so it tells a client whether it needs one."""

    def get(self) -> CapabilitiesDto:
        """The WebApi's capabilities; ``CapabilitiesDto()`` for a WebApi that predates them (404).

        Answers while the hardware app is disconnected too.
        """
        try:
            result = self._get_json("api/capabilities")
        except AccordionQ2ApiError as error:
            if error.status_code == 404:
                return CapabilitiesDto()
            raise
        assert isinstance(result, dict)
        return CapabilitiesDto.from_dict(result)

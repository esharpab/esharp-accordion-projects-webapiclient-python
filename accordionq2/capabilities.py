"""What the WebApi supports (accordionq2 contract section 2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from ._base import ApiGroupBase
from .exceptions import AccordionQ2ApiError


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

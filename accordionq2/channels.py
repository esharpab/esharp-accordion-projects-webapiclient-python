"""Channel query and configuration operations."""

from __future__ import annotations

from ._base import ApiGroupBase
from .models import ChannelConfigRequest, ChannelDto, ChannelLookupRequest


class ChannelsGroup(ApiGroupBase):
    """Operations for querying and configuring hardware channels."""

    def get_all(self) -> list[ChannelDto]:
        """Return all configured channels."""
        data = self._get_json("api/channels")
        assert isinstance(data, list)
        return [ChannelDto.from_dict(ch) for ch in data]

    def get_channel(self, alias: str | None = None, net_name: str | None = None) -> ChannelDto:
        """Look up a single channel by alias or net name.

        At least one of *alias* or *net_name* must be provided.
        """
        body = ChannelLookupRequest(alias=alias, net_name=net_name).to_dict()
        result = self._post_json("api/channels/channel", body)
        assert isinstance(result, dict)
        return ChannelDto.from_dict(result)

    def configure(self, config: ChannelConfigRequest) -> None:
        """Apply a partial update to a single channel.

        *config* is a :class:`~accordionq2.models.ChannelConfigRequest`.
        Only non-``None`` fields are applied.
        """
        self._post("api/channels/channel/configure", config.to_dict())

    def configure_many(self, configs: list[ChannelConfigRequest]) -> None:
        """Apply partial updates to multiple channels in one round-trip.

        *configs* is a list of
        :class:`~accordionq2.models.ChannelConfigRequest` objects.
        """
        self._post("api/channels/configure", [c.to_dict() for c in configs])

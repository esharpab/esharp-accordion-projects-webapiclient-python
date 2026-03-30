"""Channel query and configuration operations."""

from ._base import ApiGroupBase
from .models import ChannelConfigRequest, ChannelDto


class ChannelsGroup(ApiGroupBase):
    """Operations for querying and configuring hardware channels."""

    def get_all(self):
        """Return all configured channels."""
        data = self._get_json("api/channels")
        return [ChannelDto.from_dict(ch) for ch in data]

    def get_channel(self, alias=None, net_name=None):
        """Look up a single channel by alias or net name.

        At least one of *alias* or *net_name* must be provided.
        """
        body = {}
        if alias is not None:
            body["Alias"] = alias
        if net_name is not None:
            body["NetName"] = net_name
        return ChannelDto.from_dict(self._post_json("api/channels/channel", body))

    def configure(self, config):
        """Apply a partial update to a single channel.

        *config* is a :class:`~accordionq2.models.ChannelConfigRequest`.
        Only non-``None`` fields are applied.
        """
        self._post("api/channels/channel/configure", config.to_dict())

    def configure_many(self, configs):
        """Apply partial updates to multiple channels in one round-trip.

        *configs* is a list of
        :class:`~accordionq2.models.ChannelConfigRequest` objects.
        """
        self._post("api/channels/configure", [c.to_dict() for c in configs])

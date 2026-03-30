"""Connection status operations."""

from ._base import ApiGroupBase
from .models import ConnectionStatusDto


class ConnectionGroup(ApiGroupBase):
    """Operations for querying the API's connection status."""

    def get_status(self):
        """Return the current connection status."""
        return ConnectionStatusDto.from_dict(
            self._get_json("api/connection/status")
        )

"""Connection status operations."""

from __future__ import annotations

from ._base import ApiGroupBase
from .models import ConnectionStatusDto


class ConnectionGroup(ApiGroupBase):
    """Operations for querying the API's connection status."""

    def get_status(self) -> ConnectionStatusDto:
        """Return the current connection status."""
        result = self._get_json("api/connection/status")
        assert isinstance(result, dict)
        return ConnectionStatusDto.from_dict(result)

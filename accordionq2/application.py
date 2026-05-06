"""Application lifecycle operations."""

from __future__ import annotations

from urllib.parse import quote

from ._base import ApiGroupBase
from .enums import ModuleStatus


class ApplicationGroup(ApiGroupBase):
    """Application lifecycle, status, and configuration file management."""

    def get_name(self) -> str:
        """Return the application module name."""
        result = self._get_json("api/application/name")
        assert isinstance(result, str)
        return result

    def get_identification(self) -> str:
        """Return the application identification string."""
        result = self._get_json("api/application/identification")
        assert isinstance(result, str)
        return result

    def get_status(self) -> ModuleStatus:
        """Return the current application module status."""
        return ModuleStatus(self._get_json("api/application/status"))

    def reset(self) -> None:
        """Send a reset command to the application engine."""
        self._post("api/application/reset")

    def list_config_files(self) -> list[str]:
        """List all configuration files available on the device."""
        result = self._get_json("api/application/config/list")
        assert isinstance(result, list)
        return result

    def get_loaded_config_files(self) -> list[str]:
        """Return the names of currently loaded configuration files."""
        result = self._get_json("api/application/config/loaded")
        assert isinstance(result, list)
        return result

    def load_config_file(self, file_name: str) -> None:
        """Load a configuration file by name."""
        self._post("api/application/config/load", {"FileName": file_name})

    def save_config_file(self, file_name: str) -> None:
        """Save the current configuration to a named file on the device."""
        self._post("api/application/config/save", {"FileName": file_name})

    def download_config_file(self, file_name: str) -> bytes:
        """Download a configuration file as raw bytes."""
        return self._get_bytes(
            "api/application/config/download/{}".format(quote(file_name, safe=""))
        )

    def upload_config_file(self, file_name: str, data: bytes) -> None:
        """Upload a configuration file to the device."""
        self._post_multipart("api/application/config/upload", file_name, data)

    def delete_config_file(self, file_name: str) -> None:
        """Delete a configuration file from the device."""
        self._delete(
            "api/application/config/{}".format(quote(file_name, safe=""))
        )

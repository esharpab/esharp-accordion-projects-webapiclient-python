"""Application lifecycle operations."""

from urllib.parse import quote

from ._base import ApiGroupBase
from .enums import ModuleStatus


class ApplicationGroup(ApiGroupBase):
    """Application lifecycle, status, and configuration file management."""

    def get_name(self):
        """Return the application module name."""
        return self._get_json("api/application/name")

    def get_identification(self):
        """Return the application identification string."""
        return self._get_json("api/application/identification")

    def get_status(self):
        """Return the current application module status."""
        return ModuleStatus(self._get_json("api/application/status"))

    def reset(self):
        """Send a reset command to the application engine."""
        self._post("api/application/reset")

    def list_config_files(self):
        """List all configuration files available on the device."""
        return self._get_json("api/application/config/list")

    def get_loaded_config_files(self):
        """Return the names of currently loaded configuration files."""
        return self._get_json("api/application/config/loaded")

    def load_config_file(self, file_name):
        """Load a configuration file by name."""
        self._post("api/application/config/load", {"FileName": file_name})

    def save_config_file(self, file_name):
        """Save the current configuration to a named file on the device."""
        self._post("api/application/config/save", {"FileName": file_name})

    def download_config_file(self, file_name):
        """Download a configuration file as raw bytes."""
        return self._get_bytes(
            "api/application/config/download/{}".format(quote(file_name, safe=""))
        )

    def upload_config_file(self, file_name, data):
        """Upload a configuration file to the device."""
        self._post_multipart("api/application/config/upload", file_name, data)

    def delete_config_file(self, file_name):
        """Delete a configuration file from the device."""
        self._delete(
            "api/application/config/{}".format(quote(file_name, safe=""))
        )

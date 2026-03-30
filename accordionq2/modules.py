"""Module management operations."""

from ._base import ApiGroupBase
from .models import AppLicenseDto, ModuleSettingsDto, PhysicalSystemDto


class ModulesGroup(ApiGroupBase):
    """Operations for managing hardware and software modules."""

    def get_all(self):
        """Return all available modules (loaded and unloaded)."""
        data = self._get_json("api/modules")
        return [ModuleSettingsDto.from_dict(m) for m in data]

    def get_loaded(self):
        """Return currently loaded modules only."""
        data = self._get_json("api/modules/loaded")
        return [ModuleSettingsDto.from_dict(m) for m in data]

    def load(self, module):
        """Load a module."""
        self._post("api/modules/load", module.to_dict())

    def unload(self, module):
        """Unload a module."""
        self._post("api/modules/unload", module.to_dict())

    def configure(self, module):
        """Configure a module."""
        self._post("api/modules/configure", module.to_dict())

    def get_physical_system(self):
        """Return the physical system description (hardware topology)."""
        return PhysicalSystemDto.from_dict(
            self._get_json("api/modules/physical-system")
        )

    def get_licensed_apps(self):
        """Return licensed applications only."""
        data = self._get_json("api/modules/apps/licensed")
        return [AppLicenseDto.from_dict(a) for a in data]

    def get_all_apps(self):
        """Return all applications (licensed and unlicensed)."""
        data = self._get_json("api/modules/apps")
        return [AppLicenseDto.from_dict(a) for a in data]

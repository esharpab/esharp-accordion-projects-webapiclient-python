"""Module management operations."""

from __future__ import annotations

from ._base import ApiGroupBase
from .models import AppLicenseDto, ModuleSettingsDto, PhysicalSystemDto


class ModulesGroup(ApiGroupBase):
    """Operations for managing hardware and software modules."""

    def get_all(self) -> list[ModuleSettingsDto]:
        """Return all available modules (loaded and unloaded)."""
        data = self._get_json("api/modules")
        assert isinstance(data, list)
        return [ModuleSettingsDto.from_dict(m) for m in data]

    def get_loaded(self) -> list[ModuleSettingsDto]:
        """Return currently loaded modules only."""
        data = self._get_json("api/modules/loaded")
        assert isinstance(data, list)
        return [ModuleSettingsDto.from_dict(m) for m in data]

    def load(self, module: ModuleSettingsDto) -> None:
        """Load a module."""
        self._post("api/modules/load", module.to_dict())

    def unload(self, module: ModuleSettingsDto) -> None:
        """Unload a module."""
        self._post("api/modules/unload", module.to_dict())

    def configure(self, module: ModuleSettingsDto) -> None:
        """Configure a module."""
        self._post("api/modules/configure", module.to_dict())

    def get_physical_system(self) -> PhysicalSystemDto:
        """Return the physical system description (hardware topology)."""
        result = self._get_json("api/modules/physical-system")
        assert isinstance(result, dict)
        return PhysicalSystemDto.from_dict(result)

    def get_licensed_apps(self) -> list[AppLicenseDto]:
        """Return licensed applications only."""
        data = self._get_json("api/modules/apps/licensed")
        assert isinstance(data, list)
        return [AppLicenseDto.from_dict(a) for a in data]

    def get_all_apps(self) -> list[AppLicenseDto]:
        """Return all applications (licensed and unlicensed)."""
        data = self._get_json("api/modules/apps")
        assert isinstance(data, list)
        return [AppLicenseDto.from_dict(a) for a in data]

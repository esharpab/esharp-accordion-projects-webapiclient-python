"""The hardware app's start-up configuration, boot.config (accordionq2 contract section 11)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ._base import ApiGroupBase


@dataclass(frozen=True, slots=True)
class BootAliasFile:
    """An alias file the hardware app loads at start-up, in ``order``."""

    #: A file name in the alias folder, e.g. ``station.csv``.
    path: str
    enabled: bool = True
    order: int = 0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BootAliasFile:
        return cls(d.get("path", ""), bool(d.get("enabled")), int(d.get("order") or 0))


@dataclass(frozen=True, slots=True)
class BootModule:
    """A module the hardware app loads at start-up."""

    name: str
    assembly_path: str = ""
    class_name: str = ""
    #: Empty when sent: taken from ``class_name``.
    namespace: str = ""
    enabled: bool = False

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BootModule:
        return cls(
            d.get("name", ""),
            d.get("assemblyPath", ""),
            d.get("className", ""),
            d.get("namespace", ""),
            bool(d.get("enabled")),
        )


@dataclass(frozen=True, slots=True)
class BootAddress:
    """A static IPv4 address given to an interface beside DHCP, e.g. ``192.168.0.222/24``."""

    interface: str
    static_ip: str = ""
    enabled: bool = False

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BootAddress:
        return cls(d.get("interface", ""), d.get("staticIp", ""), bool(d.get("enabled")))


@dataclass(frozen=True, slots=True)
class BootService:
    """A service applied at every start, even with boot.config off.

    One marked on is enabled and started; one marked off is stopped and disabled.
    """

    name: str
    #: The systemd unit, with or without ``.service``.
    service_file: str
    enabled: bool = True

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BootService:
        return cls(d.get("name", ""), d.get("serviceFile", ""), bool(d.get("enabled")))


@dataclass(frozen=True, slots=True)
class BootWifi:
    """The Wi-Fi set at start-up. The password is never returned, only whether there is one."""

    enabled: bool
    ssid: str
    password_set: bool

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BootWifi:
        return cls(bool(d.get("enabled")), d.get("ssid", ""), bool(d.get("passwordSet")))


@dataclass(frozen=True, slots=True)
class BootConfig:
    """boot.config as the station shows it. With ``enabled`` False only ``services`` apply."""

    enabled: bool
    #: When the file was last written (ISO 8601); pass it back as ``if_modified``.
    modified: str
    description: str | None
    wifi: BootWifi
    disable_usb_ports: bool
    enable_media_devices: bool
    #: Loaded after the engine starts, and on every reset, in this order.
    alias_files: tuple[BootAliasFile, ...] = field(default=())
    modules: tuple[BootModule, ...] = field(default=())
    ip_configurations: tuple[BootAddress, ...] = field(default=())
    services: tuple[BootService, ...] = field(default=())
    #: Units that can't be turned off here: the hardware app's and the WebApi's.
    protected_services: tuple[str, ...] = field(default=())

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BootConfig:
        return cls(
            enabled=bool(d.get("enabled")),
            modified=d.get("modified", ""),
            description=d.get("description"),
            wifi=BootWifi.from_dict(d.get("wifi") or {}),
            disable_usb_ports=bool(d.get("disableUsbPorts")),
            enable_media_devices=bool(d.get("enableMediaDevices")),
            alias_files=tuple(BootAliasFile.from_dict(a) for a in d.get("aliasFiles") or ()),
            modules=tuple(BootModule.from_dict(m) for m in d.get("modules") or ()),
            ip_configurations=tuple(
                BootAddress.from_dict(i) for i in d.get("ipConfigurations") or ()
            ),
            services=tuple(BootService.from_dict(s) for s in d.get("services") or ()),
            protected_services=tuple(d.get("protectedServices") or ()),
        )


# Tells "leave the Wi-Fi password alone" (the default) apart from None.
_KEEP: Any = object()


def _alias_files(files: list[BootAliasFile]) -> list[dict[str, Any]]:
    return [{"path": a.path, "enabled": a.enabled} for a in files]


class BootGroup(ApiGroupBase):
    """The hardware app's start-up configuration, boot.config.

    Changes take effect at the hardware app's next start (the alias files and modules also on a
    reset), not at once. They are writes: while another client holds the lease they raise 423.
    """

    def get(self) -> BootConfig:
        """boot.config, without the Wi-Fi password. 404 when the Pi has none yet."""
        data = self._get_json("api/system/boot")
        assert isinstance(data, dict)
        return BootConfig.from_dict(data)

    def set_startup(
        self, enabled: bool | None = None, alias_files: list[BootAliasFile] | None = None
    ) -> BootConfig:
        """Turn applying boot.config on or off, and/or replace the alias files.

        The alias files load in list order. None leaves either as it is. Turning boot.config on
        also applies its Wi-Fi, static addresses, USB ports and modules at the next start.
        """
        body: dict[str, Any] = {"enabled": enabled}
        if alias_files is not None:
            body["aliasFiles"] = _alias_files(alias_files)
        data = self._put_json("api/system/boot/startup", body)
        assert isinstance(data, dict)
        return BootConfig.from_dict(data)

    def update(
        self,
        *,
        if_modified: str | None = None,
        enabled: bool | None = None,
        description: str | None = None,
        alias_files: list[BootAliasFile] | None = None,
        modules: list[BootModule] | None = None,
        ip_configurations: list[BootAddress] | None = None,
        wifi: BootWifi | None = None,
        wifi_password: str | None = _KEEP,
        disable_usb_ports: bool | None = None,
        enable_media_devices: bool | None = None,
        services: list[BootService] | None = None,
    ) -> BootConfig:
        """Edit boot.config: each section given replaces the file's; the rest stays.

        Pass the ``modified`` you read as *if_modified* to get 409 instead of overwriting a
        change made since. *wifi* sends the Wi-Fi section (its ``password_set`` is ignored); the
        saved password stays unless *wifi_password* is given, and ``""`` clears it. Everything
        is checked before anything is written: a bad address, interface, unit name, module or
        alias file raises 400, and so does turning off one of ``protected_services``.
        """
        body: dict[str, Any] = {}
        if if_modified is not None:
            body["ifModified"] = if_modified
        if enabled is not None:
            body["enabled"] = enabled
        if description is not None:
            body["description"] = description
        if alias_files is not None:
            body["aliasFiles"] = _alias_files(alias_files)
        if modules is not None:
            body["modules"] = [
                {
                    "name": m.name,
                    "assemblyPath": m.assembly_path,
                    "className": m.class_name,
                    "namespace": m.namespace,
                    "enabled": m.enabled,
                }
                for m in modules
            ]
        if ip_configurations is not None:
            body["ipConfigurations"] = [
                {"interface": i.interface, "staticIp": i.static_ip, "enabled": i.enabled}
                for i in ip_configurations
            ]
        if wifi is not None or wifi_password is not _KEEP:
            if wifi is None:
                raise ValueError("wifi_password needs wifi: the Wi-Fi section is sent whole")
            body["wifi"] = {
                "enabled": wifi.enabled,
                "ssid": wifi.ssid,
                "password": None if wifi_password is _KEEP else wifi_password,
            }
        if disable_usb_ports is not None:
            body["disableUsbPorts"] = disable_usb_ports
        if enable_media_devices is not None:
            body["enableMediaDevices"] = enable_media_devices
        if services is not None:
            body["services"] = [
                {"name": s.name, "serviceFile": s.service_file, "enabled": s.enabled}
                for s in services
            ]
        data = self._put_json("api/system/boot", body)
        assert isinstance(data, dict)
        return BootConfig.from_dict(data)

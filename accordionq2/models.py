"""Data models for the AccordionQ2 REST API."""

from __future__ import annotations

from dataclasses import dataclass, field

from .enums import (
    AppTypes,
    BusActions,  # noqa: F401 – re-exported for convenience
    ChannelTypes,
    DirectionTypes,
    MpioUsageTypes,
    direction_to_json,
    parse_channel_types,
    parse_direction_types,
)


@dataclass(frozen=True, slots=True)
class ConnectionStatusDto:
    """Current connection status of the API to the hardware manager."""

    is_connected: bool = False
    last_error: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> ConnectionStatusDto:
        return cls(
            is_connected=data.get("isConnected", False),
            last_error=data.get("lastError"),
        )


@dataclass(frozen=True, slots=True)
class AppLicenseDto:
    """Application license information."""

    name: str = ""
    key: str = ""
    expires: str = ""
    type: AppTypes = AppTypes.UNKNOWN

    @classmethod
    def from_dict(cls, data: dict) -> AppLicenseDto:
        raw_type = data.get("type", "Unknown")
        try:
            app_type = AppTypes(raw_type)
        except ValueError:
            app_type = AppTypes.UNKNOWN
        return cls(
            name=data.get("name", ""),
            key=data.get("key", ""),
            expires=data.get("expires", ""),
            type=app_type,
        )


@dataclass(frozen=True, slots=True)
class ModuleSettingsDto:
    """Configuration settings for a hardware or software module."""

    name: str = ""
    enabled: bool = False
    class_name: str = ""
    assembly_path: str = ""
    namespace: str = ""
    image_name: str = ""
    initial_data: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> ModuleSettingsDto:
        return cls(
            name=data.get("name", ""),
            enabled=data.get("enabled", False),
            class_name=data.get("className", ""),
            assembly_path=data.get("assemblyPath", ""),
            namespace=data.get("namespace", ""),
            image_name=data.get("imageName", ""),
            initial_data=data.get("initialData") or {},
        )

    def to_dict(self) -> dict:
        return {
            "Name": self.name,
            "Enabled": self.enabled,
            "ClassName": self.class_name,
            "AssemblyPath": self.assembly_path,
            "Namespace": self.namespace,
            "ImageName": self.image_name,
            "InitialData": self.initial_data,
        }


@dataclass(frozen=True, slots=True)
class PhysicalModuleDto:
    """Describes one physical hardware module slot."""

    index: int = 0
    name: str = ""
    product_id: str = ""
    revision: int = 0
    serial_number: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> PhysicalModuleDto:
        return cls(
            index=data.get("index", 0),
            name=data.get("name", ""),
            product_id=data.get("productID", ""),
            revision=data.get("revision", 0),
            serial_number=data.get("serialNumber", ""),
        )


@dataclass(frozen=True, slots=True)
class PhysicalSystemDto:
    """Physical hardware system description (topology)."""

    host: str = ""
    eth_ip_v4: str = ""
    eth_ip_v6: str = ""
    firmware: str = ""
    mac: str = ""
    modules: tuple[PhysicalModuleDto, ...] = field(default_factory=tuple)
    network_interfaces: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> PhysicalSystemDto:
        modules_data = data.get("modules") or []
        return cls(
            host=data.get("host", ""),
            eth_ip_v4=data.get("ethIpV4", ""),
            eth_ip_v6=data.get("ethIpV6", ""),
            firmware=data.get("firmware", ""),
            mac=data.get("mac", ""),
            modules=tuple(PhysicalModuleDto.from_dict(m) for m in modules_data),
            network_interfaces=data.get("networkInterfaces") or {},
        )


@dataclass(frozen=True, slots=True)
class ChannelDto:
    """Represents a multi-purpose hardware channel."""

    channel_index: int = 0
    index: int = 0
    enabled: bool = False
    usage: MpioUsageTypes = MpioUsageTypes.UNDEFINED
    device_name: str = ""
    channel_type: ChannelTypes = ChannelTypes.UNDEFINED
    channel_type_capability: ChannelTypes = ChannelTypes.UNDEFINED
    alias: str = ""
    net_name: str = ""
    group_name: str = ""
    capability: DirectionTypes = DirectionTypes.UNDEFINED
    description: str = ""
    direction: DirectionTypes = DirectionTypes.UNDEFINED
    direction_changed: bool = False
    default_direction: DirectionTypes = DirectionTypes.UNDEFINED
    unit: str = ""
    is_virtual: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> ChannelDto:
        raw_usage = data.get("usage", "Undefined")
        try:
            usage = MpioUsageTypes(raw_usage)
        except ValueError:
            usage = MpioUsageTypes.UNDEFINED
        return cls(
            channel_index=data.get("channelIndex", 0),
            index=data.get("index", 0),
            enabled=data.get("enabled", False),
            usage=usage,
            device_name=data.get("deviceName", ""),
            channel_type=parse_channel_types(data.get("channelType", 0)),
            channel_type_capability=parse_channel_types(data.get("channelTypeCapability", 0)),
            alias=data.get("alias", ""),
            net_name=data.get("netName", ""),
            group_name=data.get("groupName", ""),
            capability=parse_direction_types(data.get("capability", 0)),
            description=data.get("description", ""),
            direction=parse_direction_types(data.get("direction", 0)),
            direction_changed=data.get("directionChanged", False),
            default_direction=parse_direction_types(data.get("defaultDirection", 0)),
            unit=data.get("unit", ""),
            is_virtual=data.get("isVirtual", False),
        )


@dataclass(slots=True)
class ChannelLookupRequest:
    """Identifies a channel by alias or net name."""

    alias: str | None = None
    net_name: str | None = None

    def to_dict(self) -> dict:
        result: dict = {}
        if self.alias is not None:
            result["Alias"] = self.alias
        if self.net_name is not None:
            result["NetName"] = self.net_name
        return result


@dataclass(slots=True)
class ChannelConfigRequest:
    """Partial-update configuration for a single channel.

    Only non-None fields are applied; the rest are left unchanged.
    """

    alias: str | None = None
    net_name: str | None = None
    enabled: bool | None = None
    direction: DirectionTypes | None = None
    description: str | None = None
    unit: str | None = None
    group_name: str | None = None
    device_name: str | None = None

    def to_dict(self) -> dict:
        result: dict = {}
        if self.alias is not None:
            result["Alias"] = self.alias
        if self.net_name is not None:
            result["NetName"] = self.net_name
        if self.enabled is not None:
            result["Enabled"] = self.enabled
        if self.direction is not None:
            result["Direction"] = direction_to_json(self.direction)
        if self.description is not None:
            result["Description"] = self.description
        if self.unit is not None:
            result["Unit"] = self.unit
        if self.group_name is not None:
            result["GroupName"] = self.group_name
        if self.device_name is not None:
            result["DeviceName"] = self.device_name
        return result


@dataclass(frozen=True, slots=True)
class BusTransactionResponse:
    """Result of a raw bus transaction (I2C, UART, SPI, or Socket)."""

    device_name: str = ""
    action: str = ""
    received: bytes = b""
    number_of_bytes_received: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> BusTransactionResponse:
        raw = data.get("received") or ""
        try:
            received = bytes.fromhex(raw) if raw else b""
        except Exception:
            received = b""
        return cls(
            device_name=data.get("deviceName", ""),
            action=data.get("action", ""),
            received=received,
            number_of_bytes_received=data.get("numberOfBytesReceived", len(received)),
        )


@dataclass(frozen=True, slots=True)
class NumericResultChannelDto:
    """Describes one NumericResult channel and its sampling capabilities."""

    net_name: str = ""
    alias: str = ""
    possible_target_names: tuple[str, ...] = field(default_factory=tuple)
    sample_rate: int = 0
    default_samples: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> NumericResultChannelDto:
        return cls(
            net_name=data.get("netName", ""),
            alias=data.get("alias", ""),
            possible_target_names=tuple(data.get("possibleTargetNames") or []),
            sample_rate=data.get("sampleRate", 0),
            default_samples=data.get("defaultSamples", 0),
        )


@dataclass(frozen=True, slots=True)
class NumericMeasureResultDto:
    """Acquisition metadata returned after a successful measure call."""

    channel_net_name: str = ""
    target_net_name: str = ""
    sample_count: int = 0
    sample_rate: int = 0
    reduced_set: bool = True
    started: str = ""
    stopped: str = ""
    duration: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> NumericMeasureResultDto:
        return cls(
            channel_net_name=data.get("channelNetName", ""),
            target_net_name=data.get("targetNetName", ""),
            sample_count=data.get("sampleCount", 0),
            sample_rate=data.get("sampleRate", 0),
            reduced_set=data.get("reducedSet", True),
            started=data.get("started", ""),
            stopped=data.get("stopped", ""),
            duration=data.get("duration", ""),
        )

"""Data models for the AccordionQ2 REST API."""

from dataclasses import dataclass, field

from .enums import (
    AppTypes,
    ChannelTypes,
    DirectionTypes,
    MpioUsageTypes,
    direction_to_json,
    parse_channel_types,
    parse_direction_types,
)


@dataclass
class ConnectionStatusDto:
    """Current connection status of the API to the hardware manager."""
    is_connected = False
    last_error = None

    def __init__(self, is_connected=False, last_error=None):
        self.is_connected = is_connected
        self.last_error = last_error

    @classmethod
    def from_dict(cls, data):
        return cls(
            is_connected=data.get("IsConnected", False),
            last_error=data.get("LastError"),
        )


@dataclass
class AppLicenseDto:
    """Application license information."""
    name = ""
    key = ""
    expires = ""
    type = AppTypes.UNKNOWN

    def __init__(self, name="", key="", expires="", type=AppTypes.UNKNOWN):
        self.name = name
        self.key = key
        self.expires = expires
        self.type = type

    @classmethod
    def from_dict(cls, data):
        raw_type = data.get("Type", "Unknown")
        try:
            app_type = AppTypes(raw_type)
        except ValueError:
            app_type = AppTypes.UNKNOWN
        return cls(
            name=data.get("Name", ""),
            key=data.get("Key", ""),
            expires=data.get("Expires", ""),
            type=app_type,
        )


@dataclass
class ModuleSettingsDto:
    """Configuration settings for a hardware or software module."""
    name = ""
    enabled = False
    class_name = ""
    assembly_path = ""
    namespace = ""
    image_name = ""
    initial_data = None

    def __init__(self, name="", enabled=False, class_name="", assembly_path="",
                 namespace="", image_name="", initial_data=None):
        self.name = name
        self.enabled = enabled
        self.class_name = class_name
        self.assembly_path = assembly_path
        self.namespace = namespace
        self.image_name = image_name
        self.initial_data = initial_data if initial_data is not None else {}

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data.get("Name", ""),
            enabled=data.get("Enabled", False),
            class_name=data.get("ClassName", ""),
            assembly_path=data.get("AssemblyPath", ""),
            namespace=data.get("Namespace", ""),
            image_name=data.get("ImageName", ""),
            initial_data=data.get("InitialData") or {},
        )

    def to_dict(self):
        return {
            "Name": self.name,
            "Enabled": self.enabled,
            "ClassName": self.class_name,
            "AssemblyPath": self.assembly_path,
            "Namespace": self.namespace,
            "ImageName": self.image_name,
            "InitialData": self.initial_data,
        }


@dataclass
class PhysicalModuleDto:
    """Describes one physical hardware module slot."""
    index = 0
    name = ""
    product_id = ""
    revision = 0
    serial_number = ""

    def __init__(self, index=0, name="", product_id="", revision=0, serial_number=""):
        self.index = index
        self.name = name
        self.product_id = product_id
        self.revision = revision
        self.serial_number = serial_number

    @classmethod
    def from_dict(cls, data):
        return cls(
            index=data.get("Index", 0),
            name=data.get("Name", ""),
            product_id=data.get("ProductID", ""),
            revision=data.get("Revision", 0),
            serial_number=data.get("SerialNumber", ""),
        )


@dataclass
class PhysicalSystemDto:
    """Physical hardware system description (topology)."""
    host = ""
    eth_ip_v4 = ""
    eth_ip_v6 = ""
    firmware = ""
    mac = ""
    modules = None
    network_interfaces = None

    def __init__(self, host="", eth_ip_v4="", eth_ip_v6="", firmware="",
                 mac="", modules=None, network_interfaces=None):
        self.host = host
        self.eth_ip_v4 = eth_ip_v4
        self.eth_ip_v6 = eth_ip_v6
        self.firmware = firmware
        self.mac = mac
        self.modules = modules if modules is not None else []
        self.network_interfaces = network_interfaces if network_interfaces is not None else {}

    @classmethod
    def from_dict(cls, data):
        modules_data = data.get("Modules") or []
        return cls(
            host=data.get("Host", ""),
            eth_ip_v4=data.get("EthIpV4", ""),
            eth_ip_v6=data.get("EthIpV6", ""),
            firmware=data.get("Firmware", ""),
            mac=data.get("MAC", ""),
            modules=[PhysicalModuleDto.from_dict(m) for m in modules_data],
            network_interfaces=data.get("NetworkInterfaces") or {},
        )


@dataclass
class ChannelDto:
    """Represents a multi-purpose hardware channel."""
    channel_index = 0
    index = 0
    enabled = False
    usage = MpioUsageTypes.UNDEFINED
    device_name = ""
    channel_type = ChannelTypes.UNDEFINED
    channel_type_capability = ChannelTypes.UNDEFINED
    alias = ""
    net_name = ""
    group_name = ""
    capability = DirectionTypes.UNDEFINED
    description = ""
    direction = DirectionTypes.UNDEFINED
    direction_changed = False
    default_direction = DirectionTypes.UNDEFINED
    unit = ""
    is_virtual = False

    def __init__(self, channel_index=0, index=0, enabled=False,
                 usage=MpioUsageTypes.UNDEFINED, device_name="",
                 channel_type=ChannelTypes.UNDEFINED,
                 channel_type_capability=ChannelTypes.UNDEFINED,
                 alias="", net_name="", group_name="",
                 capability=DirectionTypes.UNDEFINED, description="",
                 direction=DirectionTypes.UNDEFINED, direction_changed=False,
                 default_direction=DirectionTypes.UNDEFINED, unit="",
                 is_virtual=False):
        self.channel_index = channel_index
        self.index = index
        self.enabled = enabled
        self.usage = usage
        self.device_name = device_name
        self.channel_type = channel_type
        self.channel_type_capability = channel_type_capability
        self.alias = alias
        self.net_name = net_name
        self.group_name = group_name
        self.capability = capability
        self.description = description
        self.direction = direction
        self.direction_changed = direction_changed
        self.default_direction = default_direction
        self.unit = unit
        self.is_virtual = is_virtual

    @classmethod
    def from_dict(cls, data):
        raw_usage = data.get("Usage", "Undefined")
        try:
            usage = MpioUsageTypes(raw_usage)
        except ValueError:
            usage = MpioUsageTypes.UNDEFINED
        return cls(
            channel_index=data.get("ChannelIndex", 0),
            index=data.get("Index", 0),
            enabled=data.get("Enabled", False),
            usage=usage,
            device_name=data.get("DeviceName", ""),
            channel_type=parse_channel_types(data.get("ChannelType", 0)),
            channel_type_capability=parse_channel_types(data.get("ChannelTypeCapability", 0)),
            alias=data.get("Alias", ""),
            net_name=data.get("NetName", ""),
            group_name=data.get("GroupName", ""),
            capability=parse_direction_types(data.get("Capability", 0)),
            description=data.get("Description", ""),
            direction=parse_direction_types(data.get("Direction", 0)),
            direction_changed=data.get("DirectionChanged", False),
            default_direction=parse_direction_types(data.get("DefaultDirection", 0)),
            unit=data.get("Unit", ""),
            is_virtual=data.get("IsVirtual", False),
        )


class ChannelLookupRequest:
    """Identifies a channel by alias or net name."""

    def __init__(self, alias=None, net_name=None):
        self.alias = alias
        self.net_name = net_name

    def to_dict(self):
        result = {}
        if self.alias is not None:
            result["Alias"] = self.alias
        if self.net_name is not None:
            result["NetName"] = self.net_name
        return result


class ChannelConfigRequest:
    """Partial-update configuration for a single channel.

    Only non-None fields are applied; the rest are left unchanged.
    """

    def __init__(self, alias=None, net_name=None, enabled=None, direction=None,
                 description=None, unit=None, group_name=None, device_name=None):
        self.alias = alias
        self.net_name = net_name
        self.enabled = enabled
        self.direction = direction
        self.description = description
        self.unit = unit
        self.group_name = group_name
        self.device_name = device_name

    def to_dict(self):
        result = {}
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

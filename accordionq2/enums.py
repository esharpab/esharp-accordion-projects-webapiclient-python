"""Enumerations mirroring the AccordionQ2 hardware type definitions."""

from enum import Enum, IntFlag


class ModuleStatus(str, Enum):
    """Application module status."""
    UNKNOWN = "Unknown"
    OK = "OK"
    WARNING = "Warning"
    ERROR = "Error"
    DISABLED = "Disabled"


class AppTypes(str, Enum):
    """Application/module type classification."""
    UNKNOWN = "Unknown"
    SOFTWARE_MODULE = "SoftwareModule"
    HARDWARE_MODULE = "HardwareModule"


class DirectionTypes(IntFlag):
    """I/O direction flags for channels."""
    UNDEFINED = 0
    IN = 1
    OUT = 2


class MpioUsageTypes(str, Enum):
    """Multi-purpose I/O usage classification."""
    UNDEFINED = "Undefined"
    HIDDEN_SYSTEM_CONTROL = "HiddenSystemControl"
    READ_ONLY_SYSTEM_CONTROL = "ReadOnlySystemControl"
    USER_ALLOCATABLE = "UserAllocatable"
    BUS_SIGNAL = "BusSignal"


class ChannelTypes(IntFlag):
    """Hardware channel type flags."""
    UNDEFINED = 0
    ANALOG = 1 << 0
    DIGITAL = 1 << 1
    VIRTUAL_DIGITAL = 1 << 2
    TEMPERATURE = 1 << 3
    MULTIPLEXER = 1 << 4
    RESISTANCE = 1 << 5
    COUNTER = 1 << 6
    FREQUENCY = 1 << 7
    ACTUATOR = 1 << 8
    REGISTER = 1 << 10
    CURRENT = 1 << 11
    RATIOMETRIC = 1 << 12
    UART = 1 << 13
    SPI = 1 << 14
    I2C = 1 << 15
    BYTE_STREAM = 1 << 16
    SOCKET = 1 << 17
    WAVEFORM = 1 << 18
    NUMERIC_RESULT = 1 << 19
    PSEUDO_DIGITAL = 1 << 20
    IMAGE = 1 << 21
    AUDIO = 1 << 22
    VIDEO = 1 << 23
    INSTRUMENT = 1 << 24
    NUMERIC_RESULTS = 1 << 25
    CALIBRATION = 1 << 26


# --- JSON parsing helpers for IntFlag enums ---

_DIRECTION_NAMES = {
    "Undefined": 0, "IN": 1, "OUT": 2,
}

_CHANNEL_TYPE_NAMES = {
    "Undefined": 0,
    "Analog": 1 << 0,
    "Digital": 1 << 1,
    "VirtualDigital": 1 << 2,
    "Temperature": 1 << 3,
    "Multiplexer": 1 << 4,
    "Resistance": 1 << 5,
    "Counter": 1 << 6,
    "Frequency": 1 << 7,
    "Actuator": 1 << 8,
    "Register": 1 << 10,
    "Current": 1 << 11,
    "Ratiometric": 1 << 12,
    "UART": 1 << 13,
    "SPI": 1 << 14,
    "I2C": 1 << 15,
    "ByteStream": 1 << 16,
    "Socket": 1 << 17,
    "Waveform": 1 << 18,
    "NumericResult": 1 << 19,
    "PseudoDigital": 1 << 20,
    "Image": 1 << 21,
    "Audio": 1 << 22,
    "Video": 1 << 23,
    "Instrument": 1 << 24,
    "NumericResults": 1 << 25,
    "Calibration": 1 << 26,
}


def parse_direction_types(value):
    """Parse a DirectionTypes value from JSON (integer or comma-separated string)."""
    if isinstance(value, int):
        return DirectionTypes(value)
    if isinstance(value, str):
        result = 0
        for part in value.split(","):
            result |= _DIRECTION_NAMES.get(part.strip(), 0)
        return DirectionTypes(result)
    return DirectionTypes.UNDEFINED


def parse_channel_types(value):
    """Parse a ChannelTypes value from JSON (integer or comma-separated string)."""
    if isinstance(value, int):
        return ChannelTypes(value)
    if isinstance(value, str):
        result = 0
        for part in value.split(","):
            result |= _CHANNEL_TYPE_NAMES.get(part.strip(), 0)
        return ChannelTypes(result)
    return ChannelTypes.UNDEFINED


_DIRECTION_NAMES_REV = {v: k for k, v in _DIRECTION_NAMES.items()}


def direction_to_json(value):
    """Serialize a DirectionTypes value to a JSON-compatible string."""
    parts = [
        _DIRECTION_NAMES_REV[m.value]
        for m in DirectionTypes
        if m.value and m in value
    ]
    return ", ".join(parts) if parts else "Undefined"

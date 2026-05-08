"""Enumerations mirroring the AccordionQ2 hardware type definitions."""

from __future__ import annotations

from enum import IntFlag, StrEnum


class ModuleStatus(StrEnum):
    """Application module status."""

    UNKNOWN = "Unknown"
    OK = "OK"
    WARNING = "Warning"
    ERROR = "Error"
    DISABLED = "Disabled"


class AppTypes(StrEnum):
    """Application/module type classification."""

    UNKNOWN = "Unknown"
    SOFTWARE_MODULE = "SoftwareModule"
    HARDWARE_MODULE = "HardwareModule"


class DirectionTypes(IntFlag):
    """I/O direction flags for channels."""

    UNDEFINED = 0
    IN = 1
    OUT = 2


class MpioUsageTypes(StrEnum):
    """Multi-purpose I/O usage classification."""

    UNDEFINED = "Undefined"
    HIDDEN_SYSTEM_CONTROL = "HiddenSystemControl"
    READ_ONLY_SYSTEM_CONTROL = "ReadOnlySystemControl"
    USER_ALLOCATABLE = "UserAllocatable"
    BUS_SIGNAL = "BusSignal"


class BusActions(StrEnum):
    """Bus transaction action, mirroring ``BusTransactionTypes.BusActions``."""

    UNDEFINED = "Undefined"
    SEND = "Send"
    RECEIVE = "Receive"
    SEND_RECEIVE = "SendReceive"
    SCAN = "Scan"
    BREAK = "Break"
    CLEAR_BUFFERS = "ClearBuffers"
    RECONFIGURE = "Reconfigure"


class UartBusTypes(StrEnum):
    """UART electrical standard, mirroring ``BusTransactionTypes.UartBusTypes``."""

    UNDEFINED = "Undefined"
    RS232 = "RS232"
    RS422 = "RS422"
    RS485 = "RS485"


class FlowControlTypes(StrEnum):
    """UART flow control mode, mirroring ``BusTransactionTypes.FlowControlTypes``."""

    UNDEFINED = "Undefined"
    NONE = "None"
    XON_XOFF = "XON_XOFF"
    RTS_CTS = "RTS_CTS"
    RTS_CTS_AND_XON_XOFF = "RTS_CTS_AND_XON_XOFF"
    DTR_DSR = "DTR_DSR"
    DTR_DSR_AND_XON_XOFF = "DTR_DSR_AND_XON_XOFF"


class ParityTypes(StrEnum):
    """Serial parity setting, mirroring ``InstrumentTypes.ParityTypes``."""

    UNDEFINED = "Undefined"
    EVEN = "Even"
    MARK = "Mark"
    NONE = "None"
    ODD = "Odd"
    SPACE = "Space"


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


# --- JSON name → integer value mappings derived from the enum members ---
# Keys match the PascalCase names used in the REST API JSON payloads.
# Keeping these explicit (rather than auto-generating from member names) lets
# us handle the handful of cases where the JSON name differs from the Python
# attribute name (e.g. "UART" → ChannelTypes.UART, "I2C" → ChannelTypes.I2C).

_DIRECTION_JSON: dict[str, int] = {
    "Undefined": 0,
    "IN": DirectionTypes.IN,
    "OUT": DirectionTypes.OUT,
}

_CHANNEL_TYPE_JSON: dict[str, int] = {
    "Undefined": 0,
    "Analog": ChannelTypes.ANALOG,
    "Digital": ChannelTypes.DIGITAL,
    "VirtualDigital": ChannelTypes.VIRTUAL_DIGITAL,
    "Temperature": ChannelTypes.TEMPERATURE,
    "Multiplexer": ChannelTypes.MULTIPLEXER,
    "Resistance": ChannelTypes.RESISTANCE,
    "Counter": ChannelTypes.COUNTER,
    "Frequency": ChannelTypes.FREQUENCY,
    "Actuator": ChannelTypes.ACTUATOR,
    "Register": ChannelTypes.REGISTER,
    "Current": ChannelTypes.CURRENT,
    "Ratiometric": ChannelTypes.RATIOMETRIC,
    "UART": ChannelTypes.UART,
    "SPI": ChannelTypes.SPI,
    "I2C": ChannelTypes.I2C,
    "ByteStream": ChannelTypes.BYTE_STREAM,
    "Socket": ChannelTypes.SOCKET,
    "Waveform": ChannelTypes.WAVEFORM,
    "NumericResult": ChannelTypes.NUMERIC_RESULT,
    "PseudoDigital": ChannelTypes.PSEUDO_DIGITAL,
    "Image": ChannelTypes.IMAGE,
    "Audio": ChannelTypes.AUDIO,
    "Video": ChannelTypes.VIDEO,
    "Instrument": ChannelTypes.INSTRUMENT,
    "NumericResults": ChannelTypes.NUMERIC_RESULTS,
    "Calibration": ChannelTypes.CALIBRATION,
}

_DIRECTION_JSON_REV: dict[int, str] = {v: k for k, v in _DIRECTION_JSON.items() if v != 0}


def parse_direction_types(value: int | str) -> DirectionTypes:
    """Parse a DirectionTypes value from JSON (integer or comma-separated string)."""
    if isinstance(value, int):
        return DirectionTypes(value)
    result = 0
    for part in value.split(","):
        result |= _DIRECTION_JSON.get(part.strip(), 0)
    return DirectionTypes(result)


def parse_channel_types(value: int | str) -> ChannelTypes:
    """Parse a ChannelTypes value from JSON (integer or comma-separated string)."""
    if isinstance(value, int):
        return ChannelTypes(value)
    result = 0
    for part in value.split(","):
        result |= _CHANNEL_TYPE_JSON.get(part.strip(), 0)
    return ChannelTypes(result)


def direction_to_json(value: DirectionTypes) -> str:
    """Serialize a DirectionTypes value to a JSON-compatible string."""
    parts = [_DIRECTION_JSON_REV[m.value] for m in DirectionTypes if m.value and m in value]
    return ", ".join(parts) if parts else "Undefined"

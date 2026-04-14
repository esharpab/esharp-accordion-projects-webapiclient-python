# Enumerations

All enums live in `accordionq2.enums`.

## `ModuleStatus`

Application module status. Type: `str, Enum`.

| Value | Description |
|-------|-------------|
| `UNKNOWN` | Status is unknown |
| `OK` | Module is operating normally |
| `WARNING` | Module has warnings |
| `ERROR` | Module has errors |
| `DISABLED` | Module is disabled |

## `AppTypes`

Application/module type classification. Type: `str, Enum`.

| Value | Description |
|-------|-------------|
| `UNKNOWN` | Type is unknown |
| `SOFTWARE_MODULE` | Software module |
| `HARDWARE_MODULE` | Hardware module |

## `DirectionTypes`

I/O direction flags for channels. Type: `IntFlag`.

| Value | Int | Description |
|-------|-----|-------------|
| `UNDEFINED` | 0 | Not defined |
| `IN` | 1 | Input capable |
| `OUT` | 2 | Output capable |

Supports bitwise operations:

```python
from accordionq2.enums import DirectionTypes

# Check if a channel is input capable
if ch.direction & DirectionTypes.IN:
    print("Input capable")
```

## `MpioUsageTypes`

Multi-purpose I/O usage classification. Type: `str, Enum`.

| Value | Description |
|-------|-------------|
| `UNDEFINED` | Not defined |
| `HIDDEN_SYSTEM_CONTROL` | Hidden system control pin |
| `READ_ONLY_SYSTEM_CONTROL` | Read-only system control pin |
| `USER_ALLOCATABLE` | User-allocatable pin |
| `BUS_SIGNAL` | Bus signal pin |

## `BusActions`

Bus transaction action types. Type: `str, Enum`.

| Value | Description |
|-------|-------------|
| `UNDEFINED` | Not defined |
| `SEND` | Transmit data |
| `RECEIVE` | Receive data |
| `SEND_RECEIVE` | Transmit then receive |
| `SCAN` | Scan for devices (I2C) |
| `BREAK` | Send a break condition |
| `CLEAR_BUFFERS` | Clear receive/transmit buffers |
| `RECONFIGURE` | Reconfigure the bus |

## `ChannelTypes`

Hardware channel type flags. Type: `IntFlag`.

| Value | Bit | Description |
|-------|-----|-------------|
| `UNDEFINED` | 0 | Not defined |
| `ANALOG` | 1 | Analog channel |
| `DIGITAL` | 2 | Digital channel |
| `VIRTUAL_DIGITAL` | 4 | Virtual digital channel |
| `TEMPERATURE` | 8 | Temperature sensor |
| `MULTIPLEXER` | 16 | Multiplexer channel |
| `RESISTANCE` | 32 | Resistance measurement |
| `COUNTER` | 64 | Counter channel |
| `FREQUENCY` | 128 | Frequency measurement |
| `ACTUATOR` | 256 | Actuator control |
| `REGISTER` | 1024 | Register access |
| `CURRENT` | 2048 | Current measurement |
| `RATIOMETRIC` | 4096 | Ratiometric measurement |
| `UART` | 8192 | UART communication |
| `SPI` | 16384 | SPI communication |
| `I2C` | 32768 | I2C communication |
| `BYTE_STREAM` | 65536 | Byte stream |
| `SOCKET` | 131072 | TCP socket |
| `WAVEFORM` | 262144 | Waveform channel |
| `NUMERIC_RESULT` | 524288 | Numeric result (single) |
| `PSEUDO_DIGITAL` | 1048576 | Pseudo-digital channel |
| `IMAGE` | 2097152 | Image channel |
| `AUDIO` | 4194304 | Audio channel |
| `VIDEO` | 8388608 | Video channel |
| `INSTRUMENT` | 16777216 | Instrument channel |
| `NUMERIC_RESULTS` | 33554432 | Numeric results (batch) |
| `CALIBRATION` | 67108864 | Calibration channel |

Supports bitwise operations:

```python
from accordionq2.enums import ChannelTypes

# Combine types
combined = ChannelTypes.ANALOG | ChannelTypes.DIGITAL

# Check if a channel is I2C
if ch.channel_type & ChannelTypes.I2C:
    print("I2C channel")
```

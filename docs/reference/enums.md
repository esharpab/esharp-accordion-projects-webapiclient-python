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
| `ANALOG` | 1 | Analog (voltage/current) channel |
| `DIGITAL` | 2 | Digital I/O channel |
| `VIRTUAL_DIGITAL` | 4 | Software-defined digital channel |
| `TEMPERATURE` | 8 | Temperature sensor channel |
| `MULTIPLEXER` | 16 | Multiplexer channel |
| `RESISTANCE` | 32 | Resistance measurement channel |
| `COUNTER` | 64 | Pulse counter channel |
| `FREQUENCY` | 128 | Frequency measurement channel |
| `ACTUATOR` | 256 | Actuator output channel |
| `REGISTER` | 1024 | Register/memory-mapped channel |
| `CURRENT` | 2048 | Current measurement channel |
| `RATIOMETRIC` | 4096 | Ratiometric measurement channel |
| `UART` | 8192 | UART serial channel |
| `SPI` | 16384 | SPI bus channel |
| `I2C` | 32768 | I2C bus channel |
| `BYTE_STREAM` | 65536 | Raw byte stream channel |
| `SOCKET` | 131072 | TCP socket channel |
| `WAVEFORM` | 262144 | Waveform generation/capture channel |
| `NUMERIC_RESULT` | 524288 | Single numeric result channel |
| `PSEUDO_DIGITAL` | 1048576 | Pseudo-digital (thresholded analog) channel |
| `IMAGE` | 2097152 | Image capture channel |
| `AUDIO` | 4194304 | Audio channel |
| `VIDEO` | 8388608 | Video channel |
| `INSTRUMENT` | 16777216 | Virtual instrument channel |
| `NUMERIC_RESULTS` | 33554432 | Multi-sample numeric results channel |
| `CALIBRATION` | 67108864 | Calibration channel |

Supports bitwise operations:

```python
from accordionq2.enums import ChannelTypes

if ch.channel_type & ChannelTypes.ANALOG:
    print("Analog channel")

if ch.channel_type & (ChannelTypes.I2C | ChannelTypes.SPI):
    print("Bus channel")
```

---

## `UartBusTypes`

UART electrical standard. Type: `str, Enum`. Mirrors `BusTransactionTypes.UartBusTypes`.

| Value | Description |
|-------|-------------|
| `UNDEFINED` | Not defined |
| `RS232` | Standard RS-232 full-duplex serial |
| `RS422` | Differential RS-422 serial |
| `RS485` | Multi-drop RS-485 serial |

---

## `FlowControlTypes`

UART flow control mode. Type: `str, Enum`. Mirrors `BusTransactionTypes.FlowControlTypes`.

| Value | Description |
|-------|-------------|
| `UNDEFINED` | Not defined |
| `NONE` | No flow control |
| `XON_XOFF` | Software (XON/XOFF) flow control |
| `RTS_CTS` | Hardware RTS/CTS flow control |
| `RTS_CTS_AND_XON_XOFF` | Hardware RTS/CTS combined with XON/XOFF |
| `DTR_DSR` | Hardware DTR/DSR flow control |
| `DTR_DSR_AND_XON_XOFF` | Hardware DTR/DSR combined with XON/XOFF |

---

## `ParityTypes`

Serial port parity. Type: `str, Enum`. Mirrors `InstrumentTypes.ParityTypes`.

| Value | Description |
|-------|-------------|
| `UNDEFINED` | Not defined / unknown |
| `NONE` | No parity |
| `EVEN` | Even parity |
| `ODD` | Odd parity |
| `MARK` | Mark parity |
| `SPACE` | Space parity |

```python
from accordionq2.enums import FlowControlTypes, ParityTypes, UartBusTypes

resp = client.comm.uart(
    "MyDevice",
    action=BusActions.SEND_RECEIVE,
    port_name="/dev/ttyS0",
    baud_rate=115200,
    bus_type=UartBusTypes.RS485,
    flow_control=FlowControlTypes.NONE,
    parity=ParityTypes.ODD,
    data_to_send=b"\x01\x03",
    number_of_bytes_to_receive=8,
)
```

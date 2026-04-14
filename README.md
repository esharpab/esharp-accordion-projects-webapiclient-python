# AccordionQ2 Python Client

Python client library for the **AccordionQ2 Hardware Management REST API**.
This is the Python counterpart of the
[.NET WebApiClient](https://www.nuget.org/packages/AccordionQ2.WebApiClient/);
both libraries expose the same API surface so switching between them feels
natural.

[![PyPI](https://img.shields.io/pypi/v/accordionq2)](https://pypi.org/project/accordionq2/)
[![NuGet](https://img.shields.io/nuget/v/AccordionQ2.WebApiClient)](https://www.nuget.org/packages/AccordionQ2.WebApiClient/)
[![Documentation](https://readthedocs.org/projects/esharp-accordion-projects-webapiclient-python/badge/?version=latest)](https://esharp-accordion-projects-webapiclient-python.readthedocs.io/en/latest/)

## Requirements

| Requirement | Details |
|-------------|---------|
| Python      | 3.8 or later |
| Platform    | Windows, Linux (including ARM / Raspberry Pi) |
| Architecture | 32-bit and 64-bit |
| Dependencies | **None** &mdash; stdlib only (`urllib`, `json`, `enum`, `dataclasses`) |

## Installation

Install directly from a local checkout (editable mode recommended during
development):

```bash
pip install -e .
```

Or install from [PyPI](https://pypi.org/project/accordionq2/):

```bash
pip install accordionq2
```

## Quick Start

```python
from accordionq2 import AccordionQ2Client

with AccordionQ2Client("http://agent64.local:5000") as client:
    # Check the hardware connection
    status = client.connection.get_status()
    print("Connected:", status.is_connected)

    # Read a sensor value
    temp = client.resources.get_value("TempRegulator.CPU_TEMP")
    print("CPU temperature:", temp)

    # List all channels
    for ch in client.channels.get_all():
        print(f"  {ch.alias}: type={ch.channel_type}, unit={ch.unit}")
```

The client can also be used without a `with` block:

```python
client = AccordionQ2Client("http://agent64.local:5000")
names = client.resources.get_names()
client.close()
```

### Constructor

```python
AccordionQ2Client(base_url, timeout=30.0)
```

| Parameter  | Description |
|------------|-------------|
| `base_url` | Base URL of the AccordionQ2 WebApi, e.g. `"http://raspberrypi:5000"` |
| `timeout`  | HTTP request timeout in seconds (default **30**) |

---

## API Reference

The client exposes six **groups**, each covering one area of the hardware
API.  All methods are **synchronous** and raise
`AccordionQ2ApiError` on HTTP errors.

### `client.connection` &mdash; Connection Status

| Method | Returns | Description |
|--------|---------|-------------|
| `get_status()` | `ConnectionStatusDto` | Check whether the API is connected to the hardware manager. |

```python
status = client.connection.get_status()
if not status.is_connected:
    print("Error:", status.last_error)
```

---

### `client.resources` &mdash; Resource Values

Resources represent readable/writable hardware values such as voltages,
temperatures, and firmware revisions.  They are identified by a dotted name
string (e.g. `"TempRegulator.CPU_TEMP"`).

| Method | Returns | Description |
|--------|---------|-------------|
| `get_names()` | `list[str]` | List all available resource names. |
| `get_value(name)` | `str` | Read the current value of a single resource. |
| `set_value(name, value)` | &mdash; | Write a value to a single resource. |
| `get_values(names)` | `dict[str, str]` | Read multiple resources in one call. |
| `set_values(resources)` | &mdash; | Write multiple resources in one call. |
| `transact(name, value)` | `str` | Write then read (command/response pattern). |

```python
# Single read
voltage = client.resources.get_value("0.1.ESH10000158.MON_3V3")

# Batch read
values = client.resources.get_values([
    "TempRegulator.CPU_TEMP",
    "Engine.Uptime",
])
for name, val in values.items():
    print(f"{name} = {val}")
```

---

### `client.channels` &mdash; Hardware Channels

Channels represent multi-purpose I/O pins (analog, digital, I2C, SPI, etc.).

| Method | Returns | Description |
|--------|---------|-------------|
| `get_all()` | `list[ChannelDto]` | Return every configured channel. |
| `get_channel(alias=, net_name=)` | `ChannelDto` | Look up one channel by alias or net name. |
| `configure(config)` | &mdash; | Partial-update a single channel. |
| `configure_many(configs)` | &mdash; | Partial-update multiple channels. |

```python
from accordionq2.models import ChannelConfigRequest
from accordionq2.enums import ChannelTypes

# Look up by alias
ch = client.channels.get_channel(alias="0.1.ESH10000158.MON_3V3")
print(f"Type: {ch.channel_type}, Direction: {ch.direction}")

# Check flags
if ch.channel_type & ChannelTypes.ANALOG:
    print("This is an analog channel")

# Partial update (only the fields you set are changed)
client.channels.configure(ChannelConfigRequest(
    alias="0.1.ESH10000158.MON_3V3",
    description="Main 3.3 V rail monitor",
    unit="V",
))
```

---

### `client.modules` &mdash; Module Management

| Method | Returns | Description |
|--------|---------|-------------|
| `get_all()` | `list[ModuleSettingsDto]` | All modules (loaded and unloaded). |
| `get_loaded()` | `list[ModuleSettingsDto]` | Currently loaded modules only. |
| `load(module)` | &mdash; | Load a module. |
| `unload(module)` | &mdash; | Unload a module. |
| `configure(module)` | &mdash; | Update module configuration. |
| `get_physical_system()` | `PhysicalSystemDto` | Hardware topology (host, MAC, modules). |
| `get_licensed_apps()` | `list[AppLicenseDto]` | Licensed applications. |
| `get_all_apps()` | `list[AppLicenseDto]` | All applications. |

```python
system = client.modules.get_physical_system()
print(f"Host: {system.host}, MAC: {system.mac}")
for mod in system.modules:
    print(f"  Slot {mod.index}: {mod.name} ({mod.product_id})")

for m in client.modules.get_loaded():
    print(f"  {m.name} (enabled={m.enabled})")
```

---

### `client.application` &mdash; Application Lifecycle

| Method | Returns | Description |
|--------|---------|-------------|
| `get_name()` | `str` | Application module name. |
| `get_identification()` | `str` | Application identification string. |
| `get_status()` | `ModuleStatus` | Current status (enum). |
| `reset()` | &mdash; | Reset the application engine. |
| `list_config_files()` | `list[str]` | Available configuration files. |
| `get_loaded_config_files()` | `list[str]` | Currently loaded config files. |
| `load_config_file(name)` | &mdash; | Load a configuration file. |
| `save_config_file(name)` | &mdash; | Save configuration to a file. |
| `download_config_file(name)` | `bytes` | Download a config file as raw bytes. |
| `upload_config_file(name, data)` | &mdash; | Upload a config file (bytes). |
| `delete_config_file(name)` | &mdash; | Delete a config file from the device. |

```python
from accordionq2.enums import ModuleStatus

status = client.application.get_status()
if status == ModuleStatus.OK:
    print("Application is running normally")

# Configuration file round-trip
data = client.application.download_config_file("factory.cfg")
client.application.upload_config_file("factory_backup.cfg", data)
```

---

### `client.media` &mdash; Media Files

| Method | Returns | Description |
|--------|---------|-------------|
| `list_files()` | `list[str]` | List media files on the device. |
| `download_file(name)` | `bytes` | Download a media file. |
| `upload_file(name, data)` | &mdash; | Upload a media file (bytes). |
| `delete_file(name)` | &mdash; | Delete a media file. |

```python
for f in client.media.list_files():
    print(f)

# Download and save locally
content = client.media.download_file("waveform.bin")
with open("waveform.bin", "wb") as fp:
    fp.write(content)
```

---

### `client.comm` &mdash; Raw Bus Transactions (I2C, UART, SPI, Socket)

All byte data is **hex-encoded** on the wire. The client handles
encoding and decoding transparently &mdash; callers work with plain
`bytes` objects. `BusTransactionResponse.received` is always `bytes`.

| Method | Returns | Description |
|--------|---------|-------------|
| `i2c(device_name, address, action, ...)` | `BusTransactionResponse` | I2C bus transaction (Send, Receive, SendReceive, or Scan). |
| `uart(device_name, action, ...)` | `BusTransactionResponse` | UART transaction (Send, Receive, SendReceive, or ClearBuffers). |
| `spi(device_name, action, ...)` | `BusTransactionResponse` | SPI transaction (Send, Receive, or SendReceive). |
| `socket(device_name, action, ...)` | `BusTransactionResponse` | TCP socket transaction (Send, Receive, or SendReceive). |

**I2C parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `device_name` | `str` | Device name as registered in the hardware manager |
| `address` | `int` | I2C 7-bit device address (0&ndash;127) |
| `action` | `BusActions` | `SEND`, `RECEIVE`, `SEND_RECEIVE`, or `SCAN` |
| `data_to_send` | `bytes` | Bytes to transmit (required for Send/SendReceive) |
| `number_of_bytes_to_receive` | `int` | Expected byte count for Receive/SendReceive |
| `max_retries` | `int` | Retry limit on NAK (`-1` = device default) |

```python
from accordionq2.enums import BusActions

# I2C: scan the bus for connected devices
resp = client.comm.i2c("0.ESH10000597.I2C00", address=0x00,
                       action=BusActions.SCAN)
for addr in resp.received:
    print(f"Found device at 0x{addr:02X}")

# I2C: write two bytes to address 0x50
client.comm.i2c("0.ESH10000597.I2C00", address=0x50,
                action=BusActions.SEND,
                data_to_send=bytes([0x00, 0x10]))

# I2C: read 4 bytes from address 0x50
resp = client.comm.i2c("0.ESH10000597.I2C00", address=0x50,
                       action=BusActions.RECEIVE,
                       number_of_bytes_to_receive=4)
print(resp.received.hex())  # e.g. "aabbccdd"

# UART: send a SCPI query and read the response
resp = client.comm.uart("MyUartDevice",
                        action=BusActions.SEND_RECEIVE,
                        data_to_send=b"*IDN?\n",
                        number_of_bytes_to_receive=64,
                        timeout_ms=2000)
print(resp.received.decode("ascii"))

# SPI: full-duplex transfer
resp = client.comm.spi("MySpiDevice",
                       action=BusActions.SEND_RECEIVE,
                       data_to_send=bytes([0xAA, 0xBB]),
                       number_of_bytes_to_receive=2)

# Socket: send a SCPI query over TCP
resp = client.comm.socket("MySocketDevice",
                          action=BusActions.SEND_RECEIVE,
                          host_name="192.168.1.10", port=5025,
                          data_to_send=b"*IDN?\n",
                          number_of_bytes_to_receive=64)
```

---

### `client.numeric_results` &mdash; Fast Numeric Sampling

NumericResult channels perform high-speed acquisition on physical
channels, computing summary statistics (mean, min, max, stdev)
server-side.

| Method | Returns | Description |
|--------|---------|-------------|
| `get_channels()` | `list[NumericResultChannelDto]` | All NumericResult channels with sampling capabilities. |
| `get_targets(channel_net_name)` | `list[str]` | Physical channels that a NumericResult channel can sample. |
| `measure(channel, target, samples, reduced_set)` | `NumericMeasureResultDto` | Trigger an acquisition (result cached server-side). |
| `get_mean(channel_net_name)` | `float` | Mean of the last measurement. |
| `get_min(channel_net_name)` | `float` | Minimum of the last measurement. |
| `get_max(channel_net_name)` | `float` | Maximum of the last measurement. |
| `get_stdev(channel_net_name)` | `float` | Standard deviation of the last measurement. |
| `get_samples(channel_net_name)` | `list[float]` | Raw sample array (only if `reduced_set=False`). |

**Typical workflow:**

```python
# 1. Discover available NumericResult channels
channels = client.numeric_results.get_channels()
for ch in channels:
    print(f"{ch.net_name} (rate={ch.sample_rate} Hz)")

# 2. Check what a channel can sample
targets = client.numeric_results.get_targets(channels[0].net_name)
print("Available targets:", targets)

# 3. Trigger acquisition (result cached server-side)
meta = client.numeric_results.measure(
    channels[0].net_name, targets[0],
    samples=1000, reduced_set=True)
print(f"Acquired {meta.sample_count} samples in {meta.duration}")

# 4. Fetch summary statistics
mean  = client.numeric_results.get_mean(channels[0].net_name)
stdev = client.numeric_results.get_stdev(channels[0].net_name)
print(f"Mean = {mean:.6f}, StdDev = {stdev:.6f}")

# 5. For raw samples, use reduced_set=False
meta = client.numeric_results.measure(
    channels[0].net_name, targets[0],
    samples=100, reduced_set=False)
samples = client.numeric_results.get_samples(channels[0].net_name)
print(f"First 5 samples: {samples[:5]}")
```

---

## Models

All models live in `accordionq2.models`.

| Class | Description |
|-------|-------------|
| `ConnectionStatusDto` | `is_connected` (bool), `last_error` (str or None) |
| `ChannelDto` | Full channel description (18 fields including type, direction, alias, unit, etc.) |
| `ChannelConfigRequest` | Partial-update request &mdash; only non-`None` fields are applied |
| `ChannelLookupRequest` | Identify a channel by `alias` or `net_name` |
| `ModuleSettingsDto` | Module configuration (`name`, `enabled`, `class_name`, `initial_data`, etc.) |
| `PhysicalSystemDto` | Hardware topology (`host`, `mac`, `firmware`, `modules` list) |
| `PhysicalModuleDto` | One hardware slot (`index`, `name`, `product_id`, `revision`, `serial_number`) |
| `AppLicenseDto` | License info (`name`, `key`, `expires`, `type`) |
| `BusTransactionResponse` | `device_name`, `action`, `received` (bytes), `number_of_bytes_received` |
| `NumericResultChannelDto` | `net_name`, `alias`, `possible_target_names`, `sample_rate`, `default_samples` |
| `NumericMeasureResultDto` | `channel_net_name`, `target_net_name`, `sample_count`, `sample_rate`, `reduced_set`, `started`, `stopped`, `duration` |

Response models provide a `from_dict(data)` class method; request models
provide a `to_dict()` instance method.

## Enumerations

All enums live in `accordionq2.enums`.

| Enum | Type | Values |
|------|------|--------|
| `ModuleStatus` | `str, Enum` | `UNKNOWN`, `OK`, `WARNING`, `ERROR`, `DISABLED` |
| `AppTypes` | `str, Enum` | `UNKNOWN`, `SOFTWARE_MODULE`, `HARDWARE_MODULE` |
| `MpioUsageTypes` | `str, Enum` | `UNDEFINED`, `HIDDEN_SYSTEM_CONTROL`, `READ_ONLY_SYSTEM_CONTROL`, `USER_ALLOCATABLE`, `BUS_SIGNAL` |
| `DirectionTypes` | `IntFlag` | `UNDEFINED`, `IN`, `OUT` |
| `BusActions` | `str, Enum` | `UNDEFINED`, `SEND`, `RECEIVE`, `SEND_RECEIVE`, `SCAN`, `BREAK`, `CLEAR_BUFFERS`, `RECONFIGURE` |
| `ChannelTypes` | `IntFlag` | `UNDEFINED`, `ANALOG`, `DIGITAL`, `TEMPERATURE`, `I2C`, `SPI`, `UART`, and many more |

`IntFlag` enums support bitwise operations:

```python
from accordionq2.enums import ChannelTypes, DirectionTypes

combined = ChannelTypes.ANALOG | ChannelTypes.DIGITAL
if ch.channel_type & ChannelTypes.I2C:
    print("I2C channel")

if ch.direction & DirectionTypes.IN:
    print("Input capable")
```

---

## Error Handling

All API errors raise `AccordionQ2ApiError` (importable from the top-level
package).  The exception carries the HTTP status code and the server's error
message:

```python
from accordionq2 import AccordionQ2ApiError

try:
    ch = client.channels.get_channel(alias="does.not.exist")
except AccordionQ2ApiError as e:
    print(f"HTTP {e.status_code}: {e}")
```

---

## Running the Integration Tests

The test suite uses [pytest](https://docs.pytest.org/) and talks to a live
AccordionQ2 device.

```bash
# Install with test dependencies
pip install -e ".[dev]"

# Run all integration tests
pytest tests/ -m integration -v

# Override the default device URL
ACCORDIONQ2_API_URL=http://mydevice:5000 pytest tests/ -m integration
```

The default URL is `http://agent64.local:5000`.

---

## Comparison with the .NET Client

Both clients expose the same API surface with idiomatic naming for their
respective language:

| Concept | .NET (`AccordionQ2Client`) | Python (`AccordionQ2Client`) |
|---------|---------------------------|------------------------------|
| Lifecycle | `IDisposable` / `using` | Context manager / `with` |
| Methods | `GetValueAsync(name)` | `get_value(name)` |
| Concurrency | `async` / `await` | Synchronous (thread-safe) |
| Nullability | `string?` | `None` |
| Config | `ChannelConfigRequest.Enabled = true` | `ChannelConfigRequest(enabled=True)` |
| Enums | `ChannelTypes.Analog` | `ChannelTypes.ANALOG` |
| Errors | `AccordionQ2ApiException` | `AccordionQ2ApiError` |
| Dependencies | Newtonsoft.Json | None (stdlib only) |
| Install | `dotnet add package AccordionQ2.WebApiClient` | `pip install accordionq2` |
| Package | [NuGet](https://www.nuget.org/packages/AccordionQ2.WebApiClient/) | [PyPI](https://pypi.org/project/accordionq2/) |

---

## License

Proprietary &mdash; see your license agreement for details.

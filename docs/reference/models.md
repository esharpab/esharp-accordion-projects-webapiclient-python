# Models

All models live in `accordionq2.models`.

Response models provide a `from_dict(data)` class method for deserialization; request models provide a `to_dict()` instance method for serialization.

> **Immutability:** All response models are decorated with `@dataclass(frozen=True, slots=True)`.
> Fields cannot be modified after construction — create a new instance if you need a different value.
> Request models (`ChannelLookupRequest`, `ChannelConfigRequest`, `ModuleSettingsDto`) are mutable.

## Response Models

### `ConnectionStatusDto`

| Field | Type | Description |
|-------|------|-------------|
| `is_connected` | `bool` | `True` if the API is connected to the hardware manager |
| `last_error` | `str \| None` | Last error message, if any |

### `ChannelDto`

| Field | Type | Description |
|-------|------|-------------|
| `channel_index` | `int` | Physical channel index |
| `index` | `int` | Logical index |
| `enabled` | `bool` | Whether the channel is enabled |
| `usage` | `MpioUsageTypes` | Usage classification |
| `device_name` | `str` | Name of the providing device |
| `channel_type` | `ChannelTypes` | Active channel type flags |
| `channel_type_capability` | `ChannelTypes` | Supported type flags (hardware capability) |
| `alias` | `str` | Human-readable alias |
| `net_name` | `str` | Unique net name |
| `group_name` | `str` | Logical group name |
| `capability` | `DirectionTypes` | Supported direction capability |
| `description` | `str` | Human-readable description |
| `direction` | `DirectionTypes` | Current direction (IN, OUT) |
| `direction_changed` | `bool` | Whether direction was changed from default |
| `default_direction` | `DirectionTypes` | Factory-default direction |
| `unit` | `str` | Unit of measurement |
| `is_virtual` | `bool` | Whether this is a virtual channel |
| `details` | `Mapping[str, Any] \| None` | Read-only fields of the channel's own type, keyed as the WebApi sends them (`"gain"`, `"pullType"`, `"destinationNets"`, ...). `None` for types without any, or older firmware |

### `ModuleSettingsDto`

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Module name |
| `enabled` | `bool` | Whether the module is enabled |
| `class_name` | `str` | Module class name |
| `assembly_path` | `str` | Path to the module assembly |
| `namespace` | `str` | Module namespace |
| `image_name` | `str` | Docker / image name |
| `initial_data` | `dict` | Initial configuration data |

### `PhysicalSystemDto`

| Field | Type | Description |
|-------|------|-------------|
| `host` | `str` | Host name |
| `mac` | `str` | MAC address |
| `firmware` | `str` | Firmware version |
| `eth_ip_v4` | `str` | IPv4 address |
| `eth_ip_v6` | `str` | IPv6 address |
| `modules` | `tuple[PhysicalModuleDto, ...]` | Hardware modules (immutable) |
| `network_interfaces` | `dict` | All network interfaces |

### `PhysicalModuleDto`

| Field | Type | Description |
|-------|------|-------------|
| `index` | `int` | Slot index |
| `name` | `str` | Module name |
| `product_id` | `str` | Product identifier |
| `revision` | `int` | Hardware revision |
| `serial_number` | `str` | Serial number |

### `AppLicenseDto`

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Application name |
| `key` | `str` | License key |
| `expires` | `str` | Expiration date |
| `type` | `AppTypes` | Application type |

### `BusTransactionResponse`

| Field | Type | Description |
|-------|------|-------------|
| `device_name` | `str` | Device used for the transaction |
| `action` | `str` | Action performed |
| `received` | `bytes` | Received data (decoded from hex) |
| `number_of_bytes_received` | `int` | Number of bytes received |

### `NumericResultChannelDto`

| Field | Type | Description |
|-------|------|-------------|
| `net_name` | `str` | Net name of the NumericResult channel |
| `alias` | `str` | Alias of the channel |
| `possible_target_names` | `tuple[str, ...]` | Physical channels this channel can sample (immutable) |
| `sample_rate` | `int` | Sampling rate in Hz |
| `default_samples` | `int` | Default number of samples |

### `NumericMeasureResultDto`

| Field | Type | Description |
|-------|------|-------------|
| `channel_net_name` | `str` | NumericResult channel used |
| `target_net_name` | `str` | Physical channel sampled |
| `sample_count` | `int` | Number of samples acquired |
| `sample_rate` | `int` | Actual sampling rate in Hz |
| `reduced_set` | `bool` | Whether raw samples were discarded |
| `started` | `str` | Acquisition start timestamp |
| `stopped` | `str` | Acquisition stop timestamp |
| `duration` | `str` | Acquisition duration |

### `CalibrationChannelDto`

| Field | Type | Description |
|-------|------|-------------|
| `net_name` | `str` | Hardware net name of the Calibration channel |
| `alias` | `str` | Human-readable alias |

### `CalibrationTableDto`

| Field | Type | Description |
|-------|------|-------------|
| `product_id` | `str` | Product identifier |
| `revision` | `str` | Hardware revision |
| `serial_number` | `str` | Unit serial number |
| `cal_data` | `tuple[CalibrationRowDto, ...]` | Calibration rows (immutable) |

### `CalibrationRowDto`

| Field | Type | Description |
|-------|------|-------------|
| `key` | `str` | Row identifier (e.g. channel name or composite field) |
| `gain` | `float` | Gain correction factor |
| `offset` | `float` | Offset correction value |

## Request Models

### `ChannelConfigRequest`

Partial-update request &mdash; only non-`None` fields are applied. See [Channels](../api/channels.md) for usage.

`details` (`dict[str, Any] | None`) changes fields of the channel's own type, with the same keys as `ChannelDto.details`, e.g. `{"gain": 2.0}` or `{"pullType": "Up"}`. A key the type can't configure, or a bad value, is refused with an `AccordionQ2ApiError` (400) naming it.

```python
client.channels.configure(ChannelConfigRequest(net_name="0.2.ESH10000560.MEAS2_VPP", details={"gain": 2.0}))
```

### `InstrumentDto`

| Field | Type | Description |
|-------|------|-------------|
| `net_name` | `str` | Net name of the Instrument channel |
| `alias` | `str` | Alias of the Instrument channel |
| `group_name` | `str` | Group, e.g. `"CH1"` for one output of a two-output supply |
| `description` | `str` | Description |
| `instrument_name` | `str` | Instrument name; several outputs of one module share it |
| `type` | `str` | Instrument type, e.g. `"PowerSupply"` |
| `function_map` | `Mapping[str, str]` | Capability (`OUTPUT_VOLTAGE`, `OUTPUT_ENABLE`, ...) to the net name of the channel behind it |

### `ChannelLookupRequest`

Identify a channel by `alias` or `net_name`.

# Models

All models live in `accordionq2.models`.

Response models provide a `from_dict(data)` class method for deserialization; request models provide a `to_dict()` instance method for serialization.

## Response Models

### `ConnectionStatusDto`

| Field | Type | Description |
|-------|------|-------------|
| `is_connected` | `bool` | `True` if the API is connected to the hardware manager |
| `last_error` | `str` or `None` | Last error message, if any |

### `ChannelDto`

Full channel description with 18 fields including type, direction, alias, unit, and more.

| Field | Type | Description |
|-------|------|-------------|
| `net_name` | `str` | Unique net name |
| `alias` | `str` | Human-readable alias |
| `channel_type` | `ChannelTypes` | Channel type flags |
| `direction` | `DirectionTypes` | Direction flags (IN, OUT) |
| `enabled` | `bool` | Whether the channel is enabled |
| `value` | `str` | Current value |
| `unit` | `str` | Unit of measurement |
| `description` | `str` | Human-readable description |
| `group_name` | `str` | Logical group name |
| `device_name` | `str` | Name of the providing device |
| `usage_type` | `MpioUsageTypes` | Usage classification |
| ... | ... | Additional fields |

### `ModuleSettingsDto`

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Module name |
| `enabled` | `bool` | Whether the module is enabled |
| `class_name` | `str` | Module class name |
| `initial_data` | `str` | Initial configuration data |

### `PhysicalSystemDto`

| Field | Type | Description |
|-------|------|-------------|
| `host` | `str` | Host name |
| `mac` | `str` | MAC address |
| `firmware` | `str` | Firmware version |
| `modules` | `list[PhysicalModuleDto]` | List of hardware modules |

### `PhysicalModuleDto`

| Field | Type | Description |
|-------|------|-------------|
| `index` | `int` | Slot index |
| `name` | `str` | Module name |
| `product_id` | `str` | Product identifier |
| `revision` | `str` | Hardware revision |
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
| `possible_target_names` | `list[str]` | Physical channels this channel can sample |
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

## Request Models

### `ChannelConfigRequest`

Partial-update request &mdash; only non-`None` fields are applied. See [Channels](../api/channels.md) for usage.

### `ChannelLookupRequest`

Identify a channel by `alias` or `net_name`.

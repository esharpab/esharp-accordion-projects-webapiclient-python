# Channels

Channels represent multi-purpose I/O pins (analog, digital, I2C, SPI, etc.).

## Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_all()` | `list[ChannelDto]` | Return every configured channel. |
| `get_channel(alias=, net_name=)` | `ChannelDto` | Look up one channel by alias or net name. |
| `configure(config)` | &mdash; | Partial-update a single channel. |
| `configure_many(configs)` | &mdash; | Partial-update multiple channels. |

## Examples

### Listing Channels

```python
for ch in client.channels.get_all():
    print(f"  {ch.alias}: type={ch.channel_type}, unit={ch.unit}")
```

### Looking Up a Channel

```python
# By alias
ch = client.channels.get_channel(alias="0.1.ESH10000158.MON_3V3")
print(f"Type: {ch.channel_type}, Direction: {ch.direction}")

# By net name
ch = client.channels.get_channel(net_name="MPIO00")
```

### Checking Channel Capabilities

```python
from accordionq2.enums import ChannelTypes, DirectionTypes

if ch.channel_type & ChannelTypes.ANALOG:
    print("This is an analog channel")

if ch.direction & DirectionTypes.IN:
    print("Input capable")
```

### Configuring Channels

Channel configuration uses **partial updates** &mdash; only non-`None` fields in `ChannelConfigRequest` are applied; everything else is left unchanged.

```python
from accordionq2.models import ChannelConfigRequest

# Update a single property
client.channels.configure(ChannelConfigRequest(
    alias="0.1.ESH10000158.MON_3V3",
    description="Main 3.3 V rail monitor",
    unit="V",
))

# Batch configure
client.channels.configure_many([
    ChannelConfigRequest(net_name="MPIO00", enabled=True, direction=DirectionTypes.IN),
    ChannelConfigRequest(net_name="MPIO01", enabled=True, direction=DirectionTypes.OUT, value=0.0),
])
```

### Switching an MPIO to an Output at a Known Level

`value` sets the output's value in the same configure as `direction`, `channel_type` and `details`
(firmware 7.0.5 and later), so the pin never drives another level in between. Without it, a channel
that becomes an output (from an input, or as another type) starts at its default value
(`details["defaultValue"]`, 0 V / False unless set), never at the last value read while it was an
input. One that stays an output keeps its present value unless `value` is given.

```python
from accordionq2.enums import ChannelTypes, DirectionTypes

# Analog: 0.8 V, in the channel's units at the gain and offset the request leaves
client.channels.configure(ChannelConfigRequest(
    net_name="0.3.ESH10000121.MPIO04", direction=DirectionTypes.OUT, value=0.8))

# PseudoDigital: type, levels and state together
client.channels.configure(ChannelConfigRequest(
    net_name="0.3.ESH10000121.MPIO05",
    direction=DirectionTypes.OUT,
    channel_type=ChannelTypes.PSEUDO_DIGITAL,
    details={"vl": 0.5, "vh": 3.0},
    value=False,
))
```

- `value` goes out as a string, as `resources.set_value` takes it: a bool as `"True"`/`"False"`, a
  number (an int, a float or a numpy scalar) as an invariant float, a string as it is.
- The station refuses (400) a value for a channel the request leaves an input, one of a type that
  takes no value (Ratiometric, NumericResult, ...), one that doesn't parse, and one the module can't
  drive.
- **Firmware older than 7.0.5 ignores `value`** (200 OK, and the output starts at its last
  reading). Check the station's firmware version before relying on it.
- In `configure_many`, each channel is configured as a whole or not at all: a channel the module
  refuses keeps its old configuration and the others are still applied.

### `ChannelConfigRequest` Fields

| Field | Type | Description |
|-------|------|-------------|
| `net_name` | `str?` | Net name for lookup (takes priority over `alias`) |
| `alias` | `str?` | Alias for lookup, or new alias when `net_name` is also set |
| `enabled` | `bool?` | Enable or disable the channel |
| `direction` | `DirectionTypes?` | `IN` or `OUT` &mdash; must be within the channel's capability flags |
| `channel_type` | `ChannelTypes?` | One active channel type &mdash; must be within the channel's type capability flags |
| `description` | `str?` | Human-readable description |
| `unit` | `str?` | Unit of measurement (e.g. `"V"`, `"°C"`, `"A"`) |
| `group_name` | `str?` | Logical group name |
| `device_name` | `str?` | Name of the providing device |
| `details` | `dict?` | Type-specific fields to change, e.g. `{"gain": 2.0}` |
| `value` | `str \| float \| int \| bool?` | The output's value, applied in the same configure (firmware 7.0.5+; see above) |

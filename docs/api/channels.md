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
    ChannelConfigRequest(net_name="MPIO00", enabled=True, direction="IN"),
    ChannelConfigRequest(net_name="MPIO01", enabled=True, direction="OUT"),
])
```

### `ChannelConfigRequest` Fields

| Field | Type | Description |
|-------|------|-------------|
| `net_name` | `str?` | Net name for lookup (takes priority over `alias`) |
| `alias` | `str?` | Alias for lookup, or new alias when `net_name` is also set |
| `enabled` | `bool?` | Enable or disable the channel |
| `direction` | `str?` | `"IN"` or `"OUT"` &mdash; must be within the channel's capability flags |
| `channel_type` | `str?` | Active channel type &mdash; must be within the channel's type capability flags |
| `description` | `str?` | Human-readable description |
| `unit` | `str?` | Unit of measurement (e.g. `"V"`, `"°C"`, `"A"`) |
| `group_name` | `str?` | Logical group name |
| `device_name` | `str?` | Name of the providing device |

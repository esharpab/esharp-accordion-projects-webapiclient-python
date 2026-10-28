# Channels

Channels represent multi-purpose I/O pins (analog, digital, I2C, SPI, etc.).

## Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_all()` | `list[ChannelDto]` | Return every configured channel. |
| `get_channel(alias=, net_name=)` | `ChannelDto` | Look up one channel by alias or net name. |
| `configure(config)` | &mdash; | Partial-update a single channel. |
| `configure_many(configs)` | &mdash; | Partial-update multiple channels. |
| `upload_bytestream(name, image, target="sram", file_name=None, force=False)` | `ByteStreamStatus` | Send a file to a ByteStream file channel (MicroHAPS `JTAG.FPGA_IMAGE`: an FPGA image); firmware 7.0.5. |
| `bytestream_status(name)` | `ByteStreamStatus` | The load's state, progress and result, and the last image's name, size and SHA-256. |
| `wait_bytestream(name, timeout=120, poll=0.5)` | `ByteStreamStatus` | Poll the status until `done` or `failed`. |
| `load_fpga_image(name, image, target="sram", timeout=120)` | `ByteStreamStatus` | Upload and wait; raises `ByteStreamLoadError` when the load fails. |

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

### Loading an FPGA image (firmware 7.0.5)

MicroHAPS has a ByteStream channel `JTAG.FPGA_IMAGE` (Unit `file:FPGA image`). It takes a file, not a value: the
client sends the file to `POST /api/channels/bytestream`, and the station checks it and loads it into the KU5P's SRAM
with openFPGALoader, without Vivado and whether or not the XVC server is on. `resources.set_values` on this channel is
refused (400). `image` is the bytes, an open binary file or a path; a file is sent as it is read, not read whole.
Loading needs the Operator role, as switching `XVC_ENABLE` on does: the station checks the part (XCKU5P-FFVB676) and
the IDCODE, not what the design drives. Writing the configuration flash is not in 7.0.5 (`target="flash"` gives 501).

```python
from accordionq2 import AccordionQ2Client, ByteStreamLoadError

with AccordionQ2Client("http://station:5000", api_key="acc_...") as client:
    try:
        status = client.channels.load_fpga_image("1.MicroHAPS.JTAG.FPGA_IMAGE", "hci_mig_top.bit")
    except ByteStreamLoadError as error:
        print("failed:", error.status.message)   # e.g. "...is for xcku3p-ffva676-1-e, not the XCKU5P..."
        raise
    print(status.image.file_name, status.image.sha256, status.image.duration_ms, "ms")
    client.resources.set_value("1.MicroHAPS.HCI.Scan", "True")   # the new design's HCI devices
```

| Status | When |
|--------|------|
| 400 | Not a file channel, a bad file name or extension, or the station refused the file (another part, a partial bitstream, not a bitstream) |
| 409 | A load, a POWER cycle or a PROGRAM pulse is running; the board is off; Vivado is connected to XVC (pass `force=True` to cut it) |
| 413 | Over 64 MB |
| 423 | Another client holds the lease |
| 501 | `target="flash"` |
| 504 | The station didn't take the file in time: read the status, the load may still start |

`ByteStreamStatus`: `state` (`idle`, `validating`, `loading`, `waitingDone`, `done`, `failed`), `progress` (0 to 100),
`phase`, `message`, `accept`, `targets`, `max_bytes`, and `image` (`ByteStreamImage`: `file_name`, `size`, `sha256`,
`format`, `design`, `part`, `built`, `started`, `finished`, `duration_ms`, `result`, `loaded`, `replaced`,
`design_keys`). `loaded` turns `False` once a POWER cycle or a PROGRAM_B pulse has put the flash design back;
`design_keys` is the DesignID device's `Info.Keys` from the first `HCI.Scan` after the load.

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

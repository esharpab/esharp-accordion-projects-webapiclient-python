# Calibration

Calibration channels carry a `CalibrationTable` encoded as a Base64 binary payload on the wire.
The server transparently decodes and encodes that payload, so you always work with plain
[`CalibrationTableDto`](../reference/models.md#calibrationtabledto) objects.

Both **NetName** and **Alias** are accepted wherever a channel name is required.

## Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_channels()` | `list[CalibrationChannelDto]` | All Calibration channels. |
| `get_table(channel_name)` | `CalibrationTableDto` | Read and decode the CalibrationTable from a channel. |
| `set_table(channel_name, table)` | `None` | Encode and write a CalibrationTable to a channel. |

## Typical Workflow

```python
from accordionq2 import AccordionQ2Client, CalibrationRowDto
import dataclasses

with AccordionQ2Client("http://agent64.local:5000") as client:

    # 1. Discover available Calibration channels
    channels = client.calibration.get_channels()
    for ch in channels:
        print(f"{ch.net_name}  ({ch.alias})")

    # 2. Read the current table (by NetName or Alias)
    table = client.calibration.get_table(channels[0].net_name)
    print(f"Product: {table.product_id}  Rev: {table.revision}  S/N: {table.serial_number}")
    for row in table.cal_data:
        print(f"  {row.key:<40} gain={row.gain:.6f}  offset={row.offset:.6f}")

    # 3. Modify a row and write back
    new_rows = tuple(
        dataclasses.replace(row, gain=1.0012, offset=0.001) if row.key == "ADC0" else row
        for row in table.cal_data
    )
    updated = dataclasses.replace(table, cal_data=new_rows)
    client.calibration.set_table(channels[0].net_name, updated)
```

## Alias Support

The channel can be addressed by either its NetName or its friendly Alias:

```python
# These two calls are equivalent
t1 = client.calibration.get_table("0.8.ESH10000590.CAL0")
t2 = client.calibration.get_table("FRONT AIR CALIBRATION")
```

## Models

### `CalibrationChannelDto`

| Field | Type | Description |
|-------|------|-------------|
| `net_name` | `str` | Hardware net name of the channel |
| `alias` | `str` | Human-readable alias |

### `CalibrationTableDto`

| Field | Type | Description |
|-------|------|-------------|
| `product_id` | `str` | Product identifier |
| `revision` | `str` | Hardware revision |
| `serial_number` | `str` | Unit serial number |
| `cal_data` | `tuple[CalibrationRowDto, ...]` | Calibration rows |

### `CalibrationRowDto`

| Field | Type | Description |
|-------|------|-------------|
| `key` | `str` | Row identifier (e.g. channel name or composite field) |
| `gain` | `float` | Gain correction factor |
| `offset` | `float` | Offset correction value |

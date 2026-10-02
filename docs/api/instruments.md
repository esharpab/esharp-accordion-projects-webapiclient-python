# Instruments

The station's instruments, such as the outputs of a power-supply module. Each one is an Instrument channel whose function map names the ordinary channel behind each capability, so a script can find "the voltage setpoint of CH1" without hard-coding net names.

## Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_all()` | `list[InstrumentDto]` | Every Instrument channel with its type and function map |

## Example

```python
for instrument in client.instruments.get_all():
    if instrument.type != "PowerSupply":
        continue
    voltage = instrument.function_map.get("OUTPUT_VOLTAGE")
    enable = instrument.function_map.get("OUTPUT_ENABLE")
    print(instrument.instrument_name, instrument.group_name, voltage, enable)

# e.g. Mini PSU CH1 0.4.ESH10000662.VSET1 0.4.ESH10000662.OUTPUT_ENABLE_CH1
```

Every key of the function map is optional; check for it before using it. Set the values through `client.resources` as for any other channel.

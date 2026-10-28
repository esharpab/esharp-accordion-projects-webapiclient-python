# Resources

Resources represent readable/writable hardware values such as voltages, temperatures, and firmware revisions. They are identified by a dotted name string (e.g. `"TempRegulator.CPU_TEMP"`).

> **Alias support:** Both the **NetName** (e.g. `"0.23.ESH10000517.READ_TEMPERATURE"`) and the channel **Alias** (e.g. `"FRONT_AIR READ TEMPERATURE"`) are accepted interchangeably by all read, write, and transact methods.

## Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_names()` | `list[str]` | List all available resource names. |
| `get_value(name)` | `str` | Read the current value of a single resource. |
| `set_value(name, value)` | &mdash; | Write a value to a single resource. |
| `get_values(names)` | `dict[str, str]` | Read multiple resources in one call. |
| `read_cached(names, max_age_ms=0)` | `CachedValues` | Read multiple resources from the WebApi's cache alone, never from the hardware; lists the names it had no value for. |
| `set_values(resources)` | &mdash; | Write multiple resources in one call. |
| `transact(name, value)` | `str` | Write then read (command/response pattern). |

## Examples

### Single Read/Write

```python
# Read a single value
voltage = client.resources.get_value("0.1.ESH10000158.MON_3V3")
print(f"Voltage: {voltage} V")

# Write a value
client.resources.set_value("MyOutput", "2.5")
```

### Batch Operations

```python
# Batch read
values = client.resources.get_values([
    "TempRegulator.CPU_TEMP",
    "Engine.Uptime",
])
for name, val in values.items():
    print(f"{name} = {val}")

# Batch write
client.resources.set_values({
    "Output1": "1.0",
    "Output2": "2.0",
})
```

### Cache-only Reads

`read_cached` answers from the WebApi's value cache alone: the station never reads the hardware for it, and the [lease](lease.md) never refuses it. Use it where a read must not disturb anything, for example a remote reader looking at a station while a test runs: reading a channel whose `readEffect` is `Disturbing` (most of them) can switch a mux or reset a peak buffer.

```python
r = client.resources.read_cached([
    "0.4.ESH10000662.VMON1",
    "0.4.ESH10000662.PEAK1",
    "Ports.UART.ttyAMA0",
], max_age_ms=5000)

for name, value in r.values.items():
    print(f"{name} = {value} ({r.ages_ms[name]:.0f} ms old)")
for name in r.not_cached:
    print(f"{name}: not cached")
```

- A name whose cached value is at most `max_age_ms` old is in `values` and `ages_ms`. Any other name is in `not_cached` and in neither of the others. `max_age_ms=0` (the default) takes a cached value of any age.
- Channels whose reads use data up (bus receives, byte streams, numeric results) are always in `not_cached`.
- A name no channel has raises `AccordionQ2ApiError` 400, as the other reads do.
- The first call checks `GET /api/capabilities` for `CapabilitiesDto.VALUES_CACHE_ONLY` (firmware 7.0.5 or later). An older WebApi would ignore `cacheOnly` and read the hardware, so without the feature the call raises `AccordionQ2NotSupportedError` and asks for no values. It raises it too when an answer has no `notCached`.

`CachedValues` is a frozen dataclass: `values` (`dict[str, str]`), `ages_ms` (`dict[str, float]`) and `not_cached` (`tuple[str, ...]`, in the order asked, empty when every name was cached).

### Write-then-Read Transaction

Useful for command/response patterns such as EEPROM or register access:

```python
response = client.resources.transact("Eeprom.Read", "0x0010")
print(f"Register value: {response}")
```

# Resources

Resources represent readable/writable hardware values such as voltages, temperatures, and firmware revisions. They are identified by a dotted name string (e.g. `"TempRegulator.CPU_TEMP"`).

## Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_names()` | `list[str]` | List all available resource names. |
| `get_value(name)` | `str` | Read the current value of a single resource. |
| `set_value(name, value)` | &mdash; | Write a value to a single resource. |
| `get_values(names)` | `dict[str, str]` | Read multiple resources in one call. |
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

### Write-then-Read Transaction

Useful for command/response patterns such as EEPROM or register access:

```python
response = client.resources.transact("Eeprom.Read", "0x0010")
print(f"Register value: {response}")
```

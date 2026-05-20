# Application

Application lifecycle management and configuration file operations.

## Methods

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
| `get_system_log(tail=100)` | `list[str]` | Last `tail` lines of the system log (hw.log). Pass `0` for the full log. |

## Examples

### Checking Application Status

```python
from accordionq2.enums import ModuleStatus

status = client.application.get_status()
if status == ModuleStatus.OK:
    print("Application is running normally")
elif status == ModuleStatus.ERROR:
    print("Application has an error")
```

### Configuration File Round-Trip

```python
# Download config, back it up, then reload
data = client.application.download_config_file("factory.cfg")
client.application.upload_config_file("factory_backup.cfg", data)
client.application.load_config_file("factory.cfg")
```

### Listing Configuration Files

```python
print("Available configs:")
for f in client.application.list_config_files():
    print(f"  {f}")

print("Currently loaded:")
for f in client.application.get_loaded_config_files():
    print(f"  {f}")
```

### Reading the System Log

```python
# Get the last 100 lines (default)
for line in client.application.get_system_log():
    print(line)

# Get the last 200 lines
recent = client.application.get_system_log(tail=200)

# Get the entire log
full = client.application.get_system_log(tail=0)
```
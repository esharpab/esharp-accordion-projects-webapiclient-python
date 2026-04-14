# Modules

Manage hardware and software modules, query the hardware topology, and view application licenses.

## Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_all()` | `list[ModuleSettingsDto]` | All modules (loaded and unloaded). |
| `get_loaded()` | `list[ModuleSettingsDto]` | Currently loaded modules only. |
| `load(module)` | &mdash; | Load a module. |
| `unload(module)` | &mdash; | Unload a module. |
| `configure(module)` | &mdash; | Update module configuration. |
| `get_physical_system()` | `PhysicalSystemDto` | Hardware topology (host, MAC, modules). |
| `get_licensed_apps()` | `list[AppLicenseDto]` | Licensed applications. |
| `get_all_apps()` | `list[AppLicenseDto]` | All applications. |

## Examples

### Hardware Topology

```python
system = client.modules.get_physical_system()
print(f"Host: {system.host}, MAC: {system.mac}")
for mod in system.modules:
    print(f"  Slot {mod.index}: {mod.name} ({mod.product_id})")
```

### Loaded Modules

```python
for m in client.modules.get_loaded():
    print(f"  {m.name} (enabled={m.enabled})")
```

### License Information

```python
for app in client.modules.get_licensed_apps():
    print(f"  {app.name}: key={app.key}, expires={app.expires}")
```

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
| `get_present()` | `list[ModulePresenceDto]` | Every module present, as the Web UI's status bar lists them: hardware by slot, then software by name (`kind`, `address`, `prefix`, `name`, ...). Firmware with stable module names; 404 before. |
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

## The modules present

On firmware with stable module names a software module's net names start with its configured name
(`MicroHAPS.HCI.Scan`, `Drummer.Target.Status`), a hardware module's with its slot path and product
(`0.2.ESH10000560.CH1`). `prefix` is that start:

```python
present = client.modules.get_present()
channels = client.channels.get_all()
for m in present:
    count = sum(1 for c in channels if c.net_name.lower().startswith(m.prefix.lower() + "."))
    print(m.address, m.name, m.class_name or m.product_id, count)
```

`ModulePresenceDto`: `kind` (`"hardware"` or `"software"`, `is_hardware`), `address` (`"0.2"`, `"MicroHAPS"`),
`prefix`, `name`, and for hardware `product_id`, `revision`, `serial_number`; for software `class_name`.

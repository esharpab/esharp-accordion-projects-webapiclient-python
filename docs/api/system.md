# System

The station's services, reboot and clock, and in `client.system.boot` the hardware app's start-up configuration (boot.config).

The WebApi runs these on the Pi itself. Reads are open to anyone; changes are writes, so while another client holds the [lease](lease.md) they raise 423. Off a station (a WebApi on a development PC) the services, reboot and clock calls raise 501.

## Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_services()` | `list[ServiceStatus]` | The hardware app, the WebApi and the dashboard, with their state. |
| `service_action(service_id, action)` | &mdash; | `start`, `stop`, `restart`, `enable` or `disable` a service. Returns at once, without waiting for the job. |
| `reboot()` | &mdash; | Reboot the Pi a second after answering. |
| `get_clock()` | `ClockStatus` | The Pi's clock. |
| `set_clock(utc=None, force=False)` | `ClockStatus` | Set the Pi's clock, to this computer's when `utc` is `None`. |
| `boot` | `BootGroup` | The start-up configuration; see [below](#start-up-configuration-bootconfig). |

## Services

The services are `hardware` (the hardware app), `webapi` (the WebApi and its GUI) and `dashboard` (Node-RED). `enable` and `disable` turn starting at boot on or off; `start`, `stop` and `restart` return straight away, so follow `get_services()` to see the result.

The service marked `self` is the WebApi answering: it can be restarted through itself but not stopped. Restarting it drops every client's connection, and the event stream, for a few seconds.

Errors: 404 for an unknown service, 400 for an action the service can't take, 500 with systemd's message.

```python
for s in client.system.get_services():
    print(f"{s.id:<10} {s.unit:<28} {s.active_state}/{s.sub_state}  boot={s.enabled}")

client.system.service_action("hardware", "restart")
```

## Reboot

```python
client.system.reboot()   # the Pi is back after about a minute
```

## Clock

An isolated station has no time server, so this computer's clock is usually the best source. A clock a time server keeps (`ntp_synchronized`) is refused with 409 unless `force=True`. A naive `datetime` is taken as UTC.

```python
from datetime import datetime, timezone

clock = client.system.get_clock()
print(clock.utc, clock.time_zone, "NTP synchronised:", clock.ntp_synchronized)

# Set it to this computer's clock
client.system.set_clock()

# Or to a given time
client.system.set_clock(datetime(2026, 10, 3, 8, 15, tzinfo=timezone.utc), force=True)
```

## Start-up configuration (boot.config)

`client.system.boot` reads and edits the hardware app's `hw/config/boot.config`, which says what the hardware app applies when it starts. This is how an alias file activated today is still active after a restart.

When the hardware app starts it applies the `services` always, and only when `enabled` is `True` also the Wi-Fi, the static addresses and the USB ports; after the engine starts, the `modules` and then the `alias_files` in order. The engine loads the modules and alias files again on every reset.

**Changes apply at the hardware app's next start** (the alias files and modules also at the next reset), not at once.

| Method | Returns | Description |
|--------|---------|-------------|
| `get()` | `BootConfig` | boot.config, without the Wi-Fi password. Raises 404 when the Pi has none yet (the hardware app creates it on its first start). |
| `set_startup(enabled=None, alias_files=None)` | `BootConfig` | Turn applying boot.config on or off, and/or replace the alias files. `None` leaves either as it is. |
| `update(*, if_modified=None, enabled=None, description=None, alias_files=None, modules=None, ip_configurations=None, wifi=None, wifi_password=..., disable_usb_ports=None, enable_media_devices=None, services=None)` | `BootConfig` | Edit boot.config: each section given replaces the file's; the rest stays. Keyword arguments only. |

Both changes answer with the file as `get()` shows it.

### Rules for `update()`

- **`if_modified`:** pass the `modified` you read. If the file has changed since, the call raises 409 and nothing is written, instead of overwriting someone else's edit; read it again and redo your change.
- **Wi-Fi password:** never returned, only `wifi.password_set`. The saved password stays unless `wifi_password` is given; `wifi_password=""` clears it, otherwise it is 8 to 63 characters. `wifi_password` needs `wifi`, since the Wi-Fi section is sent whole (`ValueError` otherwise).
- **Protected services:** `protected_services` lists the hardware app's and the WebApi's own units. Turning one of them off raises 400: the hardware app stops and disables a service marked off at every start, which would leave SSH as the only way back in.
- **Checked first:** everything is checked before anything is written. A bad address, interface name, unit name, module or alias file raises 400. An alias file must be a plain file name in the alias folder.
- A module keeps what isn't shown (its image name and initial data) when its name stays; an empty `namespace` is taken from `class_name`.

### Examples

#### Alias Files Loaded at Start-up

```python
from accordionq2 import BootAliasFile

boot = client.system.boot.get()
print("Applied at start:", boot.enabled)
for a in boot.alias_files:
    print(f"  {a.order}: {a.path} (enabled={a.enabled})")

# Load station.csv, then limits.csv, at every start and reset
client.system.boot.set_startup(
    enabled=True,
    alias_files=[BootAliasFile("station.csv"), BootAliasFile("limits.csv")],
)
```

The alias files load in list order; `order` is ignored when sending.

#### Editing Without Overwriting Another Edit

```python
from accordionq2 import AccordionQ2ApiError, BootAddress

boot = client.system.boot.get()
try:
    client.system.boot.update(
        if_modified=boot.modified,
        description="Line 3",
        ip_configurations=[BootAddress("eth0", "192.168.0.222/24", enabled=True)],
    )
except AccordionQ2ApiError as e:
    if e.status_code == 409:
        print("boot.config changed since it was read; read it again")
    else:
        raise
```

#### Wi-Fi

```python
from accordionq2 import BootWifi

# Turn Wi-Fi on with a new password
client.system.boot.update(wifi=BootWifi(True, "factory-net", False), wifi_password="s3cret-pass")

# Change the SSID and keep the saved password
client.system.boot.update(wifi=BootWifi(True, "factory-net-2", True))

# Clear the password
client.system.boot.update(wifi=BootWifi(False, "", False), wifi_password="")
```

`BootWifi.password_set` is ignored when sending.

## Models

### `ServiceStatus`

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | `hardware`, `webapi` or `dashboard` |
| `unit` | `str` | The systemd unit, e.g. `accordion.service` |
| `description` | `str` | The unit's description |
| `installed` | `bool` | `False` when the Pi doesn't have the unit |
| `active_state` | `str` | systemd's state: `active`, `inactive`, `failed`, `activating`, `deactivating` |
| `sub_state` | `str` | systemd's detail: `running`, `dead`, `exited` and so on |
| `enabled` | `bool` | Starts at boot |
| `since` | `str` or `None` | When it last became active (ISO 8601) |
| `self` | `bool` | The WebApi answering: can be restarted but not stopped |
| `actions` | `tuple[str, ...]` | What it can be asked for |

### `ClockStatus`

| Field | Type | Description |
|-------|------|-------------|
| `utc` | `str` | The Pi's time when it answered (ISO 8601) |
| `time_zone` | `str` | e.g. `Etc/UTC` |
| `ntp_enabled` | `bool` | A time server is configured |
| `ntp_synchronized` | `bool` | A time server keeps the clock; setting it then needs `force` |

### `BootConfig`

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | `bool` | Apply boot.config at start; when `False` only `services` apply |
| `modified` | `str` | When the file was last written (ISO 8601); pass it back as `if_modified` |
| `description` | `str` or `None` | Free text |
| `wifi` | `BootWifi` | The Wi-Fi set at start-up |
| `disable_usb_ports` | `bool` | Turn the USB ports off at start-up |
| `enable_media_devices` | `bool` | Enable media devices |
| `alias_files` | `tuple[BootAliasFile, ...]` | Loaded after the engine starts, and on every reset, in order |
| `modules` | `tuple[BootModule, ...]` | Modules loaded at start-up |
| `ip_configurations` | `tuple[BootAddress, ...]` | Static addresses beside DHCP |
| `services` | `tuple[BootService, ...]` | Services applied at every start, even with `enabled` off |
| `protected_services` | `tuple[str, ...]` | Units that can't be turned off here |

### `BootAliasFile`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `path` | `str` | &mdash; | A file name in the alias folder, e.g. `station.csv` |
| `enabled` | `bool` | `True` | Load it |
| `order` | `int` | `0` | Load order (read only; the list order is used when sending) |

### `BootModule`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | &mdash; | Module name |
| `assembly_path` | `str` | `""` | e.g. `additional/Snowball.dll` |
| `class_name` | `str` | `""` | Full class name |
| `namespace` | `str` | `""` | Empty when sent: taken from `class_name` |
| `enabled` | `bool` | `False` | Load it |

### `BootAddress`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `interface` | `str` | &mdash; | e.g. `eth0` |
| `static_ip` | `str` | `""` | IPv4 with an optional prefix length, e.g. `192.168.0.222/24` |
| `enabled` | `bool` | `False` | Apply it |

### `BootService`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | &mdash; | Display name |
| `service_file` | `str` | &mdash; | The systemd unit, with or without `.service` |
| `enabled` | `bool` | `True` | On: enabled and started at every start. Off: stopped and disabled |

### `BootWifi`

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | `bool` | Wi-Fi on at start-up |
| `ssid` | `str` | Network name (at most 32 bytes; required when enabled) |
| `password_set` | `bool` | A password is saved; ignored when sending |

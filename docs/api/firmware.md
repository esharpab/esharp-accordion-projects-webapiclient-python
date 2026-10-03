# Firmware

Firmware updates through the WebApi: list the releases, choose where the station looks for them, send it a package, install, and follow the update.

A station looks for releases at the E-Sharp deployment by default, or at another http(s) address or a folder on the Pi (a USB stick, a mounted share). A station without internet can be updated from a package on your computer with `install_package(path)`.

!!! important "Only releases signed by E-Sharp"
    The station installs only releases signed by E-Sharp. The signature is checked on the station before anything is unpacked, whichever way the package arrives: downloaded, from a folder on the Pi, or uploaded. No client can skip the check. An unsigned or altered package is refused: `upload_package()` and `install_package()` raise `AccordionQ2ApiError` with status 400, and an update from the source ends in `failed` with the reason in `message`.

**Minimum version.** The station installs nothing older than its minimum version, 6.0.0 (`FirmwareState.minimum_version`): earlier releases have no browser GUI or update API. They are still listed, with `installable=False`, and installing or uploading one raises 400 naming the minimum. An older version at or above the minimum, or the same version again, may be installed.

**Installing restarts the hardware app and the WebApi**, so every client loses the station, the API and the event stream for a minute or two. `wait_for_update()` and `install()` keep polling through the dropped connections until the update has ended. If the new version doesn't stay running, the station puts the old one back (`rolledBack`).

Changes are writes, so while another client holds the [lease](lease.md) they raise 423. Off a station (a WebApi on a development PC) `supported` is `False` and installing raises 501.

## Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_state()` | `FirmwareState` | The installed version, the release source, the minimum version and how the last update went. |
| `get_releases(include_beta=False)` | `FirmwareReleases` | The source's releases, newest first. Revoked releases are left out, beta ones unless `include_beta=True`. Packages only the station's cache has (uploaded ones) are listed too. |
| `set_source(location)` | `FirmwareSource` | Where the station looks for releases: an http(s) address or an absolute folder on the Pi. `None` goes back to the E-Sharp deployment. |
| `start_update(version, include_beta=False)` | `FirmwareUpdateStatus` | Start installing `version` and return at once; follow `get_update()`. |
| `get_update()` | `FirmwareUpdateStatus` | How the current or last update stands. |
| `get_update_log()` | `str` | The last update's log. |
| `wait_for_update(timeout=900.0, poll=2.0)` | `FirmwareUpdateStatus` | Poll every `poll` seconds until the update has ended, retrying failed connections; `TimeoutError` after `timeout` seconds. |
| `install(version, include_beta=False, timeout=900.0)` | `FirmwareUpdateStatus` | `start_update()` then `wait_for_update()`. Check `state == "succeeded"`. |
| `upload_package(package)` | `FirmwareRelease` | Send a release package (`rel-x.y.z.zip`, at most 256 MB) to the station, as bytes or a path. The station checks it, signature included, and keeps it in its cache. |
| `install_package(package, timeout=900.0)` | `FirmwareUpdateStatus` | `upload_package()` then `install()` of its version. |
| `delete_package(file_name)` | &mdash; | Remove a package from the station's cache. |

`start_update()` (and so `install()`) raises 400 for a release below the minimum version, 409 while an update runs, and 501 off a station. What goes wrong after it has started (a version neither the source nor the cache has, a revoked release, a damaged download, a package that isn't signed by E-Sharp, too little space) ends the update in `failed`, with the reason in `message` and in `get_update_log()`. A beta release needs `include_beta=True` here too.

`upload_package()` raises 400 for a file that isn't a release package, one below the minimum version, or one that isn't signed by E-Sharp; nothing is kept then.

## Update States

| `state` | Meaning |
|---------|---------|
| `idle` | No update has run |
| `downloading` | Fetching the package; `bytes` and `total_bytes` show progress |
| `staging` | Checking the package's layout and signature, and unpacking it |
| `installing` | The hardware app and the WebApi are stopped, the release copied, and both started again |
| `succeeded` | Both services were still running 20 s and 40 s after starting |
| `rolledBack` | They weren't; the old version was put back |
| `failed` | The update ended before anything was copied (an unknown version, a bad download, an unsigned package, too little space) |
| `unknown` | The station couldn't read its status file; `message` says why |

`FirmwareUpdateStatus.finished` is `True` in `idle`, `succeeded`, `failed`, `rolledBack` and `unknown`.

## Examples

### Install the Newest Release

```python
import sys

from accordionq2 import AccordionQ2ApiError, AccordionQ2Client

with AccordionQ2Client("http://agent64.local:5000") as client:
    state = client.firmware.get_state()
    print(f"Installed: {state.current}  (minimum {state.minimum_version})")
    print(f"Source:    {state.source.location}")
    if not state.supported:
        sys.exit("This WebApi isn't on a station")
    if not state.update.finished:
        sys.exit(f"An update is already running: {state.update.state}")

    releases = client.firmware.get_releases()
    if releases.error:
        print("Source not readable, showing cached packages only:", releases.error)
    for r in releases.releases:
        flags = " installed" if r.installed else ""
        flags += "" if r.installable else " (below minimum)"
        print(f"  {r.version}{flags}")

    newest = next((r for r in releases.releases if r.installable), None)
    if newest is None:
        sys.exit("No installable release")
    if newest.installed:
        sys.exit(f"Already on {newest.version}")

    print(f"Installing {newest.version}; the station restarts...")
    try:
        status = client.firmware.install(newest.version)
    except AccordionQ2ApiError as e:
        sys.exit(f"Refused: HTTP {e.status_code}: {e}")

    if status.state == "succeeded":
        print(f"Updated to {status.version}")
    else:
        print(f"Update {status.state}: {status.message}")
        print(client.firmware.get_update_log())
        sys.exit(1)
```

### Update a Station Without Internet

Releases are published at the station's `default_source`, the E-Sharp deployment
`https://esharp.blob.core.windows.net/accfirmware`. A computer with internet can download them
for a station without: `releases.json` lists the releases, and each package is beside it under
its `FileName`, for example `https://esharp.blob.core.windows.net/accfirmware/rel-6.0.0.zip`.
Read the address from the station rather than writing it into a script:

```python
url = client.firmware.get_state().default_source
print(f"{url}/releases.json")
```

Then send a package from your computer:

```python
status = client.firmware.install_package("C:/releases/rel-6.0.0.zip")
print(status.state, status.message)
if status.state != "succeeded":
    print(client.firmware.get_update_log())
```

To send it now and install later, use `upload_package()` and then `install(release.version)`:

```python
release = client.firmware.upload_package("C:/releases/rel-6.0.0.zip")
print(release.version, release.origin)   # "uploaded" unless the source has it too
```

### Following an Update Yourself

```python
import time

client.firmware.start_update("6.1.0")
while True:
    try:
        u = client.firmware.get_update()
    except (OSError, AccordionQ2ApiError):
        time.sleep(2)            # the WebApi is restarting
        continue
    if u.state == "downloading" and u.total_bytes:
        print(f"{u.bytes / u.total_bytes:.0%}")
    else:
        print(u.state)
    if u.finished:
        break
    time.sleep(2)
```

### Release Source

```python
client.firmware.set_source("/media/usb/accfirmware")   # a folder on the Pi
client.firmware.set_source(None)                       # back to the E-Sharp deployment
```

## Models

### `FirmwareState`

| Field | Type | Description |
|-------|------|-------------|
| `current` | `str` or `None` | The installed version; `pending` after an interrupted update |
| `source` | `FirmwareSource` | Where the station looks for releases |
| `default_source` | `str` | The E-Sharp deployment's address |
| `supported` | `bool` | `False` off a station: installing raises 501 |
| `minimum_version` | `str` | The oldest version the station installs |
| `update` | `FirmwareUpdateStatus` | The current or last update |

### `FirmwareSource`

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `str` | `url` or `folder` (a folder on the Pi) |
| `location` | `str` | The address or folder |
| `is_default` | `bool` | The E-Sharp deployment |

### `FirmwareReleases`

| Field | Type | Description |
|-------|------|-------------|
| `source` | `FirmwareSource` | The source read |
| `releases` | `tuple[FirmwareRelease, ...]` | Newest first |
| `error` | `str` or `None` | Why the source couldn't be read; `releases` then holds the cached packages only |

### `FirmwareRelease`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `version` | `str` | &mdash; | e.g. `6.0.0` |
| `file_name` | `str` | &mdash; | e.g. `rel-6.0.0.zip` |
| `author` | `str` or `None` | `None` | |
| `release_notes` | `str` or `None` | `None` | Text, or a link to the release notes |
| `beta` | `bool` | `False` | A beta release |
| `revoked` | `bool` | `False` | Withdrawn (revoked releases aren't listed) |
| `installed` | `bool` | `False` | The version the station runs |
| `downloaded` | `bool` | `False` | On the station already, so installing needs no download |
| `origin` | `str` | `"catalogue"` | `catalogue`, or `uploaded` for a package only the station's cache has |
| `installable` | `bool` | `True` | `False` below the minimum version; installing it is refused |

### `FirmwareUpdateStatus`

| Field | Type | Description |
|-------|------|-------------|
| `state` | `str` | See [Update States](#update-states) |
| `version` | `str` or `None` | The version being or last installed |
| `message` | `str` or `None` | What happened, e.g. why it failed |
| `bytes` | `int` or `None` | Bytes downloaded so far |
| `total_bytes` | `int` or `None` | The package size, while downloading |
| `time` | `str` or `None` | When the state last changed (ISO 8601) |
| `finished` | `bool` | Property: `True` once the update has ended, however it went |

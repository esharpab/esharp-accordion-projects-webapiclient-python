# Files

Files in the station's own folders: configuration, alias files, state machines, media, extensions and logs. Only these folders are reachable, each by an id (its *root*).

| Root | Folder on a station | Writable |
|------|---------------------|----------|
| `config` | `hw/config`: boot.config, modules.config, log4net.config | yes |
| `alias` | `hw/alias` | yes |
| `fsms` | `hw/fsms` | yes |
| `media` | `hw/capture` | yes |
| `extensions` | `hw/additional` | yes |
| `logs` | `hw/logs` | no |
| `webapi-logs` | The WebApi's logs, `audit.log` among them | no |

A *path* is relative to its root, with forward slashes; `""` is the root itself. A path that climbs out (`..`), names a drive or holds a character a file name can't is refused with 400, and a symbolic link anywhere below the root with 403. Changes in a read-only root raise 403. Changes are writes, so while another client holds the [lease](lease.md) they raise 423.

## Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_roots()` | `list[FileRoot]` | The folders the file API reaches. |
| `list(root, path="")` | `FileListing` | What a folder holds, folders first. |
| `download(root, path)` | `bytes` | A file's bytes. A log can be read while it is written. |
| `upload(root, path, data, overwrite=False)` | `FileEntry` | Upload a file (at most 64 MB). An existing file is replaced only with `overwrite=True`; 409 otherwise. |
| `create_folder(root, path)` | &mdash; | Create a folder; 409 if it exists. |
| `move(root, source, target, overwrite=False)` | &mdash; | Rename or move a file or folder within its root. |
| `delete(root, path, recursive=False)` | &mdash; | Delete a file, or a folder: an empty one, or one with contents with `recursive=True` (409 otherwise). The root itself can't be deleted. |

An upload is written beside the old file first, so a failed upload leaves the old file as it was.

## Examples

### Browsing

```python
for r in client.files.get_roots():
    print(f"{r.id:<12} writable={r.writable} exists={r.exists}  {r.description}")

listing = client.files.list("alias")
for e in listing.entries:
    kind = "dir " if e.directory else f"{e.size:>8}"
    print(f"{kind}  {e.modified}  {e.name}")
```

### Backing Up and Restoring an Alias File

```python
data = client.files.download("alias", "station.csv")
with open("station.csv", "wb") as fp:
    fp.write(data)

client.files.upload("alias", "station.csv", data, overwrite=True)
```

### Folders, Moving and Deleting

```python
client.files.create_folder("alias", "old")
client.files.move("alias", "limits.csv", "old/limits.csv")
client.files.delete("alias", "old", recursive=True)
```

### Reading a Log

```python
text = client.files.download("logs", "hw.log").decode("utf-8", errors="replace")
print(text[-2000:])
```

Loading an alias file into the hardware app is still `client.application.load_config_file(name)`; to load it at every start, see [boot.config](system.md#start-up-configuration-bootconfig).

## Models

### `FileRoot`

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | The root id, e.g. `alias` |
| `description` | `str` | What the folder holds |
| `writable` | `bool` | Changes are allowed |
| `exists` | `bool` | `False` when the station doesn't have the folder |

### `FileListing`

| Field | Type | Description |
|-------|------|-------------|
| `root` | `str` | The root listed |
| `path` | `str` | The folder listed, relative to the root |
| `writable` | `bool` | Changes are allowed |
| `entries` | `tuple[FileEntry, ...]` | Its contents, folders first |

### `FileEntry`

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | File or folder name |
| `directory` | `bool` | `True` for a folder |
| `size` | `int` or `None` | Bytes; `None` for a folder |
| `modified` | `str` | Last written (ISO 8601) |

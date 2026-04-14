# Media

Upload, download, and manage media files on the device.

## Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `list_files()` | `list[str]` | List media files on the device. |
| `download_file(name)` | `bytes` | Download a media file. |
| `upload_file(name, data)` | &mdash; | Upload a media file (bytes). |
| `delete_file(name)` | &mdash; | Delete a media file. |

## Examples

```python
# List all media files
for f in client.media.list_files():
    print(f)

# Download and save locally
content = client.media.download_file("waveform.bin")
with open("waveform.bin", "wb") as fp:
    fp.write(content)

# Upload a file
with open("new_waveform.bin", "rb") as fp:
    client.media.upload_file("new_waveform.bin", fp.read())

# Delete a file
client.media.delete_file("old_waveform.bin")
```

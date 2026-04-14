# Connection

Check whether the API is connected to the hardware manager.

## Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_status()` | `ConnectionStatusDto` | Check the hardware manager connection state. |

## Example

```python
status = client.connection.get_status()
if status.is_connected:
    print("Connected to hardware manager")
else:
    print("Not connected:", status.last_error)
```

## Response Model

`ConnectionStatusDto`:

| Field | Type | Description |
|-------|------|-------------|
| `is_connected` | `bool` | `True` if the API is connected to the hardware manager |
| `last_error` | `str` or `None` | Last error message, if any |

# Audit

WebApi request audit log — records the IP address, HTTP method, path, response status, and duration of every request handled by the server.

## Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_audit_log(tail=100)` | `list[str]` | Last `tail` lines of the audit log. Pass `0` for the full log. |

## Examples

### Reading the Audit Log

```python
# Get the last 100 entries (default)
for line in client.audit.get_audit_log():
    print(line)

# Get the last 200 entries
recent = client.audit.get_audit_log(tail=200)

# Get the entire log
full = client.audit.get_audit_log(tail=0)
```

### Log Entry Format

Each line contains: `timestamp  ip  method  path  status  duration`

```
2026-05-29 14:23:01.442 192.168.1.55 POST /api/channels/configure 200 12ms
2026-05-29 14:23:02.019 10.0.0.3 GET /api/application/status 200 3ms
```

The log rotates automatically — up to 20 files of 1 MB each (20 MB total). This endpoint reads only the current (most recent) file.

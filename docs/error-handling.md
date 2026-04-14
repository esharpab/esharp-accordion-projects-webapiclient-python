# Error Handling

All API errors raise `AccordionQ2ApiError`, importable from the top-level package. The exception carries the HTTP status code and the server's error message.

## Basic Usage

```python
from accordionq2 import AccordionQ2ApiError

try:
    ch = client.channels.get_channel(alias="does.not.exist")
except AccordionQ2ApiError as e:
    print(f"HTTP {e.status_code}: {e}")
```

## Common Error Codes

| HTTP Status | Meaning | Typical Cause |
|-------------|---------|---------------|
| 400 | Bad Request | Invalid parameters, or `get_samples()` called after `reduced_set=True` |
| 404 | Not Found | Channel, resource, or config file does not exist |
| 500 | Internal Server Error | Hardware manager encountered an error |
| Connection refused | — | WebApi host is unreachable |

## Exception Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `status_code` | `int` | HTTP status code |
| `message` | `str` | Error message from the server |

## Pattern: Retry on Transient Errors

```python
import time
from accordionq2 import AccordionQ2ApiError

def read_with_retry(client, name, retries=3):
    for attempt in range(retries):
        try:
            return client.resources.get_value(name)
        except AccordionQ2ApiError as e:
            if e.status_code >= 500 and attempt < retries - 1:
                time.sleep(1)
                continue
            raise
```

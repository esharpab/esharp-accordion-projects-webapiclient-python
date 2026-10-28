# Error Handling

All API errors raise `AccordionQ2ApiError`, importable from the top-level package. The exception carries the HTTP status code and the server's error message. A refusal for want of an API key or role is its subclass `AccordionQ2SecurityError` ([below](#security-errors-401-and-403)).

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
| 3xx | Redirect | The station's API never redirects, and the client doesn't follow one: usually a wrong base URL |
| 400 | Bad Request | Invalid parameters, or `get_samples()` called after `reduced_set=True` |
| 401 | Unauthorized | The station is in security mode `On` and the client sent no API key, or one it doesn't know: `AccordionQ2SecurityError` |
| 403 | Forbidden | The API key's role is too low (`AccordionQ2SecurityError`); or a change in a read-only folder ([Files](api/files.md)), a plain `AccordionQ2ApiError` |
| 404 | Not Found | Channel, resource, or config file does not exist |
| 409 | Conflict | The lease is held by someone else (`acquire`), a file exists, boot.config changed since it was read (`if_modified`), or a firmware update is running |
| 423 | Locked | Another client holds the [lease](api/lease.md); changes and forced reads are refused |
| 500 | Internal Server Error | Hardware manager encountered an error |
| 501 | Not Implemented | System, firmware or service calls on a WebApi that isn't on a station |
| Connection refused | — | WebApi host is unreachable: `OSError` (e.g. `ConnectionRefusedError`, `TimeoutError`) |
| Certificate | — | Over HTTPS, the certificate isn't the pinned one (`AccordionQ2CertificateError`) or isn't trusted (`ssl.SSLCertVerificationError`) |

> **Note:** Network-level errors (host unreachable, DNS failure, timeout, a refused certificate) are raised as `OSError` subclasses rather than `AccordionQ2ApiError`. Catch both when robustness is required.

## Exception Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `status_code` | `int` | HTTP status code |
| `message` | `str` | Error message from the server |

The client automatically extracts error messages from RFC 7807 **ProblemDetails** responses
(checking the `message`, `detail`, and `title` fields in that order), as well as plain-text
and JSON error bodies.

## Security Errors (401 and 403)

A station in security mode `On` refuses a request without a valid API key (401) or from a key whose role is too low (403). The client raises `AccordionQ2SecurityError`, a subclass of `AccordionQ2ApiError`, for both, on the [event stream](api/events.md) too. Its message names the cause, followed by the server's own text as `(station: ...)` when it sent one, and never contains the key. The server's text matters when a 401 doesn't come from the station, e.g. from a proxy in front of it. See [Security](security.md) for keys and roles.

| Attribute | Type | Description |
|-----------|------|-------------|
| `reason` | `AccordionQ2SecurityReason` | `MISSING_API_KEY` (401, the client has no key), `INVALID_API_KEY` (401, the station doesn't know the key: wrong, or removed) or `ROLE_TOO_LOW` (403) |
| `required_role` | `str \| None` | The role the request needs: `Viewer`, `Operator` or `Admin`, as the station said |
| `status_code` | `int` | 401 or 403 |

```python
from accordionq2 import AccordionQ2SecurityError, AccordionQ2SecurityReason

try:
    client.system.reboot()
except AccordionQ2SecurityError as e:
    if e.reason is AccordionQ2SecurityReason.ROLE_TOO_LOW:
        print(f"This key can't do that; it needs {e.required_role}")
    else:
        print(f"Check the API key: {e}")
```

A 403 that doesn't name a role, such as a change in a read-only folder, stays a plain `AccordionQ2ApiError`.

## Certificate Errors

With `cert_sha256`, a server whose certificate has another fingerprint raises `AccordionQ2CertificateError` before any request is sent, so the key doesn't reach it. It is a subclass of `ssl.SSLCertVerificationError` (and so of `OSError`), as an untrusted certificate raises without a pin, and it isn't retried.

| Attribute | Type | Description |
|-----------|------|-------------|
| `expected` | `str` | The pinned fingerprint, as 64 upper-case hex digits |
| `actual` | `str \| None` | The fingerprint of the certificate the server sent; `None` if it sent none |

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

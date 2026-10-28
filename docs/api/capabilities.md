# Capabilities

What the WebApi on a station supports: the contract version, its build version, the channel codec version, a list of features and the security mode. Use it to decide whether a newer call is available before making it.

The server answers without calling the hardware app, so this works while the hardware app is disconnected too. It needs no API key, so a client can learn the security mode before it has one.

## Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get()` | `CapabilitiesDto` | The WebApi's capabilities. A WebApi that predates `GET /api/capabilities` (404) gives `CapabilitiesDto()` instead of an exception. |

## Example

Decide by `features`, not by version numbers:

```python
from accordionq2 import CapabilitiesDto

caps = client.capabilities.get()
print(f"WebApi {caps.webapi_version}, contract v{caps.api_version}, codec v{caps.codec_version}")

if caps.has(CapabilitiesDto.EVENTS):
    ...  # the event stream is available: see Events
else:
    ...  # older firmware: poll instead
```

## Response Model

### `CapabilitiesDto`

| Field | Type | Description |
|-------|------|-------------|
| `api_version` | `int` | The contract version; `0` for a WebApi that predates it |
| `webapi_version` | `str` | The WebApi build's informational version, e.g. `"7.0.0"` |
| `codec_version` | `int` | The server's channel codec version |
| `features` | `tuple[str, ...]` | The supported features |
| `security_mode` | `str` | `"Off"`, `"Report"` or `"On"`: how the station treats a request without a valid API key ([Security](../security.md)); `"Off"` from a WebApi that predates it. A string, so a mode added later doesn't break reading |

| Member | Description |
|--------|-------------|
| `has(feature)` | Whether `features` contains *feature* |

### Feature names

| Constant | Value | Means |
|----------|-------|-------|
| `CapabilitiesDto.CHANNELS_ENCODED` | `"channels.encoded"` | The encoded channel calls work (in the .NET client; this one doesn't have them yet) |
| `CapabilitiesDto.EVENTS` | `"events"` | The [event stream](events.md) works |
| `CapabilitiesDto.SECURITY_API_KEY` | `"security.apikey"` | The station checks API keys as `security_mode` says ([Security](../security.md)) |
| `CapabilitiesDto.VALUES_CACHE_ONLY` | `"values.cacheOnly"` | `client.resources.read_cached()` works ([cache-only reads](resources.md#cache-only-reads)); checked by the client itself |

The server may list other features too, for example `"instruments"`; `has` takes any string.

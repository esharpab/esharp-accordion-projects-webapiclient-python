# Quick Start

## Creating a Client

The main entry point is `AccordionQ2Client`. Pass the base URL of the AccordionQ2 WebApi:

```python
from accordionq2 import AccordionQ2Client

client = AccordionQ2Client("http://agent64.local:5000")
```

### Constructor Parameters

| Parameter         | Type                      | Default | Description |
|-------------------|---------------------------|---------|-------------|
| `base_url`        | `str`                     | —       | Base URL of the AccordionQ2 WebApi, e.g. `"http://raspberrypi:5000"`, `"https://[::1]:5001"` or `"http://[fe80::1%eth0]:5000"` |
| `timeout`         | `float`                   | `30.0`  | HTTP request timeout in seconds |
| `auth`            | `tuple[str, str] \| None` | `None`  | Optional `(username, password)` for HTTP Basic Auth |
| `verify`          | `bool \| str`             | `True`  | TLS certificate verification: `True` uses the system CAs, a string is a path to a CA bundle (e.g. a site CA), `False` disables it. For a station's self-signed certificate use `cert_sha256` |
| `default_headers` | `dict[str, str] \| None`  | `None`  | Additional headers merged into every request; an `X-Api-Key` here is handled as `api_key` |
| `api_key`         | `str \| None`             | `None`  | Keyword only (7.0). The station API key, sent as `X-Api-Key` on every request: see [Security](../security.md) |
| `cert_sha256`     | `str \| None`             | `None`  | Keyword only (7.0). The SHA-256 fingerprint of the station's HTTPS certificate: exactly that certificate is accepted. See [Security](../security.md) |

### Using a Context Manager

The recommended approach is to use a `with` block:

```python
with AccordionQ2Client("http://agent64.local:5000") as client:
    names = client.resources.get_names()
    print(names)
```

The client also works without a context manager:

```python
client = AccordionQ2Client("http://agent64.local:5000")
names = client.resources.get_names()
client.close()
```

### API Keys and HTTPS

```python
import os

# An API key (X-Api-Key on every request, the event stream included)
with AccordionQ2Client("http://station-12:5000",
                       api_key=os.environ["ACCORDION_API_KEY"]) as client:
    names = client.resources.get_names()

# And HTTPS with the station's self-signed certificate, pinned by its SHA-256 fingerprint
with AccordionQ2Client("https://station-12:5001",
                       api_key=os.environ["ACCORDION_API_KEY"],
                       cert_sha256="3F:A2:7C:...:9C") as client:
    names = client.resources.get_names()
```

Over `http://` the key crosses the network in clear text: acceptable only on a trusted intranet segment. See [Security](../security.md) for modes, roles, pins, a site CA and IPv6 addresses.

## Checking the Connection

```python
with AccordionQ2Client("http://agent64.local:5000") as client:
    status = client.connection.get_status()
    if status.is_connected:
        print("Connected to hardware manager")
    else:
        print("Not connected:", status.last_error)
```

## Reading and Writing Values

Resources are identified by dotted name strings (e.g. `"TempRegulator.CPU_TEMP"`):

```python
# Read a single value
temp = client.resources.get_value("TempRegulator.CPU_TEMP")
print(f"CPU temperature: {temp}")

# Read multiple values at once
values = client.resources.get_values([
    "TempRegulator.CPU_TEMP",
    "Engine.Uptime",
])
for name, val in values.items():
    print(f"{name} = {val}")

# Write a value
client.resources.set_value("MyOutput", "2.5")
```

## Working with Channels

```python
# List all channels
for ch in client.channels.get_all():
    print(f"  {ch.alias}: type={ch.channel_type}, unit={ch.unit}")

# Look up a specific channel
ch = client.channels.get_channel(alias="0.1.ESH10000158.MON_3V3")
print(f"Type: {ch.channel_type}, Direction: {ch.direction}")
```

## Configuring a Channel

Use partial updates &mdash; only the fields you set are changed:

```python
from accordionq2.models import ChannelConfigRequest

client.channels.configure(ChannelConfigRequest(
    alias="0.1.ESH10000158.MON_3V3",
    description="Main 3.3 V rail monitor",
    unit="V",
))
```

## Handling Errors

All API errors raise `AccordionQ2ApiError`; a refusal for want of an API key or role (401, 403) is its subclass `AccordionQ2SecurityError` ([Error Handling](../error-handling.md)):

```python
from accordionq2 import AccordionQ2ApiError

try:
    ch = client.channels.get_channel(alias="does.not.exist")
except AccordionQ2ApiError as e:
    print(f"HTTP {e.status_code}: {e}")
```

## Next Steps

Explore the full [API Reference](../api/overview.md) for detailed documentation of all 8 operation groups.

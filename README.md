# AccordionQ2 Python Client

Python client library for the AccordionQ2 Hardware Management REST API.

## Requirements

- Python 3.8+
- No external runtime dependencies (stdlib only)

## Installation

```bash
pip install .
```

## Quick Start

```python
from accordionq2 import AccordionQ2Client

with AccordionQ2Client("http://agent64.local:5000") as client:
    # Read resource values
    names = client.resources.get_names()
    value = client.resources.get_value("TempRegulator.CPU_TEMP")

    # Check application status
    status = client.application.get_status()
    print(f"Status: {status}")

    # List channels
    channels = client.channels.get_all()
    for ch in channels:
        print(f"{ch.alias}: {ch.channel_type}")
```

## API Groups

| Group          | Description                          |
|----------------|--------------------------------------|
| `resources`    | Read/write hardware resource values  |
| `channels`     | Query and configure hardware channels|
| `modules`      | Manage hardware/software modules     |
| `application`  | Application lifecycle & config files |
| `media`        | Media file management                |
| `connection`   | Connection status                    |

## Running Tests

Integration tests require a running AccordionQ2 hardware instance:

```bash
pip install -e ".[dev]"
pytest tests/ -m integration
```

Override the default URL with an environment variable:

```bash
ACCORDIONQ2_API_URL=http://mydevice:5000 pytest tests/ -m integration
```

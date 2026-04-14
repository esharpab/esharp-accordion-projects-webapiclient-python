# AccordionQ2 Python Client

Python client library for the **AccordionQ2 Hardware Management REST API**.

[![PyPI](https://img.shields.io/pypi/v/accordionq2)](https://pypi.org/project/accordionq2/)
[![NuGet (.NET)](https://img.shields.io/nuget/v/AccordionQ2.WebApiClient)](https://www.nuget.org/packages/AccordionQ2.WebApiClient/)

This is the Python counterpart of the [.NET WebApiClient](https://www.nuget.org/packages/AccordionQ2.WebApiClient/). Both libraries expose the same API surface so switching between them feels natural.

## Features

- **Zero dependencies** &mdash; uses only the Python standard library (`urllib`, `json`, `dataclasses`)
- **Full API coverage** &mdash; 8 operation groups covering all hardware management endpoints
- **Synchronous & thread-safe** &mdash; simple blocking calls, safe from multiple threads
- **Context manager support** &mdash; use with `with` blocks for clean resource management
- **Cross-platform** &mdash; Windows, Linux (including ARM / Raspberry Pi)

## Quick Example

```python
from accordionq2 import AccordionQ2Client

with AccordionQ2Client("http://agent64.local:5000") as client:
    status = client.connection.get_status()
    print("Connected:", status.is_connected)

    temp = client.resources.get_value("TempRegulator.CPU_TEMP")
    print("CPU temperature:", temp)
```

## Getting Started

- [Installation](getting-started/installation.md)
- [Quick Start](getting-started/quickstart.md)

## API Reference

- [Overview](api/overview.md) &mdash; all 8 API groups at a glance
- [Resources](api/resources.md), [Channels](api/channels.md), [Modules](api/modules.md), [Application](api/application.md), [Media](api/media.md), [Connection](api/connection.md)
- [Comm (Bus Transactions)](api/comm.md) &mdash; I2C, UART, SPI, Socket
- [Numeric Results](api/numeric-results.md) &mdash; high-speed sampling

## Also Available

| Platform | Package |
|----------|---------|
| Python 3.8+ | [`accordionq2`](https://pypi.org/project/accordionq2/) via pip |
| .NET Standard 2.0+ | [`AccordionQ2.WebApiClient`](https://www.nuget.org/packages/AccordionQ2.WebApiClient/) via NuGet |

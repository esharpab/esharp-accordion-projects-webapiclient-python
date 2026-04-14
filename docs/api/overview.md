# API Overview

`AccordionQ2Client` exposes **eight operation groups**, each covering one area of the hardware API. All methods are **synchronous** and raise `AccordionQ2ApiError` on HTTP errors.

```python
from accordionq2 import AccordionQ2Client

with AccordionQ2Client("http://agent64.local:5000") as client:
    client.connection        # Connection status
    client.resources         # Hardware resource values (read/write)
    client.channels          # Channel configuration
    client.modules           # Module management & topology
    client.application       # Application lifecycle & config files
    client.media             # Media file management
    client.comm              # Raw bus transactions (I2C, UART, SPI, Socket)
    client.numeric_results   # Fast numeric sampling & statistics
```

| Group | Description | Details |
|-------|-------------|---------|
| [`connection`](connection.md) | Check hardware manager connectivity | [→](connection.md) |
| [`resources`](resources.md) | Read/write hardware values (voltages, temperatures, etc.) | [→](resources.md) |
| [`channels`](channels.md) | Configure multi-purpose I/O channels | [→](channels.md) |
| [`modules`](modules.md) | Load/unload modules, query hardware topology | [→](modules.md) |
| [`application`](application.md) | Application lifecycle, configuration files | [→](application.md) |
| [`media`](media.md) | Upload/download media files | [→](media.md) |
| [`comm`](comm.md) | Raw bus transactions (I2C, UART, SPI, Socket) | [→](comm.md) |
| [`numeric_results`](numeric-results.md) | High-speed sampling with server-side statistics | [→](numeric-results.md) |

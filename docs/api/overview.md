# API Overview

`AccordionQ2Client` exposes these operation groups

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
    client.calibration       # Calibration channel read/write
    client.instruments       # Instruments (power supplies) and their function maps
    client.events            # Event stream: connection, configuration and values events
    client.subscriptions     # Value subscriptions delivered on the event stream
    client.lease             # The control lease: one client at a time changes the station
    client.system            # Services, reboot and clock
    client.system.boot       # The hardware app's start-up configuration (boot.config)
    client.files             # Files in the station's folders
    client.firmware          # Firmware releases and updates
    client.audit             # WebApi request audit log
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
| [`calibration`](calibration.md) | Read and write Calibration channel tables | [→](calibration.md) |
| [`events`, `subscriptions`](events.md) | Event stream and value subscriptions | [→](events.md) |
| [`instruments`](instruments.md) | Instruments such as power-supply outputs, with the channel behind each capability | [→](instruments.md) |
| [`lease`](lease.md) | Hold control of the station; other clients' changes get 423 | [→](lease.md) |
| [`system`, `system.boot`](system.md) | Services, reboot, clock, and the start-up configuration (boot.config) | [→](system.md) |
| [`files`](files.md) | Browse, download, upload, move and delete files in the station's folders | [→](files.md) |
| [`firmware`](firmware.md) | List releases, install signed releases, update offline from a package | [→](firmware.md) |
| [`audit`](audit.md) | WebApi request audit log | [→](audit.md) |

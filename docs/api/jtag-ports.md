# JTAG ports

A JTAG port is a JTAG TAP that a module on the station owns the way to: MicroHAPS's FT4232H interface A
(`MicroHAPS.JTAG.A`), an FTDI cable of the JtagPorts module (`JTAG_FTDI.JTAG.A`). One holder at a time: the owner itself
(an FPGA image load, a power cycle), an XVC client (Vivado's hardware manager), or the Drummer instance bound to it.
`client.jtag_ports` lists them and switches their XVC server. Firmware with stable module names; on older firmware the
list is empty.

Each port is two channels:

| Channel | Type | What |
|---|---|---|
| `<port>.State` | Register, IN, Unit `jtag-port` | The port's state as JSON (below), from the station's memory. |
| `<port>.Xvc` | Digital, IN/OUT, Unit `jtag-port:xvc` | The XVC server's switch: true, it listens. Writing it needs **Admin**. |

## Methods

`client.jtag_ports` (`JtagPortsGroup`):

| Method | Returns | Description |
|--------|---------|-------------|
| `get_all()` | `list[JtagPort]` | Every port with its state read now, by name. |
| `get_state(port)` | `JtagPortState \| None` | One port's state (`port` is its name or one of its channels' net names). |
| `set_xvc(port, on)` | `None` | Switch the XVC server on or off. 403 below Admin; 409 when the TCP port can't be bound. |

`accordionq2.jtag_ports.port_name(name)` gives `"MicroHAPS.JTAG.A"` for itself and for its `.State` or `.Xvc` channel.

A Drummer instance binds to a port with `client.drummer.target("Drummer").bind_port("MicroHAPS.JTAG.A")` and says which
one with `port()` (see [Drummer](drummer.md)).

## Example

```python
for p in client.jtag_ports.get_all():
    s = p.state
    if s is None:
        continue
    holder = f"{s.holder.kind} {s.holder.name}" if s.holder else "nobody"
    print(f"{p.name} ({s.label}): {s.state}, held by {holder}, bound to {s.bound}")
    if s.xvc.enabled:
        print(f"  XVC on {s.xvc.listen}, client {s.xvc.client or 'none'}, {s.xvc.sessions} sessions")

client.jtag_ports.set_xvc("MicroHAPS.JTAG.A", True)    # an Admin key
```

## Models

`JtagPort`: `name`, `state` (`JtagPortState` or None), `raw` (the channel's value), `state_channel`, `xvc_channel`.

`JtagPortState` (the State channel's JSON):

| Field | JSON | Description |
|-------|------|-------------|
| `port` | `port` | `"MicroHAPS.JTAG.A"` |
| `owner` | `owner` | The module that owns it: `"MicroHAPS"` |
| `label` | `label` | What it opens: `"FT4232H J020324 interface A"` |
| `seq` | `seq` | One more at every change; a value older than one you have is stale |
| `state` | `state` | `"free"`, `"held"` or `"down"` |
| `holder` | `holder` | `JtagHolder`: `kind` (`borrower`, `xvc`, `owner`), `name`, `what`, `since`; None when free or down |
| `why` | `why` | Why it is down: `"the board is powered down (POWER is off)"` |
| `bound` | `bound` | The Drummer instance that claims it, or None |
| `max_tck_hz` | `max_tck_hz` | The fastest TCK a holder gets |
| `xvc` | `xvc` | `JtagXvc`: `enabled`, `engine`, `listen`, `allow`, `client`, `waiting`, `sessions`, `last_end` |
| `since` | `since` | When the state last changed |

## Holders, and who waits

The owner takes the port from anyone; an XVC client takes it from a Drummer instance at its first shift, except while
the instance runs a bitfile load or a self-test (the client then waits for it to end). The instance is then `parked`
and connects again, with discovery, when the port is free. With the switch on and no client, the instance keeps the
port as usual.

In the station's security mode `Off` everyone is Admin, so the switch is anyone's there.

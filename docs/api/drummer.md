# Drummer

A Drummer module (Extensions/Drummer in the station's firmware) reaches IEEE 1687 instruments in an FPGA over JTAG:
GPIO, block RAM, clock counters, MMCMs, I2C controllers and targets, logic analysers, link testers, GT transceivers and
memory PHYs. `client.drummer` finds the modules and runs their instruments' operations.

Every operation the station's Web UI offers on its Drummer > Instruments page (`/drummer/instruments`) is a **transaction** on the instrument's
**Call channel** (`Drummer.MEM.Call`; module operations on `Drummer.Target.Call`). The value sent is a JSON object
with the operation's name in `call` and its arguments; the answer is the operation's result. So a script does exactly
what the page does. The operations, their arguments and their results are listed in the firmware's
`Documentation/02-hardware/drummer.md`; they are the Python console's (`web.py`).

> Needs firmware with the `resources.transact` capability (`CapabilitiesDto.RESOURCES_TRANSACT`). Older firmware runs
> transactions for Admin only, under the engine lock: the calls then raise `AccordionQ2NotSupportedError` and send
> nothing.

## Methods

`client.drummer`:

| Method | Returns | Description |
|--------|---------|-------------|
| `find()` | `list[DrummerModuleRef]` | The Drummer modules: one per Instrument of type `Drummer`, else one per `Target.Status` with a `Target.Package` beside it. `prefix` (`"Drummer"`) and `name`. |
| `target(prefix)` | `DrummerTarget` | One module. Makes no request. |

`DrummerTarget`:

| Method | Returns | Description |
|--------|---------|-------------|
| `call(instrument, name, args=None, /, *, timeout_s=60.0, **kwargs)` | `dict` | Runs operation `name` on `<segment>.Call`, follows a job to its end. |
| `module_call(name, args=None, /, *, timeout_s=60.0, **kwargs)` | `dict` | A module operation on `Target.Call` (`attention`, `attention_detail`, `la_group_*`), or an instrument's with `sib=`. |
| `status()` | `dict` | `Target.Status`: connected, the design, the error. |
| `info()` | `dict` | `Target.Info`: the design, the chain, every instrument with its register map and tool facts. No scan. |
| `attention()` | `dict` | `Target.Attention`: the ATTN word, the instruments asking for attention and why. |
| `jobs()` | `list[dict]` | `Target.Jobs`: running jobs and ended ones not fetched yet. |
| `snapshot(instrument)` | `dict` | `<segment>.Snapshot`: the instrument's fields and status. While something else holds the JTAG: the last capture with `stale` and `age_ms`. |
| `read(name)` / `write(name, value)` | `str` / `None` | A field or semantic channel below the module (`"CLK.Freq0"`, `"GPIO.GPIO0"`). |
| `net(name)` | `str` | `"Drummer." + name`. |
| `port()` | `str` | `Target.Port`: the JTAG port bound now (`"MicroHAPS.JTAG.A"`), `""` when unbound. |
| `bind_port(port)` | `None` | Bind the instance to that port now (`""` or None unbinds). 409 when another instance claims it, or while a load, the self-test or a job holds the TAP. Not saved: the module's `Port` setting is the binding at its next load. |
| `library()` | `dict` | `Target.Library`: the station's package library and this instance's selection (below). From the module's memory, no scan. |
| `select_package(sha256)` | `None` | `Target.Select`: select a library package for this instance, by its SHA-256 or 8 or more of its first hex digits. |
| `unselect_package()` | `None` | `Target.Select` = `""`: back to the `PackagePath` setting, or to no package. |
| `delete_package(sha256)` | `None` | `Target.Delete`: delete a library package. 409 while a configured instance selects it (the message names the instances). |
| `upload_package(path, timeout=60)` | `ByteStreamStatus` | Upload a `.drummer` package to `Target.Package` and wait until it is kept and selected (`done`) or refused (`failed`, returned). The connect and any load follow. |
| `build()` | `dict \| None` | `Target.Status`'s `build`: which build the FPGA runs, which build the package has, which rule decided. None on firmware without build identity. |

A Drummer instance is named as it is configured in modules.config (`Drummer`, `DUT_A`): that name is its channels'
prefix (`Drummer.Target.Status`) and `DrummerModuleRef.prefix`. An instance whose port is held by someone else (an
XVC client, the port's owner) or down is **parked**: `status()` says `"state": "parked"` with `port`, `port_state`,
`holder` and `why`; its field channels and operations answer 409 until it is connected again, which it does by itself.
The ports are [`client.jtag_ports`](jtag-ports.md).

- **An instrument** is a segment or a SIB: `"MEM"` or `"SIB_MEM"`. The leading `SIB_` is dropped.
- **Arguments** come as a dict, as keyword arguments, or both. The method's own parameters are positional, so an
  argument named `op` (`mem_start`'s), `name` or `instrument` passes as any other. `call` and `job` are not arguments.
- **The answer** is the operation's result with two keys the module adds: `ms` (time in the module, TAP wait included)
  and `seq` (the module's TAP hold number: of two results, the higher `seq` is the newer).
- **Jobs**: the module answers within 15 s. An operation still holding the JTAG 10 s after it arrived becomes a job:
  the answer is `{"job": "<ticket>", "state": "running", ...}`. `call` then sends `{"call": "job", "job": "<ticket>",
  "wait_ms": 10000}` until the job has ended. After `timeout_s` it raises `TimeoutError` with the job's ticket; the
  job goes on in the module, and its result can be fetched with that ticket (only the caller that started the job has
  it; `Target.Jobs` shows the id before its dot) for 5 minutes after it ends.

## The package library

Firmware with the library (`Target.Library`; older firmware answers 404 for these channels). The station keeps every
uploaded `.drummer` package once, by its SHA-256; each instance has one selected package, kept across restarts, and
that is what it loads.

```python
t = client.drummer.target("Drummer")

# The developer flow: upload, and the station keeps it, selects it, loads its bitfile when the FPGA does not run that
# build (LoadOnSelect mismatch), runs discovery and connects
up = t.upload_package("build/microhaps_mem.drummer")
if up.state != "done":
    raise RuntimeError(up.message)                       # refused: the old selection stays

# The upload's wait ends at the selection: the connect and any load follow
while t.status()["state"] in ("connecting", "loading"):
    time.sleep(0.5)
print(t.build()["text"])
# FPGA runs build unknown · package build none · the package's build: this station loaded ... (marker)

# Back to a known-good build: one call
for p in t.library()["packages"]:
    print(p["sha256"][:8], p["file"], p["uploaded"], p["usr_access_time"], "selected by", p["selected_by"])
t.select_package("4f0c1a2b")

t.delete_package("9a1b2c3d")                             # 409 while a configured instance selects it
```

`build["rule"]` says what decided whether the FPGA runs the package's build: `usr_access` (the FPGA's USR_ACCESS against
the stamp in the bitfile, a bitfile built with `BITSTREAM.CONFIG.USR_ACCESS TIMESTAMP`), `marker` (this station's
record of what it loaded on the port, forgotten at anything it sees that may reconfigure the FPGA), `design_id`,
`discovery`, `device`, or `neither` (`runs_package` None: can't tell). `Target.Status` also has `package` (what the
instance runs), `load_on_select` and `warnings` (instruments without a register map in the package, driver versions,
a bitfile held back).

An instrument whose register map is not in the package is **opaque** (`"opaque": True` in `info()`): it stays in the
scan path, its `snapshot` has its raw words, and only `read`, `scan` without fields, `reset_instrument` and
`clear_errors` work on it. One whose class version has no driver (`"driver": "generic"`) has its register channels and
the generic operations.

## Errors

| Status | Meaning |
|--------|---------|
| 400 | The request is wrong: no such operation, a missing or bad argument, the operation refused it ("no frequency given"). |
| 403 | The key's role is too low: operations and writes need Operator; a transaction or a write on a bus channel (`<seg>.Bus`) needs Admin. |
| **409** | **Busy, try again**: something else holds the JTAG (another operation, a job, a bitfile load, the self-test). The message names it: "la_read on LA holds the JTAG now; try again when it has ended". |
| 500 | An instrument or JTAG fault (no lock, a CRC error, the cable gone), with the message. |

All are `AccordionQ2ApiError` with `status_code` (`AccordionQ2SecurityError` for 401 and 403).

## Examples

### Measuring a clock

```python
t = client.drummer.target("Drummer")
r = t.call("CLK", "clock_measure", gate=1_200_000, channel=1)
print(f"{r['hz'] / 1e6:.6f} MHz ({r['count']} edges in {r['ms']} ms)")
```

### The week-46 demo's run 1

```python
t = client.drummer.target("Drummer")
t.call("MEM", "mem_start", op="write_read", order="up", pattern="PRBS31", count=65536,
       iterations=1, reread=True)

def running():
    s = t.snapshot("MEM")                 # "stale" while an operation holds the JTAG, "fields" None before a read
    return s["fields"] is None or s["fields"]["RUNNING"] == 1

while running():
    time.sleep(0.5)
r = t.call("MEM", "mem_finish")          # r["mem"]["err"] == 0, r["log"]["count"] == 0
```

### Busy: try again

```python
for attempt in range(5):
    try:
        t.call("MMCM", "mmcm_set", mhz={"0": "50"})
        break
    except AccordionQ2ApiError as e:
        if e.status_code != 409:
            raise
        time.sleep(1)                     # str(e) says what holds the JTAG
```

### Semantic channels

```python
t.read("CLK.Freq0")                       # "233250000": 0.1 s of TAP, used again for 1 s
t.write("GPIO.GPIO0", "True")           # one bit, the other outputs kept
```

Poll with channel reads (`snapshot`, `read`) rather than with operations: every operation is one line in the station's
audit log.

# Events and subscriptions

The WebApi's event stream tells a client when the connection to the hardware app goes up or down and when channels change, and delivers values for subscriptions. One scheduler on the WebApi reads for every subscription through its value cache, so channels several clients watch are read once.

## Event stream

`client.events.open()` opens `GET /api/events` on a connection of its own and reads its `hello` at once.

| Event | When | Data |
|-------|------|------|
| `hello` | The stream opened | `isConnected`, `generation`, `apiVersion`, `streamId` |
| `connection` | The WebApi's connection to the hardware app went up or down | `isConnected`, `generation`, `lastError` |
| `configuration` | Channels were added, removed or changed | `changeType`, `generation` |
| `values` | A subscription's values | `subscription`, `values`, `ageMs`, `errors` (when some failed) |

Thirty seconds without any data (the server pings every 10 s) raises `TimeoutError`; the server ending the stream raises `ConnectionError`. Reconnecting is yours: open a new stream, subscribe again, and reload channels, since missed events aren't replayed.

## Subscriptions

| Method | Description |
|--------|-------------|
| `subscriptions.create(stream_id, channels, interval_ms=1000)` | Values of *channels* about every interval (100 to 60 000 ms) on that stream |
| `subscriptions.update(id, channels, interval_ms=1000)` | Replace channels and interval, and renew; renew within 60 s or it ends |
| `subscriptions.delete(id)` | End it; closing the stream ends all of its subscriptions too |

```python
with client.events.open() as events:
    sub = client.subscriptions.create(events.stream_id, ["0.4.ESH10000662.VMON1"], 500)
    for event in events:
        if event.name == "values":
            print(event.data["values"], event.data["ageMs"])
```

## Reads with a maximum age

`resources.get_values(names, max_age_ms=1000)` accepts values the WebApi read at most that long ago (by any client) and reads only the rest; `resources.read_values(...)` also returns how old each value is. Without `max_age_ms` every value is read from the hardware, as before.

## The control lease

One client at a time may change the station. While someone else holds it, writes and forced reads raise `AccordionQ2ApiError` with status 423; reads with `max_age_ms` and subscriptions keep working.

```python
with client.lease.hold("TAT station 3", ttl_ms=30000):
    client.resources.set_value("0.4.ESH10000662.VSET1", "5")
```

`hold` renews the lease every third of `ttl_ms` and releases it when the block ends, also on an exception. `client.lease.get()` says who holds it.

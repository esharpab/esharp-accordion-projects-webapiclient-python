# Lease

The control lease lets one client at a time change the station, typically a test station for the length of a test sequence, so that nobody else changes a setting in the middle of it.

While another client holds the lease, this client's changes (every POST, PUT and DELETE that changes something) and forced reads (`resources.get_value`, `resources.get_values` without `max_age_ms`) raise `AccordionQ2ApiError` with status **423**. Reads with `max_age_ms` and [subscriptions](events.md) keep working; they get the values the holder's own reads keep up to date. Anyone may ask who holds it.

After `acquire()` the client sends the lease id (the `X-Lease-Id` header) with every request, so its own changes go through as if there were no lease.

## Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get()` | `LeaseDto` | Who holds the lease, if anyone. |
| `acquire(owner, ttl_ms=30000)` | `LeaseDto` | Take the lease for `ttl_ms` (1 000 to 600 000 ms). Raises 409 while someone else holds it. |
| `renew(ttl_ms=None)` | `LeaseDto` | Renew the lease this client holds, optionally with a new time to live. Raises 404 once it has ended, and `RuntimeError` when this client holds none. |
| `release()` | &mdash; | Release the lease this client holds; does nothing when it holds none. |
| `hold(owner, ttl_ms=30000)` | context manager yielding `LeaseDto` | Acquire, renew in the background, and release when the block ends. |
| `held_lease_id` | `str` or `None` | Property: the id of the lease this client holds. |

A lease not renewed within its time to live ends by itself, so a crashed test station doesn't lock the station.

## Examples

### Holding the Lease for a Sequence

```python
with client.lease.hold("TAT station 3", ttl_ms=30000):
    client.resources.set_value("0.4.ESH10000662.VSET1", "5")
    voltage = client.resources.get_value("0.4.ESH10000662.VMON1")
```

`hold` renews the lease every third of `ttl_ms` on a background thread and releases it when the block ends, also on an exception. If the script dies, the lease ends within `ttl_ms`.

### Who Holds It

```python
lease = client.lease.get()
if lease.held:
    print(f"Held by {lease.owner} for another {lease.expires_in_ms / 1000:.0f} s")
```

### Acquiring and Releasing by Hand

```python
from accordionq2 import AccordionQ2ApiError

try:
    client.lease.acquire("TAT station 3", ttl_ms=60000)
except AccordionQ2ApiError as e:
    if e.status_code == 409:
        print("Someone else holds the lease:", e)
    raise

try:
    client.resources.set_value("0.4.ESH10000662.VSET1", "5")
    client.lease.renew()          # within ttl_ms, or the lease ends
finally:
    client.lease.release()
```

### Handling 423 in Another Client

```python
try:
    client.resources.set_value("0.4.ESH10000662.VSET1", "5")
except AccordionQ2ApiError as e:
    if e.status_code == 423:
        print("The station is held by another client:", e)
```

## Model

### `LeaseDto`

| Field | Type | Description |
|-------|------|-------------|
| `held` | `bool` | `True` while someone holds the lease |
| `owner` | `str` or `None` | The owner name the holder gave |
| `expires_in_ms` | `float` | Time left before the lease ends unless renewed |
| `lease_id` | `str` or `None` | The lease id, on the `LeaseDto` that `acquire()` returns; `None` from `get()` |

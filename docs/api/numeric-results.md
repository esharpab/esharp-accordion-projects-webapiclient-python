# Numeric Results &mdash; Fast Numeric Sampling

NumericResult channels perform high-speed acquisition on physical channels, computing summary statistics (mean, min, max, standard deviation) server-side. This avoids transferring large sample arrays over the network when only statistics are needed.

## Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_channels()` | `list[NumericResultChannelDto]` | All NumericResult channels with sampling capabilities. |
| `get_targets(channel_net_name)` | `list[str]` | Physical channels that a NumericResult channel can sample. |
| `measure(channel, target, samples, reduced_set)` | `NumericMeasureResultDto` | Trigger an acquisition (result cached server-side). |
| `get_mean(channel_net_name)` | `float` | Mean of the last measurement. |
| `get_min(channel_net_name)` | `float` | Minimum of the last measurement. |
| `get_max(channel_net_name)` | `float` | Maximum of the last measurement. |
| `get_stdev(channel_net_name)` | `float` | Standard deviation of the last measurement. |
| `get_samples(channel_net_name)` | `list[float]` | Raw sample array (only if `reduced_set=False`). |

## Typical Workflow

```python
# 1. Discover available NumericResult channels
channels = client.numeric_results.get_channels()
for ch in channels:
    print(f"{ch.net_name} (rate={ch.sample_rate} Hz, "
          f"default_samples={ch.default_samples})")

# 2. Check what a channel can sample
targets = client.numeric_results.get_targets(channels[0].net_name)
print("Available targets:", targets)

# 3. Trigger acquisition (result cached server-side)
meta = client.numeric_results.measure(
    channels[0].net_name, targets[0],
    samples=1000, reduced_set=True)
print(f"Acquired {meta.sample_count} samples in {meta.duration}")

# 4. Fetch summary statistics
mean  = client.numeric_results.get_mean(channels[0].net_name)
stdev = client.numeric_results.get_stdev(channels[0].net_name)
min_v = client.numeric_results.get_min(channels[0].net_name)
max_v = client.numeric_results.get_max(channels[0].net_name)
print(f"Mean={mean:.6f}, StdDev={stdev:.6f}, Min={min_v:.6f}, Max={max_v:.6f}")
```

## Getting Raw Samples

When you need the full sample array, set `reduced_set=False`:

```python
meta = client.numeric_results.measure(
    channels[0].net_name, targets[0],
    samples=100, reduced_set=False)

samples = client.numeric_results.get_samples(channels[0].net_name)
print(f"First 5 samples: {samples[:5]}")
```

!!! warning
    Calling `get_samples()` after a measurement with `reduced_set=True` will raise an `AccordionQ2ApiError` (HTTP 400) because raw samples are discarded when only statistics are computed.

## Response Models

### `NumericResultChannelDto`

| Field | Type | Description |
|-------|------|-------------|
| `net_name` | `str` | Net name of the NumericResult channel |
| `alias` | `str` | Alias of the channel |
| `possible_target_names` | `list[str]` | Physical channels this channel can sample |
| `sample_rate` | `int` | Sampling rate in Hz |
| `default_samples` | `int` | Default number of samples |

### `NumericMeasureResultDto`

| Field | Type | Description |
|-------|------|-------------|
| `channel_net_name` | `str` | NumericResult channel used |
| `target_net_name` | `str` | Physical channel sampled |
| `sample_count` | `int` | Number of samples acquired |
| `sample_rate` | `int` | Actual sampling rate in Hz |
| `reduced_set` | `bool` | Whether raw samples were discarded |
| `started` | `str` | Acquisition start timestamp |
| `stopped` | `str` | Acquisition stop timestamp |
| `duration` | `str` | Acquisition duration |

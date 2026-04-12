"""Integration tests for numeric sampling operations."""

import pytest

from accordionq2 import AccordionQ2ApiError

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Session-scoped fixture: discover the first NumericResult channel with targets
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def nr_channel(client):
    """Return (channel_dto, target_net_name) or skip if none available."""
    channels = client.numeric_results.get_channels()
    ch = next((c for c in channels if c.possible_target_names), None)
    if ch is None:
        pytest.skip("No NumericResult channels with targets found on this device")
    target = ch.possible_target_names[0]
    print("\nNumericResult channel: {} ({})".format(ch.alias, ch.net_name))
    print("Target: {}".format(target))
    return ch, target


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def test_get_channels_returns_list(client):
    channels = client.numeric_results.get_channels()
    print("NumericResult channels: {}".format(len(channels)))
    for ch in channels:
        print("  {} ({}) — {} targets, {}Hz".format(
            ch.alias, ch.net_name, len(ch.possible_target_names), ch.sample_rate))
    assert isinstance(channels, list)


def test_get_channels_have_net_names(client):
    channels = client.numeric_results.get_channels()
    for ch in channels:
        assert ch.net_name, "Channel has no net_name"


def test_get_targets_returns_list(client, nr_channel):
    ch, _ = nr_channel
    targets = client.numeric_results.get_targets(ch.net_name)
    print("Targets for {}: {}".format(ch.alias, targets))
    assert isinstance(targets, list)
    assert len(targets) > 0, "Expected at least one target"


def test_get_targets_invalid_channel_raises(client):
    with pytest.raises(AccordionQ2ApiError):
        client.numeric_results.get_targets("NonExistent.Channel.12345")


# ---------------------------------------------------------------------------
# Measure — ReducedSet=True (default)
# ---------------------------------------------------------------------------

def test_measure_reduced_set_returns_meta(client, nr_channel):
    ch, target = nr_channel
    result = client.numeric_results.measure(
        ch.net_name, target, samples=100, reduced_set=True)

    print("Acquired: SampleRate={}Hz, Duration={}".format(
        result.sample_rate, result.duration))

    assert result.channel_net_name == ch.net_name
    assert result.target_net_name == target
    assert result.reduced_set is True
    assert result.sample_count == 0, \
        "sample_count must be 0 for reduced_set=True (firmware discards samples)"
    assert result.sample_rate > 0


# ---------------------------------------------------------------------------
# Value endpoints after a ReducedSet measurement
# ---------------------------------------------------------------------------

def test_get_mean_returns_finite_value(client, nr_channel):
    ch, target = nr_channel
    client.numeric_results.measure(ch.net_name, target, samples=100, reduced_set=True)

    mean = client.numeric_results.get_mean(ch.net_name)
    print("Mean: {}".format(mean))

    assert isinstance(mean, float), "Mean should be a float"
    assert mean == mean, "Mean must not be NaN"          # NaN != NaN
    assert mean != float("inf"), "Mean must not be Inf"
    assert mean != float("-inf"), "Mean must not be -Inf"


def test_get_min_less_than_or_equal_to_max(client, nr_channel):
    ch, target = nr_channel
    client.numeric_results.measure(ch.net_name, target, samples=100, reduced_set=True)

    min_val = client.numeric_results.get_min(ch.net_name)
    max_val = client.numeric_results.get_max(ch.net_name)
    print("Min={}, Max={}".format(min_val, max_val))

    assert min_val <= max_val, "Min ({}) must be <= Max ({})".format(min_val, max_val)


def test_get_stdev_returns_non_negative(client, nr_channel):
    ch, target = nr_channel
    client.numeric_results.measure(ch.net_name, target, samples=100, reduced_set=True)

    stdev = client.numeric_results.get_stdev(ch.net_name)
    print("StdDev: {}".format(stdev))

    assert stdev >= 0, "Standard deviation ({}) must be >= 0".format(stdev)


# ---------------------------------------------------------------------------
# Samples endpoint
# ---------------------------------------------------------------------------

def test_get_samples_with_reduced_set_raises_400(client, nr_channel):
    ch, target = nr_channel
    client.numeric_results.measure(ch.net_name, target, samples=100, reduced_set=True)

    with pytest.raises(AccordionQ2ApiError) as exc_info:
        client.numeric_results.get_samples(ch.net_name)

    assert exc_info.value.status_code == 400, \
        "Expected HTTP 400, got {}".format(exc_info.value.status_code)
    print("Got expected 400: {}".format(exc_info.value))


def test_get_samples_with_full_set_returns_array(client, nr_channel):
    ch, target = nr_channel
    client.numeric_results.measure(ch.net_name, target, samples=100, reduced_set=False)

    samples = client.numeric_results.get_samples(ch.net_name)
    print("Samples returned: {}".format(len(samples)))

    assert isinstance(samples, list)
    assert len(samples) > 0, "Expected non-empty sample array"
    assert all(isinstance(s, (int, float)) for s in samples)


# ---------------------------------------------------------------------------
# No-result guard
# ---------------------------------------------------------------------------

def test_get_mean_without_prior_measure_raises_404(client):
    # Use a channel name that has never been measured — the server cache will have no entry for it
    with pytest.raises(AccordionQ2ApiError) as exc_info:
        client.numeric_results.get_mean("No.Such.NumericResult.Channel.99999")

    assert exc_info.value.status_code == 404, \
        "Expected HTTP 404, got {}".format(exc_info.value.status_code)
    print("Got expected 404: {}".format(exc_info.value))

"""Performance / throughput tests mirroring PerformanceTests.cs."""

import time

import pytest

from tests.conftest import LED_CHANNELS, UPTIME_RESOURCE

pytestmark = pytest.mark.performance

RAINBOW_COLORS = [
    "Red", "Orange", "Yellow", "Green", "Blue", "Indigo", "Violet",
    "Cyan", "Magenta", "LightBlue", "LimeGreen", "Gold", "HotPink",
]


def test_get_uptime_1000_roundtrips(client):
    """Measure single-resource read throughput over 1000 iterations."""
    iterations = 1000

    # Warm-up
    client.resources.get_value(UPTIME_RESOURCE)

    start = time.perf_counter()

    for _ in range(iterations):
        value = client.resources.get_value(UPTIME_RESOURCE)
        assert value is not None

    elapsed = time.perf_counter() - start
    total_ms = elapsed * 1000
    avg_ms = total_ms / iterations

    print("Roundtrip test: {} iterations".format(iterations))
    print("  Total time : {:.1f} ms".format(total_ms))
    print("  Average    : {:.2f} ms/request".format(avg_ms))
    print("  Throughput : {:.1f} req/s".format(iterations / elapsed))


def test_rainbow_leds_cycle_colors(client):
    """Cycle LED channels through rainbow colors and measure throughput."""
    cycles = 50
    channels = LED_CHANNELS
    color_count = len(RAINBOW_COLORS)
    total_sets = 0

    # Warm-up: set all channels to first color
    for ch in channels:
        client.resources.set_value(ch, RAINBOW_COLORS[0])

    start = time.perf_counter()

    for _ in range(cycles):
        for offset in range(color_count):
            values = {}
            for i, ch in enumerate(channels):
                color_index = (offset + i) % color_count
                values[ch] = RAINBOW_COLORS[color_index]
            client.resources.set_values(values)
            total_sets += 1

    elapsed = time.perf_counter() - start
    total_ms = elapsed * 1000
    avg_ms = total_ms / total_sets

    print("Rainbow LED test: {} cycles x {} steps = {} batch sets".format(
        cycles, color_count, total_sets))
    print("  Channels   : {}".format(len(channels)))
    print("  Total time : {:.1f} ms".format(total_ms))
    print("  Average    : {:.2f} ms/batch".format(avg_ms))
    print("  Throughput : {:.1f} batches/s".format(total_sets / elapsed))
    print("  Per-channel: {:.1f} sets/s".format(
        total_sets * len(channels) / elapsed))

    # Reset all to off
    for ch in channels:
        client.resources.set_value(ch, "Black")

"""Performance / throughput tests mirroring PerformanceTests.cs."""

import time

import pytest

from accordionq2 import AccordionQ2ApiError
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

    # Guard against DNS-per-request regressions (urllib ~625 ms/req on
    # Windows mDNS).  With a persistent connection the average should be
    # well under 100 ms even on modest hardware.
    assert avg_ms < 100, (
        "Average latency {:.1f} ms/request exceeds 100 ms — "
        "possible per-request DNS resolution regression".format(avg_ms)
    )


def test_rainbow_leds_cycle_colors(client):
    """Cycle LED channels through rainbow colors and measure throughput."""
    cycles = 50
    channels = LED_CHANNELS
    color_count = len(RAINBOW_COLORS)
    total_sets = 0

    # Warm-up: set all channels to first color — skip if hardware not present
    for ch in channels:
        try:
            client.resources.set_value(ch, RAINBOW_COLORS[0])
        except AccordionQ2ApiError as exc:
            if "no such net name" in str(exc).lower() or "not found" in str(exc).lower():
                pytest.skip("LED channel {} not present on this hardware: {}".format(ch, exc))
            raise

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


def test_connection_reuse_latency(client):
    """Verify the persistent connection removes per-request DNS overhead.

    After a warm-up request (which resolves DNS and opens the socket),
    subsequent requests should be significantly faster.  On Windows with
    mDNS (.local) names, a per-request DNS lookup adds ~625 ms.  With
    connection reuse the second request should be well under 200 ms.
    """
    # The session-scoped client fixture has already made requests, so the
    # connection is warm.  Measure a burst of 10 back-to-back requests.
    burst = 10
    times = []
    for _ in range(burst):
        t0 = time.perf_counter()
        client.resources.get_value(UPTIME_RESOURCE)
        times.append((time.perf_counter() - t0) * 1000)

    avg_ms = sum(times) / len(times)
    max_ms = max(times)

    print("Connection-reuse burst ({} requests):".format(burst))
    print("  Average : {:.2f} ms".format(avg_ms))
    print("  Max     : {:.2f} ms".format(max_ms))

    assert avg_ms < 200, (
        "Average burst latency {:.1f} ms exceeds 200 ms — "
        "connection may not be reused".format(avg_ms)
    )

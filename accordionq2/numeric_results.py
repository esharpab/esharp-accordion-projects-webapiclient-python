"""Fast numeric sampling operations."""

from __future__ import annotations

import base64
import struct
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote as _quote

from ._base import ApiGroupBase
from .models import NumericMeasureResultDto, NumericResultChannelDto


@dataclass(frozen=True, slots=True)
class NumericAcquisition:
    """One acquisition: the samples and their statistics.

    A statistic the samples can't give is ``None``.
    """

    channel: str
    target: str
    #: The target channel's unit.
    unit: str
    #: The sample rate the hardware reported, in Hz.
    sample_rate: int
    started: str
    duration_ms: float | None
    samples: tuple[float, ...] = field(hash=False)
    #: ``count``, ``min``, ``max``, ``range``, ``mean``, ``median``, ``stdev``, ``rms``,
    #: ``skewness``, ``kurtosis``, and ``cp``/``cpk`` with limits.
    stats: dict[str, Any] = field(default_factory=dict, hash=False)


class NumericResultsGroup(ApiGroupBase):
    """Operations for fast numeric sampling via dedicated NumericResult channels.

    Typical workflow::

        # 1. Discover available NumericResult channels
        channels = client.numeric_results.get_channels()

        # 2. Check what a channel can sample
        targets = client.numeric_results.get_targets(channels[0].net_name)

        # 3. Trigger acquisition (result cached server-side)
        meta = client.numeric_results.measure(
            channels[0].net_name, targets[0], samples=1000, reduced_set=True)

        # 4. Fetch statistics
        mean  = client.numeric_results.get_mean(channels[0].net_name)
        stdev = client.numeric_results.get_stdev(channels[0].net_name)
    """

    def acquire(
        self,
        channel: str,
        target: str,
        samples: int = 1000,
        lsl: float | None = None,
        usl: float | None = None,
    ) -> NumericAcquisition:
        """Acquire *samples* on *target* and return them with their statistics in one call.

        (accordionq2 contract section 8.) With both limits, ``cp`` and ``cpk``
        are in the statistics. It reconfigures the channel, so it needs the
        lease while someone else holds it.
        """
        body: dict[str, object] = {"Channel": channel, "Target": target, "Samples": samples}
        if lsl is not None:
            body["Lsl"] = lsl
        if usl is not None:
            body["Usl"] = usl
        result = self._post_json("api/numeric-results/acquire", body)
        assert isinstance(result, dict)
        raw = base64.b64decode(result.get("samples") or "")
        values = struct.unpack(f"<{len(raw) // 8}d", raw)
        return NumericAcquisition(
            channel=result.get("channel", ""),
            target=result.get("target", ""),
            unit=result.get("unit", ""),
            sample_rate=int(result.get("sampleRate", 0)),
            started=result.get("started", ""),
            duration_ms=result.get("durationMs"),
            samples=values,
            stats=dict(result.get("stats") or {}),
        )

    def get_channels(self) -> list[NumericResultChannelDto]:
        """Return all NumericResult channels with their sampling capabilities."""
        data = self._get_json("api/numeric-results/channels")
        assert isinstance(data, list)
        return [NumericResultChannelDto.from_dict(ch) for ch in data]

    def get_targets(self, channel_net_name: str) -> list[str]:
        """Return the physical channel net names that *channel_net_name* can sample.

        Args:
            channel_net_name: Net name of the NumericResult channel.

        Returns:
            A list of strings.
        """
        path = "api/numeric-results/targets?channel={}".format(_quote(channel_net_name, safe=""))
        result = self._get_json(path)
        assert isinstance(result, list)
        return result

    def measure(
        self,
        channel_net_name: str,
        target_net_name: str,
        samples: int = 1000,
        reduced_set: bool = True,
    ) -> NumericMeasureResultDto:
        """Configure and trigger a numeric sampling acquisition.

        The result is cached server-side.  Call :meth:`get_mean`, :meth:`get_min`,
        :meth:`get_max`, :meth:`get_stdev` (or :meth:`get_samples` when
        *reduced_set* is ``False``) to read values.

        Args:
            channel_net_name: Net name of the NumericResult channel.
            target_net_name:  Net name of the physical channel to sample.
            samples:          Number of samples to acquire (default 1000).
            reduced_set:      When ``True`` (default) the firmware discards raw
                              samples after computing summary statistics.

        Returns:
            A :class:`~accordionq2.models.NumericMeasureResultDto` with acquisition metadata.
        """
        body = {
            "ChannelNetName": channel_net_name,
            "TargetNetName": target_net_name,
            "Samples": samples,
            "ReducedSet": reduced_set,
        }
        result = self._post_json("api/numeric-results/measure", body)
        assert isinstance(result, dict)
        return NumericMeasureResultDto.from_dict(result)

    def get_mean(self, channel_net_name: str) -> float:
        """Return the mean value from the last measurement on *channel_net_name*."""
        return self._get_stat("mean", channel_net_name)

    def get_min(self, channel_net_name: str) -> float:
        """Return the minimum value from the last measurement on *channel_net_name*."""
        return self._get_stat("min", channel_net_name)

    def get_max(self, channel_net_name: str) -> float:
        """Return the maximum value from the last measurement on *channel_net_name*."""
        return self._get_stat("max", channel_net_name)

    def get_stdev(self, channel_net_name: str) -> float:
        """Return the standard deviation from the last measurement on *channel_net_name*."""
        return self._get_stat("stdev", channel_net_name)

    def get_samples(self, channel_net_name: str) -> list[float]:
        """Return the raw sample array from the last measurement on *channel_net_name*.

        Raises :class:`~accordionq2.AccordionQ2ApiError` (HTTP 400) if the
        measurement was taken with ``reduced_set=True``.
        """
        path = "api/numeric-results/result/samples?channel={}".format(
            _quote(channel_net_name, safe="")
        )
        result = self._get_json(path)
        assert isinstance(result, list)
        return result

    # ------------------------------------------------------------------

    def _get_stat(self, stat: str, channel_net_name: str) -> float:
        path = "api/numeric-results/result/{}?channel={}".format(
            stat, _quote(channel_net_name, safe="")
        )
        raw = self._get_json(path)
        return float(raw)  # type: ignore[arg-type]

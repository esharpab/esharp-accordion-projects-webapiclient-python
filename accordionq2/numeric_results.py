"""Fast numeric sampling operations."""

from __future__ import annotations

from urllib.parse import quote as _quote

from ._base import ApiGroupBase
from .models import NumericMeasureResultDto, NumericResultChannelDto


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
        path = "api/numeric-results/targets?channel={}".format(
            _quote(channel_net_name, safe=""))
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
            "TargetNetName":  target_net_name,
            "Samples":        samples,
            "ReducedSet":     reduced_set,
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
            _quote(channel_net_name, safe=""))
        result = self._get_json(path)
        assert isinstance(result, list)
        return result

    # ------------------------------------------------------------------

    def _get_stat(self, stat: str, channel_net_name: str) -> float:
        path = "api/numeric-results/result/{}?channel={}".format(
            stat, _quote(channel_net_name, safe=""))
        raw = self._get_json(path)
        return float(raw)  # type: ignore[arg-type]

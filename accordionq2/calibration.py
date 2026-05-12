"""Calibration channel read/write operations."""

from __future__ import annotations

from urllib.parse import quote as _quote

from ._base import ApiGroupBase
from .models import CalibrationChannelDto, CalibrationTableDto


class CalibrationGroup(ApiGroupBase):
    """Operations for reading and writing Calibration channel tables.

    Calibration channels carry a ``CalibrationTable`` encoded as a Base64 binary
    payload on the wire.  The server transparently decodes and encodes that payload,
    so you always work with plain :class:`~accordionq2.models.CalibrationTableDto`
    objects.

    Both **NetName** and **Alias** are accepted wherever a channel name is required.

    Typical workflow::

        # 1. Discover available Calibration channels
        channels = client.calibration.get_channels()
        for ch in channels:
            print(ch.net_name, ch.alias)

        # 2. Read the current table (by NetName or Alias)
        table = client.calibration.get_table(channels[0].net_name)
        for row in table.cal_data:
            print(f"{row.key}: gain={row.gain:.6f}, offset={row.offset:.6f}")

        # 3. Modify a row and write back
        new_rows = [
            row._replace(gain=1.0012, offset=0.001) if row.key == "ADC0" else row
            for row in table.cal_data
        ]
        import dataclasses
        updated = dataclasses.replace(table, cal_data=new_rows)
        client.calibration.set_table(channels[0].net_name, updated)
    """

    def get_channels(self) -> list[CalibrationChannelDto]:
        """Return all Calibration channels."""
        data = self._get_json("api/calibration/channels")
        assert isinstance(data, list)
        return [CalibrationChannelDto.from_dict(ch) for ch in data]

    def get_table(self, channel_name: str) -> CalibrationTableDto:
        """Read and decode the CalibrationTable from a Calibration channel.

        Args:
            channel_name: Net name or Alias of the Calibration channel.

        Returns:
            A :class:`~accordionq2.models.CalibrationTableDto` with the decoded table.
        """
        path = "api/calibration/table?channel={}".format(_quote(channel_name, safe=""))
        data = self._get_json(path)
        assert isinstance(data, dict)
        return CalibrationTableDto.from_dict(data)

    def set_table(self, channel_name: str, table: CalibrationTableDto) -> None:
        """Encode and write a CalibrationTable to a Calibration channel.

        Args:
            channel_name: Net name or Alias of the Calibration channel.
            table:        The calibration table to write.
        """
        self._post(
            "api/calibration/table",
            {
                "ChannelNetName": channel_name,
                "Table": table.to_dict(),
            },
        )

"""Instrument operations."""

from __future__ import annotations

from ._base import ApiGroupBase
from .models import InstrumentDto


class InstrumentsGroup(ApiGroupBase):
    """The station's instruments, such as power-supply outputs."""

    def get_all(self) -> list[InstrumentDto]:
        """Return every Instrument channel with its type and function map."""
        result = self._get_json("api/instruments")
        assert isinstance(result, list)
        return [InstrumentDto.from_dict(item) for item in result]

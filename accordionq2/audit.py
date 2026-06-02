"""Audit log operations."""

from __future__ import annotations

from ._base import ApiGroupBase


class AuditGroup(ApiGroupBase):
    """WebApi audit log operations."""

    def get_audit_log(self, tail: int = 100) -> list[str]:
        """Return the last *tail* lines of the WebApi audit log.

        Pass ``tail=0`` to retrieve the entire log.
        """
        result = self._get_json(f"api/audit/log?tail={tail}")
        assert isinstance(result, list)
        return result

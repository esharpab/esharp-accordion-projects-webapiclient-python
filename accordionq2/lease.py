"""The control lease (accordionq2 contract section 5.5)."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from ._base import ApiGroupBase
from .exceptions import AccordionQ2ApiError

HEADER = "X-Lease-Id"


@dataclass(frozen=True, slots=True)
class LeaseDto:
    """Who holds the lease, or the lease this client took."""

    held: bool = False
    owner: str | None = None
    expires_in_ms: float = 0.0
    lease_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LeaseDto:
        return cls(
            held=bool(data.get("held", data.get("leaseId") is not None)),
            owner=data.get("owner") or data.get("heldBy"),
            expires_in_ms=float(data.get("expiresInMs", 0)),
            lease_id=data.get("leaseId"),
        )


class LeaseGroup(ApiGroupBase):
    """One client at a time may change the station; typically a test station for a sequence.

    While another client holds it, this client's writes and forced reads raise
    :class:`AccordionQ2ApiError` with status 423; reads with ``max_age_ms`` and
    subscriptions keep working. After :meth:`acquire` this client sends the
    lease id with every request, so its own changes go through::

        with client.lease.hold("TAT station 3"):
            client.resources.set_value("0.4.ESH10000662.VSET1", "5")
    """

    @property
    def held_lease_id(self) -> str | None:
        """The lease this client holds, if any."""
        return self._session.default_headers.get(HEADER)

    def get(self) -> LeaseDto:
        """Who holds the lease, if anyone."""
        result = self._get_json("api/lease")
        assert isinstance(result, dict)
        return LeaseDto.from_dict(result)

    def acquire(self, owner: str, ttl_ms: int = 30000) -> LeaseDto:
        """Take the lease; raises ``AccordionQ2ApiError`` (409) when someone else holds it."""
        result = self._post_json("api/lease", {"Owner": owner, "TtlMs": ttl_ms})
        assert isinstance(result, dict)
        lease = LeaseDto.from_dict(result)
        if lease.lease_id:
            self._session.set_default_header(HEADER, lease.lease_id)
        return lease

    def renew(self, ttl_ms: int | None = None) -> LeaseDto:
        """Renew the lease this client holds; raises (404) once it has ended."""
        lease_id = self.held_lease_id
        if lease_id is None:
            raise RuntimeError("This client holds no lease")
        body: dict[str, Any] = {} if ttl_ms is None else {"TtlMs": ttl_ms}
        result = self._put_json(f"api/lease/{lease_id}", body)
        assert isinstance(result, dict)
        return LeaseDto.from_dict(result)

    def release(self) -> None:
        """Release the lease this client holds; does nothing when it holds none."""
        lease_id = self.held_lease_id
        if lease_id is None:
            return
        self._session.set_default_header(HEADER, None)
        try:
            self._delete(f"api/lease/{lease_id}")
        except AccordionQ2ApiError as error:
            if error.status_code != 404:  # already ended
                raise

    @contextmanager
    def hold(self, owner: str, ttl_ms: int = 30000) -> Iterator[LeaseDto]:
        """Hold the lease for a ``with`` block, renewing it in the background, and release it after.

        Renewal runs every third of *ttl_ms*, so a crashed script loses the
        lease within *ttl_ms*.
        """
        lease = self.acquire(owner, ttl_ms)
        stop = threading.Event()

        def renew_loop() -> None:
            while not stop.wait(ttl_ms / 3000):
                try:
                    self.renew()
                except Exception:
                    return  # ended; the block's own requests will say so

        renewer = threading.Thread(target=renew_loop, name="lease-renewal", daemon=True)
        renewer.start()
        try:
            yield lease
        finally:
            stop.set()
            renewer.join(timeout=5)
            self.release()

"""Value subscriptions (accordionq2 contract section 5.3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._base import ApiGroupBase


@dataclass(frozen=True, slots=True)
class SubscriptionDto:
    """A subscription as created or renewed."""

    id: str = ""
    #: It ends unless renewed (:meth:`SubscriptionsGroup.update`) within this long.
    expires_in_ms: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SubscriptionDto:
        return cls(id=data.get("id", ""), expires_in_ms=int(data.get("expiresInMs", 0)))


class SubscriptionsGroup(ApiGroupBase):
    """Values of the named channels about every interval, as ``values`` events on an event stream.

    One scheduler on the WebApi reads for every subscription, through its
    value cache, so channels several clients watch are read once.
    """

    def create(
        self, stream_id: str, channels: list[str], interval_ms: int = 1000
    ) -> SubscriptionDto:
        """Subscribe the stream *stream_id* (``EventStream.stream_id``) to *channels*.

        The subscription ends with the stream, on :meth:`delete`, or when not
        renewed with :meth:`update` within ``expires_in_ms`` (60 s).
        """
        body = {"StreamId": stream_id, "Channels": list(channels), "IntervalMs": interval_ms}
        result = self._post_json("api/subscriptions", body)
        assert isinstance(result, dict)
        return SubscriptionDto.from_dict(result)

    def update(
        self, subscription_id: str, channels: list[str], interval_ms: int = 1000
    ) -> SubscriptionDto:
        """Replace the subscription's channels and interval, and renew it."""
        body = {"Channels": list(channels), "IntervalMs": interval_ms}
        result = self._put_json(f"api/subscriptions/{subscription_id}", body)
        assert isinstance(result, dict)
        return SubscriptionDto.from_dict(result)

    def delete(self, subscription_id: str) -> None:
        """End the subscription."""
        self._delete(f"api/subscriptions/{subscription_id}")

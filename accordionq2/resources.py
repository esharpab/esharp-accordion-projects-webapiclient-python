"""Resource read/write operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from ._base import ApiGroupBase, HttpSession
from .capabilities import CapabilitiesDto, CapabilitiesGroup
from .exceptions import AccordionQ2ApiError, AccordionQ2NotSupportedError


@dataclass(frozen=True, slots=True)
class CachedValues:
    """What :meth:`ResourcesGroup.read_cached` answers (accordionq2 contract section 5.2).

    A name is in :attr:`values` and :attr:`ages_ms`, or in :attr:`not_cached`, never both.
    """

    #: Each name the cache had a value for, and the value.
    values: dict[str, str]
    #: How old each value in :attr:`values` is, in ms.
    ages_ms: dict[str, float]
    #: The names it had no value for (none fresh enough, or a channel whose reads consume
    #: data), in the order asked; empty when every name was cached.
    not_cached: tuple[str, ...]


def _extract_value(result: object, path: str) -> str:
    """Extract the ``value`` field from a JSON response dict.

    Accepts both ``"value"`` (lowercase) and ``"Value"`` (uppercase) to be
    robust against server-side casing variations.
    """
    if not isinstance(result, dict):
        raise AccordionQ2ApiError(200, f"Unexpected response shape from {path}: {result!r}")
    for key in ("value", "Value"):
        if key in result:
            return cast(str, result[key])
    raise AccordionQ2ApiError(200, f"Missing 'value' key in response from {path}: {result!r}")


class ResourcesGroup(ApiGroupBase):
    """Operations for reading and writing hardware resource values.

    Resources are identified by name (e.g. ``"Voltage.VDD"``,
    ``"Temperature.Ambient"``).
    """

    def __init__(self, session: HttpSession) -> None:
        super().__init__(session)
        self._cache_only_checked = False

    def get_names(self) -> list[str]:
        """Return the names of all available resources."""
        result = self._get_json("api/resources/names")
        assert isinstance(result, list)
        return result

    def get_value(self, name: str) -> str:
        """Read the current value of a single resource."""
        path = "api/resources/value/get"
        result = self._post_json(path, {"Name": name})
        return _extract_value(result, path)

    def set_value(self, name: str, value: str) -> None:
        """Set the value of a single resource."""
        self._post("api/resources/value/set", {"Name": name, "Value": value})

    def get_values(self, names: list[str], max_age_ms: int = 0) -> dict[str, str]:
        """Read values for multiple resources in one round-trip.

        Returns a dict mapping each resource name to its current value string.
        With *max_age_ms*, values the WebApi read at most that long ago are
        returned from its cache (accordionq2 contract section 5.2); 0 reads
        every one from the hardware.
        """
        return self.read_values(names, max_age_ms)[0]

    def read_values(
        self, names: list[str], max_age_ms: int = 0
    ) -> tuple[dict[str, str], dict[str, float]]:
        """Like :meth:`get_values`, and also how old each value is in ms (0 when just read).

        A WebApi without the cache reads every value and reports no ages.
        """
        body: dict[str, object] = {"Names": names}
        if max_age_ms:
            body["MaxAgeMs"] = max_age_ms
        result = self._post_json("api/resources/values/get", body)
        assert isinstance(result, dict)
        ages = result.get("ageMs") or {}
        return cast(dict[str, str], result["resources"]), {k: float(v) for k, v in ages.items()}

    def read_cached(self, names: list[str], max_age_ms: int = 0) -> CachedValues:
        """Read several resources from the WebApi's value cache alone (``cacheOnly``).

        The station never reads the hardware for this call and the lease never refuses it,
        so it can't switch a mux or reset a peak buffer under a running test. A name with no
        cached value at most *max_age_ms* old is in :attr:`CachedValues.not_cached`, and so
        is every channel whose reads consume data. *max_age_ms* 0 takes a cached value of
        any age; :attr:`CachedValues.ages_ms` says how old each is.

        The first call asks ``GET /api/capabilities`` for
        :attr:`CapabilitiesDto.VALUES_CACHE_ONLY`, since an older WebApi ignores
        ``cacheOnly`` and reads the hardware. Without it this raises
        :class:`AccordionQ2NotSupportedError` and asks for no values; it raises it too
        when an answer has no ``notCached``. A name no channel has is an
        :class:`AccordionQ2ApiError` 400, as with the other reads.
        """
        feature = CapabilitiesDto.VALUES_CACHE_ONLY
        if not self._cache_only_checked:
            if not CapabilitiesGroup(self._session).get().has(feature):
                raise AccordionQ2NotSupportedError(
                    feature,
                    f"The station doesn't offer cache-only reads (feature {feature!r}, "
                    "firmware 7.0.5 or later); nothing was read",
                )
            self._cache_only_checked = True
        body = {"Names": names, "MaxAgeMs": max_age_ms, "CacheOnly": True}
        result = self._post_json("api/resources/values/get", body)
        not_cached = result.get("notCached") if isinstance(result, dict) else None
        if not isinstance(result, dict) or not isinstance(not_cached, list):
            raise AccordionQ2NotSupportedError(
                feature,
                "The station answered without notCached: it ignored cacheOnly "
                "and may have read the hardware",
            )
        ages = result.get("ageMs") or {}
        return CachedValues(
            values=cast(dict[str, str], result.get("resources") or {}),
            ages_ms={k: float(v) for k, v in ages.items()},
            not_cached=tuple(str(n) for n in not_cached),
        )

    def set_values(self, resources: dict[str, str]) -> None:
        """Set values for multiple resources in one round-trip.

        *resources* is a ``dict[str, str]`` mapping names to values.
        """
        self._post("api/resources/values/set", {"Resources": resources})

    def transact(self, name: str, value: str) -> str:
        """Perform a write-then-read transaction on a resource.

        Useful for EEPROM commands, register access, or other stateful
        resources.  Returns the response value string.
        """
        path = "api/resources/transact"
        result = self._post_json(path, {"Name": name, "Value": value})
        return _extract_value(result, path)

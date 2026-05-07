"""Resource read/write operations."""

from __future__ import annotations

from typing import cast

from ._base import ApiGroupBase
from .exceptions import AccordionQ2ApiError


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

    def get_values(self, names: list[str]) -> dict[str, str]:
        """Read values for multiple resources in one round-trip.

        Returns a dict mapping each resource name to its current value string.
        """
        result = self._post_json("api/resources/values/get", {"Names": names})
        assert isinstance(result, dict)
        return cast(dict[str, str], result["resources"])

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

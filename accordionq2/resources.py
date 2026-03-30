"""Resource read/write operations."""

from ._base import ApiGroupBase


class ResourcesGroup(ApiGroupBase):
    """Operations for reading and writing hardware resource values.

    Resources are identified by name (e.g. ``"Voltage.VDD"``,
    ``"Temperature.Ambient"``).
    """

    def get_names(self):
        """Return the names of all available resources."""
        return self._get_json("api/resources/names")

    def get_value(self, name):
        """Read the current value of a single resource."""
        result = self._post_json("api/resources/value/get", {"Name": name})
        return result["Value"]

    def set_value(self, name, value):
        """Set the value of a single resource."""
        self._post("api/resources/value/set", {"Name": name, "Value": value})

    def get_values(self, names):
        """Read values for multiple resources in one round-trip.

        Returns a dict mapping each resource name to its current value string.
        """
        result = self._post_json("api/resources/values/get", {"Names": names})
        return result["Resources"]

    def set_values(self, resources):
        """Set values for multiple resources in one round-trip.

        *resources* is a ``dict[str, str]`` mapping names to values.
        """
        self._post("api/resources/values/set", {"Resources": resources})

    def transact(self, name, value):
        """Perform a write-then-read transaction on a resource.

        Useful for EEPROM commands, register access, or other stateful
        resources.  Returns the response value string.
        """
        result = self._post_json(
            "api/resources/transact", {"Name": name, "Value": value}
        )
        return result["Value"]

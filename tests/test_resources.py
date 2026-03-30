"""Integration tests for resource operations."""

import pytest

from tests.conftest import CPU_TEMP_RESOURCE, MON_3V3_RESOURCE, UPTIME_RESOURCE

pytestmark = pytest.mark.integration


def test_get_names_returns_non_empty(client):
    names = client.resources.get_names()
    print("Resource names count: {}".format(len(names)))
    for n in names:
        print("  Resource: {}".format(n))
    assert names
    assert len(names) > 0, "Expected at least one resource name"


def test_get_names_contains_known_resources(client):
    names = client.resources.get_names()
    assert CPU_TEMP_RESOURCE in names
    assert MON_3V3_RESOURCE in names
    assert UPTIME_RESOURCE in names


def test_get_value_cpu_temp_returns_numeric(client):
    value = client.resources.get_value(CPU_TEMP_RESOURCE)
    print("CpuTemp raw value: '{}'".format(value))
    temp = float(value)
    print("CpuTemp parsed: {}C".format(temp))
    assert 0 < temp < 120, "CPU temp {}C seems out of range".format(temp)


def test_get_value_mon_3v3_returns_voltage_in_range(client):
    value = client.resources.get_value(MON_3V3_RESOURCE)
    print("Mon3V3 raw value: '{}'".format(value))
    voltage = float(value)
    print("Mon3V3 parsed: {}V".format(voltage))
    assert 2.5 < voltage < 4.0, \
        "3.3V rail at {}V seems out of range".format(voltage)


def test_get_value_uptime_returns_non_empty(client):
    value = client.resources.get_value(UPTIME_RESOURCE)
    print("Uptime: '{}'".format(value))
    assert value
    assert value.strip(), "Uptime should not be empty"


def test_get_values_multiple_resources(client):
    names = [CPU_TEMP_RESOURCE, MON_3V3_RESOURCE, UPTIME_RESOURCE]
    values = client.resources.get_values(names)
    print("GetValues returned {} entries:".format(len(values)))
    for k, v in values.items():
        print("  {} = '{}'".format(k, v))
    assert len(values) == len(names), \
        "Should return a value for each requested resource"
    for name in names:
        assert name in values, "Missing value for '{}'".format(name)
        assert values[name], "Value for '{}' should not be empty".format(name)

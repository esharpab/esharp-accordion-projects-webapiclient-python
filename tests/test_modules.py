"""Integration tests for module operations."""

import pytest

from accordionq2 import AccordionQ2ApiError
from tests.conftest import (
    BASE_MODULE_NAME,
    BASE_MODULE_PRODUCT_ID,
    EXPECTED_HOST_NAME,
)

pytestmark = pytest.mark.integration


def test_get_all_returns_modules(client):
    modules = client.modules.get_all()
    print("Modules count: {}".format(len(modules)))
    for m in modules:
        print("  Module: {} | Enabled={} | Class={}".format(
            m.name, m.enabled, m.class_name))
    assert modules
    assert len(modules) > 0, "Expected at least one module"


def test_get_loaded_returns_list(client):
    loaded = client.modules.get_loaded()
    print("Loaded modules count: {}".format(len(loaded)))
    for m in loaded:
        print("  Loaded: {} | Class={}".format(m.name, m.class_name))
    assert loaded is not None


def test_get_physical_system_returns_host_info(client):
    system = client.modules.get_physical_system()
    print("Host: {}".format(system.host))
    print("EthIpV4: {}".format(system.eth_ip_v4))
    print("EthIpV6: {}".format(system.eth_ip_v6))
    print("MAC: {}".format(system.mac))
    print("Firmware: {}".format(system.firmware))
    assert system.host.lower() == EXPECTED_HOST_NAME.lower()
    assert system.eth_ip_v4, "Expected an IPv4 address"


def test_get_physical_system_contains_base_module(client):
    system = client.modules.get_physical_system()
    print("Physical modules count: {}".format(len(system.modules)))
    for m in system.modules:
        print("  Slot {}: {} | ProductID={} | Rev={} | SN={}".format(
            m.index, m.name, m.product_id, m.revision, m.serial_number))
    assert system.modules
    assert len(system.modules) > 0, "Expected at least one physical module"
    base = next(
        (m for m in system.modules if m.product_id == BASE_MODULE_PRODUCT_ID),
        None,
    )
    assert base is not None, \
        "Expected base module with ProductID '{}'".format(BASE_MODULE_PRODUCT_ID)
    assert base.name == BASE_MODULE_NAME


def test_get_all_apps_returns_list(client):
    try:
        apps = client.modules.get_all_apps()
        print("All apps count: {}".format(len(apps)))
        for a in apps:
            print("  App: {} | Key={} | Type={} | Expires={}".format(
                a.name, a.key, a.type, a.expires))
        assert apps is not None
    except AccordionQ2ApiError as exc:
        if "timeout" in str(exc).lower():
            pytest.skip("Server-side timeout: {}".format(exc))
        raise


def test_get_licensed_apps_returns_list(client):
    try:
        apps = client.modules.get_licensed_apps()
        print("Licensed apps count: {}".format(len(apps)))
        for a in apps:
            print("  Licensed: {} | Key={} | Type={} | Expires={}".format(
                a.name, a.key, a.type, a.expires))
        assert apps is not None
    except AccordionQ2ApiError as exc:
        if "timeout" in str(exc).lower():
            pytest.skip("Server-side timeout: {}".format(exc))
        raise

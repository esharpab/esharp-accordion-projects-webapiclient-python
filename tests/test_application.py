"""Integration tests for application operations."""

import pytest

from accordionq2.enums import ModuleStatus

pytestmark = pytest.mark.integration


def test_get_name_returns_non_empty(client):
    name = client.application.get_name()
    print("Application name: '{}'".format(name))
    assert name
    assert name.strip(), "Application name should not be empty"


def test_get_identification_returns_non_empty(client):
    identification = client.application.get_identification()
    print("Identification: '{}'".format(identification))
    assert identification
    assert identification.strip(), "Identification should not be empty"


def test_get_status_returns_valid_enum(client):
    status = client.application.get_status()
    print("Application status: {}".format(status))
    assert isinstance(status, ModuleStatus)


def test_list_config_files_returns_list(client):
    files = client.application.list_config_files()
    print("Config files count: {}".format(len(files)))
    for f in files:
        print("  File: {}".format(f))
    assert files is not None


def test_get_loaded_config_files_returns_list(client):
    files = client.application.get_loaded_config_files()
    print("Loaded config files count: {}".format(len(files)))
    for f in files:
        print("  Loaded: {}".format(f))
    assert files is not None

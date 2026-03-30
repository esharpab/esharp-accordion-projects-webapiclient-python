"""Integration tests for connection status."""

import pytest

pytestmark = pytest.mark.integration


def test_get_status_returns_connected(client):
    status = client.connection.get_status()

    print("IsConnected: {}".format(status.is_connected))
    print("LastError: {}".format(status.last_error or "(none)"))

    assert status.is_connected, "API should be connected to the hardware manager"
    assert status.last_error is None, \
        "Unexpected connection error: {}".format(status.last_error)

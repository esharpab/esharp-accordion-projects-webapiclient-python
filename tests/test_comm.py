"""Integration tests for raw bus transaction operations (I2C, UART, SPI, Socket)."""

import pytest

from accordionq2.enums import BusActions
from accordionq2.exceptions import AccordionQ2ApiError
from tests.conftest import I2C_DEVICE_NAME

pytestmark = pytest.mark.integration


# -----------------------------------------------------------------------------
# I2C
# -----------------------------------------------------------------------------

def test_i2c_scan_known_bus_returns_response(client):
    resp = client.comm.i2c(I2C_DEVICE_NAME, address=0x00, action=BusActions.SCAN)

    assert resp is not None
    assert resp.action == "Scan"
    assert resp.device_name == I2C_DEVICE_NAME
    assert len(resp.received) == resp.number_of_bytes_received, (
        "number_of_bytes_received must match the actual received-bytes length"
    )

    print("I2C scan on '{}': {} device(s) found".format(resp.device_name, resp.number_of_bytes_received))
    for addr in resp.received:
        print("  0x{:02X}".format(addr))


def test_i2c_scan_response_device_name_matches_request(client):
    resp = client.comm.i2c(I2C_DEVICE_NAME, address=0x00, action=BusActions.SCAN)

    assert resp.device_name == I2C_DEVICE_NAME, (
        "Response device_name must echo the requested device"
    )


def test_i2c_send_null_data_raises_error(client):
    with pytest.raises(AccordionQ2ApiError):
        client.comm.i2c(I2C_DEVICE_NAME, address=0x50,
                        action=BusActions.SEND, data_to_send=None)


def test_i2c_send_empty_data_raises_error(client):
    with pytest.raises(AccordionQ2ApiError):
        client.comm.i2c(I2C_DEVICE_NAME, address=0x50,
                        action=BusActions.SEND, data_to_send=b"")


def test_i2c_send_receive_empty_data_raises_error(client):
    with pytest.raises(AccordionQ2ApiError):
        client.comm.i2c(I2C_DEVICE_NAME, address=0x50,
                        action=BusActions.SEND_RECEIVE, data_to_send=b"",
                        number_of_bytes_to_receive=4)


# -----------------------------------------------------------------------------
# UART
# -----------------------------------------------------------------------------

def test_uart_send_null_data_raises_error(client):
    with pytest.raises(AccordionQ2ApiError):
        client.comm.uart("validation-only", action=BusActions.SEND, data_to_send=None)


def test_uart_send_empty_data_raises_error(client):
    with pytest.raises(AccordionQ2ApiError):
        client.comm.uart("validation-only", action=BusActions.SEND, data_to_send=b"")


def test_uart_send_receive_empty_data_raises_error(client):
    with pytest.raises(AccordionQ2ApiError):
        client.comm.uart("validation-only", action=BusActions.SEND_RECEIVE,
                         data_to_send=b"", number_of_bytes_to_receive=32,
                         timeout_ms=500)


# -----------------------------------------------------------------------------
# SPI
# -----------------------------------------------------------------------------

def test_spi_send_null_data_raises_error(client):
    with pytest.raises(AccordionQ2ApiError):
        client.comm.spi("validation-only", action=BusActions.SEND, data_to_send=None)


def test_spi_send_empty_data_raises_error(client):
    with pytest.raises(AccordionQ2ApiError):
        client.comm.spi("validation-only", action=BusActions.SEND, data_to_send=b"")


def test_spi_send_receive_empty_data_raises_error(client):
    with pytest.raises(AccordionQ2ApiError):
        client.comm.spi("validation-only", action=BusActions.SEND_RECEIVE,
                        data_to_send=b"", number_of_bytes_to_receive=4)


# -----------------------------------------------------------------------------
# Socket
# -----------------------------------------------------------------------------

def test_socket_send_null_data_raises_error(client):
    with pytest.raises(AccordionQ2ApiError):
        client.comm.socket("validation-only", action=BusActions.SEND,
                           host_name="127.0.0.1", port=9999, data_to_send=None)


def test_socket_send_empty_data_raises_error(client):
    with pytest.raises(AccordionQ2ApiError):
        client.comm.socket("validation-only", action=BusActions.SEND,
                           host_name="127.0.0.1", port=9999, data_to_send=b"")


def test_socket_send_receive_empty_data_raises_error(client):
    with pytest.raises(AccordionQ2ApiError):
        client.comm.socket("validation-only", action=BusActions.SEND_RECEIVE,
                           host_name="127.0.0.1", port=9999,
                           data_to_send=b"", number_of_bytes_to_receive=64)

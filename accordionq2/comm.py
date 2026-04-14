"""Raw bus transaction operations (I2C, UART, SPI, Socket)."""

from ._base import ApiGroupBase
from .enums import BusActions
from .models import BusTransactionResponse


def _to_hex(data):
    """Encode a bytes-like object as an uppercase hex string for JSON transport."""
    if data is None:
        return None
    return bytes(data).hex().upper()


def _action_value(action):
    """Return the JSON string for a BusActions value or plain string."""
    if isinstance(action, BusActions):
        return action.value
    return str(action)


class CommGroup(ApiGroupBase):
    """Operations for performing raw bus transactions (I2C, UART, SPI, Socket).

    Bytes are hex-encoded on the wire; the client handles encoding and
    decoding transparently so callers work with plain :class:`bytes` objects.

    Usage::

        # I2C: write two bytes to device address 0x50
        resp = client.comm.i2c("0.ESH10000597.I2C00", address=0x50,
                               action=BusActions.SEND, data_to_send=bytes([0x00, 0xFF]))

        # I2C: read 4 bytes
        resp = client.comm.i2c("0.ESH10000597.I2C00", address=0x50,
                               action=BusActions.RECEIVE, number_of_bytes_to_receive=4)
        print(resp.received)  # bytes

        # I2C: scan the bus for connected devices
        resp = client.comm.i2c("0.ESH10000597.I2C00", address=0x00,
                               action=BusActions.SCAN)
        print(resp.received)  # bytes containing found addresses

        # UART: send and receive
        resp = client.comm.uart("MyUartDevice",
                                action=BusActions.SEND_RECEIVE,
                                data_to_send=b"*IDN?\\n",
                                number_of_bytes_to_receive=64)

        # SPI: full-duplex transfer
        resp = client.comm.spi("MySpiDevice",
                               action=BusActions.SEND_RECEIVE,
                               data_to_send=bytes([0xAA, 0xBB]),
                               number_of_bytes_to_receive=2)

        # Socket: send a SCPI query
        resp = client.comm.socket("MySocketDevice",
                                  action=BusActions.SEND_RECEIVE,
                                  host_name="192.168.1.10", port=5025,
                                  data_to_send=b"*IDN?\\n",
                                  number_of_bytes_to_receive=64)
    """

    def i2c(self, device_name, address, action, data_to_send=None,
            number_of_bytes_to_receive=0, max_retries=-1):
        """Perform an I2C bus transaction.

        Args:
            device_name: Device name as registered in the hardware manager.
            address: I2C 7-bit device address (0–127).
            action: :class:`~accordionq2.enums.BusActions` value (or string).
            data_to_send: Bytes to transmit. Required for ``Send``/``SendReceive``.
            number_of_bytes_to_receive: Expected receive count for ``Receive``/``SendReceive``.
            max_retries: Retry limit on NAK. ``-1`` uses the device default.

        Returns:
            :class:`~accordionq2.models.BusTransactionResponse`
        """
        body = {
            "DeviceName": device_name,
            "Address": format(address, "02X"),
            "Action": _action_value(action),
            "NumberOfBytesToReceive": number_of_bytes_to_receive,
            "MaxRetries": max_retries,
        }
        encoded = _to_hex(data_to_send)
        if encoded is not None:
            body["DataToSend"] = encoded
        return BusTransactionResponse.from_dict(self._post_json("api/comm/i2c", body))

    def uart(self, device_name, action, data_to_send=None,
             number_of_bytes_to_receive=0, timeout_ms=1000):
        """Perform a UART bus transaction.

        Args:
            device_name: Device name as registered in the hardware manager.
            action: :class:`~accordionq2.enums.BusActions` value (or string).
            data_to_send: Bytes to transmit. Required for ``Send``/``SendReceive``.
            number_of_bytes_to_receive: Expected receive count for ``Receive``/``SendReceive``.
            timeout_ms: Receive timeout in milliseconds.

        Returns:
            :class:`~accordionq2.models.BusTransactionResponse`
        """
        body = {
            "DeviceName": device_name,
            "Action": _action_value(action),
            "NumberOfBytesToReceive": number_of_bytes_to_receive,
            "TimeoutMs": timeout_ms,
        }
        encoded = _to_hex(data_to_send)
        if encoded is not None:
            body["DataToSend"] = encoded
        return BusTransactionResponse.from_dict(self._post_json("api/comm/uart", body))

    def spi(self, device_name, action, data_to_send=None,
            number_of_bytes_to_receive=0):
        """Perform a SPI bus transaction.

        Args:
            device_name: Device name as registered in the hardware manager.
            action: :class:`~accordionq2.enums.BusActions` value (or string).
            data_to_send: Bytes to clock out. Required for ``Send``/``SendReceive``.
            number_of_bytes_to_receive: Expected receive count for ``Receive``/``SendReceive``.

        Returns:
            :class:`~accordionq2.models.BusTransactionResponse`
        """
        body = {
            "DeviceName": device_name,
            "Action": _action_value(action),
            "NumberOfBytesToReceive": number_of_bytes_to_receive,
        }
        encoded = _to_hex(data_to_send)
        if encoded is not None:
            body["DataToSend"] = encoded
        return BusTransactionResponse.from_dict(self._post_json("api/comm/spi", body))

    def socket(self, device_name, action, host_name="", port=0,
               data_to_send=None, number_of_bytes_to_receive=0,
               termination_byte=0, use_termination_byte=False, timeout_ms=1000):
        """Perform a Socket (TCP/IP) bus transaction.

        Args:
            device_name: Device name as registered in the hardware manager.
            action: :class:`~accordionq2.enums.BusActions` value (or string).
            host_name: Remote host name or IP address.
            port: Remote TCP port number.
            data_to_send: Bytes to send. Required for ``Send``/``SendReceive``.
            number_of_bytes_to_receive: Expected receive count for ``Receive``/``SendReceive``.
            termination_byte: Byte value used as a message boundary (0–255).
            use_termination_byte: Whether to treat ``termination_byte`` as an end-of-message marker.
            timeout_ms: Receive timeout in milliseconds.

        Returns:
            :class:`~accordionq2.models.BusTransactionResponse`
        """
        body = {
            "DeviceName": device_name,
            "Action": _action_value(action),
            "HostName": host_name,
            "Port": port,
            "NumberOfBytesToReceive": number_of_bytes_to_receive,
            "TerminationByte": format(termination_byte, "02X"),
            "UseTerminationByte": use_termination_byte,
            "TimeoutMs": timeout_ms,
        }
        encoded = _to_hex(data_to_send)
        if encoded is not None:
            body["DataToSend"] = encoded
        return BusTransactionResponse.from_dict(self._post_json("api/comm/socket", body))

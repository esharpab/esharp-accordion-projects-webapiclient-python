"""Raw bus transaction operations (I2C, UART, SPI, Socket)."""

from __future__ import annotations

from typing import Any

from ._base import ApiGroupBase
from .enums import BusActions, FlowControlTypes, ParityTypes, UartBusTypes
from .models import BusTransactionResponse


def _to_hex(data: bytes | None) -> str | None:
    """Encode a bytes-like object as an uppercase hex string for JSON transport."""
    if data is None:
        return None
    return bytes(data).hex().upper()


def _action_value(action: BusActions | str) -> str:
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
                                port_name="/dev/ttyS0",
                                baud_rate=115200,
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

    def i2c(
        self,
        device_name: str,
        address: int,
        action: BusActions | str,
        data_to_send: bytes | None = None,
        number_of_bytes_to_receive: int = 0,
        max_retries: int = -1,
    ) -> BusTransactionResponse:
        """Perform an I2C bus transaction.

        Args:
            device_name: Device name as registered in the hardware manager.
            address: I2C 7-bit device address (0-127).
            action: :class:`~accordionq2.enums.BusActions` value (or string).
            data_to_send: Bytes to transmit. Required for ``Send``/``SendReceive``.
            number_of_bytes_to_receive: Expected receive count for ``Receive``/``SendReceive``.
            max_retries: Retry limit on NAK. ``-1`` uses the device default.

        Returns:
            :class:`~accordionq2.models.BusTransactionResponse`
        """
        body: dict[str, Any] = {
            "DeviceName": device_name,
            "Address": format(address, "02X"),
            "Action": _action_value(action),
            "NumberOfBytesToReceive": number_of_bytes_to_receive,
            "MaxRetries": max_retries,
        }
        encoded = _to_hex(data_to_send)
        if encoded is not None:
            body["DataToSend"] = encoded
        result = self._post_json("api/comm/i2c", body)
        assert isinstance(result, dict)
        return BusTransactionResponse.from_dict(result)

    def uart(
        self,
        device_name: str,
        action: BusActions | str,
        port_name: str = "",
        baud_rate: int = 9600,
        bus_type: UartBusTypes | str = UartBusTypes.RS232,
        flow_control: FlowControlTypes | str = FlowControlTypes.NONE,
        parity: ParityTypes | str = ParityTypes.NONE,
        use_termination_byte: bool = False,
        termination_byte: int = 0x0A,
        data_to_send: bytes | None = None,
        number_of_bytes_to_receive: int = 0,
        timeout_ms: int = 1000,
    ) -> BusTransactionResponse:
        """Perform a UART bus transaction.

        Args:
            device_name: Device name as registered in the hardware manager.
            action: :class:`~accordionq2.enums.BusActions` value (or string).
            port_name: Serial port identifier (e.g. ``"/dev/ttyS0"`` or ``"COM3"``).
            baud_rate: Baud rate (e.g. ``9600``, ``115200``).
            bus_type: Electrical standard (:class:`~accordionq2.enums.UartBusTypes`).
            flow_control: Flow control mode (:class:`~accordionq2.enums.FlowControlTypes`).
            parity: Parity setting (:class:`~accordionq2.enums.ParityTypes`).
            use_termination_byte: Whether to use ``termination_byte`` as a receive boundary.
            termination_byte: Termination byte value (0-255). Only used when ``use_termination_byte`` is ``True``.
            data_to_send: Bytes to transmit. Required for ``Send``/``SendReceive``.
            number_of_bytes_to_receive: Expected receive count for ``Receive``/``SendReceive``.
            timeout_ms: Receive timeout in milliseconds.

        Returns:
            :class:`~accordionq2.models.BusTransactionResponse`
        """
        body: dict[str, Any] = {
            "DeviceName": device_name,
            "Action": _action_value(action),
            "PortName": port_name,
            "BaudRate": baud_rate,
            "BusType": bus_type.value if isinstance(bus_type, UartBusTypes) else str(bus_type),
            "FlowControl": flow_control.value if isinstance(flow_control, FlowControlTypes) else str(flow_control),
            "Parity": parity.value if isinstance(parity, ParityTypes) else str(parity),
            "UseTerminationByte": use_termination_byte,
            "TerminationByte": format(termination_byte, "02X"),
            "NumberOfBytesToReceive": number_of_bytes_to_receive,
            "TimeoutMs": timeout_ms,
        }
        encoded = _to_hex(data_to_send)
        if encoded is not None:
            body["DataToSend"] = encoded
        result = self._post_json("api/comm/uart", body)
        assert isinstance(result, dict)
        return BusTransactionResponse.from_dict(result)

    def spi(
        self,
        device_name: str,
        action: BusActions | str,
        data_to_send: bytes | None = None,
        number_of_bytes_to_receive: int = 0,
    ) -> BusTransactionResponse:
        """Perform a SPI bus transaction.

        Args:
            device_name: Device name as registered in the hardware manager.
            action: :class:`~accordionq2.enums.BusActions` value (or string).
            data_to_send: Bytes to clock out. Required for ``Send``/``SendReceive``.
            number_of_bytes_to_receive: Expected receive count for ``Receive``/``SendReceive``.

        Returns:
            :class:`~accordionq2.models.BusTransactionResponse`
        """
        body: dict[str, Any] = {
            "DeviceName": device_name,
            "Action": _action_value(action),
            "NumberOfBytesToReceive": number_of_bytes_to_receive,
        }
        encoded = _to_hex(data_to_send)
        if encoded is not None:
            body["DataToSend"] = encoded
        result = self._post_json("api/comm/spi", body)
        assert isinstance(result, dict)
        return BusTransactionResponse.from_dict(result)

    def socket(
        self,
        device_name: str,
        action: BusActions | str,
        host_name: str = "",
        port: int = 0,
        data_to_send: bytes | None = None,
        number_of_bytes_to_receive: int = 0,
        termination_byte: int = 0,
        use_termination_byte: bool = False,
        timeout_ms: int = 1000,
    ) -> BusTransactionResponse:
        """Perform a Socket (TCP/IP) bus transaction.

        Args:
            device_name: Device name as registered in the hardware manager.
            action: :class:`~accordionq2.enums.BusActions` value (or string).
            host_name: Remote host name or IP address.
            port: Remote TCP port number.
            data_to_send: Bytes to send. Required for ``Send``/``SendReceive``.
            number_of_bytes_to_receive: Expected receive count for ``Receive``/``SendReceive``.
            termination_byte: Byte value used as a message boundary (0-255).
            use_termination_byte: Whether to treat ``termination_byte`` as an end-of-message marker.
            timeout_ms: Receive timeout in milliseconds.

        Returns:
            :class:`~accordionq2.models.BusTransactionResponse`
        """
        body: dict[str, Any] = {
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
        result = self._post_json("api/comm/socket", body)
        assert isinstance(result, dict)
        return BusTransactionResponse.from_dict(result)

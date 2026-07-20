"""Unit tests for the API group classes (mocked HTTP layer)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from accordionq2._base import HttpSession
from accordionq2.channels import ChannelsGroup
from accordionq2.comm import CommGroup
from accordionq2.enums import BusActions, FlowControlTypes, ParityTypes, UartBusTypes
from accordionq2.exceptions import AccordionQ2ApiError, AccordionQ2ShortReadError
from accordionq2.models import BusTransactionResponse, ChannelConfigRequest, ChannelDto
from accordionq2.resources import ResourcesGroup


def _session(*responses: tuple[int, object]) -> HttpSession:
    """Build a mock HttpSession that returns *responses* in order."""
    session = MagicMock(spec=HttpSession)
    encoded = [
        (status, json.dumps(body).encode() if not isinstance(body, bytes) else body)
        for status, body in responses
    ]
    session.request.side_effect = encoded
    return session


# ---------------------------------------------------------------------------
# ChannelsGroup
# ---------------------------------------------------------------------------

_CHANNEL_DATA = {
    "channelIndex": 0,
    "index": 0,
    "enabled": True,
    "usage": "UserAllocatable",
    "deviceName": "Dev",
    "channelType": "Analog",
    "channelTypeCapability": "Analog",
    "alias": "CH0",
    "netName": "NET0",
    "groupName": "",
    "capability": 3,
    "description": "",
    "direction": 1,
    "directionChanged": False,
    "defaultDirection": 1,
    "unit": "V",
    "isVirtual": False,
}


class TestChannelsGroup:
    def test_get_all_parses_list(self):
        session = _session((200, [_CHANNEL_DATA]))
        grp = ChannelsGroup(session)
        channels = grp.get_all()
        assert len(channels) == 1
        assert channels[0].alias == "CH0"
        assert isinstance(channels[0], ChannelDto)

    def test_get_channel_by_alias_uses_lookup_request(self):
        session = _session((200, _CHANNEL_DATA))
        grp = ChannelsGroup(session)
        ch = grp.get_channel(alias="CH0")
        assert ch.alias == "CH0"
        # Verify the body sent to the server
        body_sent = json.loads(
            session.request.call_args[1].get("body") or session.request.call_args[0][2]
        )
        assert body_sent["Alias"] == "CH0"
        assert "NetName" not in body_sent

    def test_get_channel_by_net_name(self):
        session = _session((200, _CHANNEL_DATA))
        grp = ChannelsGroup(session)
        grp.get_channel(net_name="NET0")
        body_sent = json.loads(
            session.request.call_args[1].get("body") or session.request.call_args[0][2]
        )
        assert body_sent["NetName"] == "NET0"
        assert "Alias" not in body_sent

    def test_configure_sends_partial_update(self):
        session = _session((200, b""))
        grp = ChannelsGroup(session)
        cfg = ChannelConfigRequest(alias="CH0", enabled=False)
        grp.configure(cfg)
        body_sent = json.loads(
            session.request.call_args[1].get("body") or session.request.call_args[0][2]
        )
        assert body_sent["Alias"] == "CH0"
        assert body_sent["Enabled"] is False
        assert "Direction" not in body_sent

    def test_configure_many_sends_list(self):
        session = _session((200, b""))
        grp = ChannelsGroup(session)
        cfgs = [
            ChannelConfigRequest(alias="CH0", unit="V"),
            ChannelConfigRequest(alias="CH1", unit="A"),
        ]
        grp.configure_many(cfgs)
        body_sent = json.loads(
            session.request.call_args[1].get("body") or session.request.call_args[0][2]
        )
        assert isinstance(body_sent, list)
        assert len(body_sent) == 2
        assert body_sent[0]["Unit"] == "V"


# ---------------------------------------------------------------------------
# ResourcesGroup
# ---------------------------------------------------------------------------


class TestResourcesGroup:
    def test_get_value_lowercase_key(self):
        session = _session((200, {"value": "3.3"}))
        grp = ResourcesGroup(session)
        assert grp.get_value("VDD") == "3.3"

    def test_get_value_uppercase_key(self):
        session = _session((200, {"Value": "5.0"}))
        grp = ResourcesGroup(session)
        assert grp.get_value("VDD") == "5.0"

    def test_get_value_missing_key_raises(self):
        session = _session((200, {"something_else": "x"}))
        grp = ResourcesGroup(session)
        with pytest.raises(AccordionQ2ApiError):
            grp.get_value("VDD")

    def test_transact_returns_value(self):
        session = _session((200, {"value": "ACK"}))
        grp = ResourcesGroup(session)
        assert grp.transact("EEPROM", "READ") == "ACK"

    def test_get_names_returns_list(self):
        session = _session((200, ["VDD", "GND", "CPU_TEMP"]))
        grp = ResourcesGroup(session)
        names = grp.get_names()
        assert names == ["VDD", "GND", "CPU_TEMP"]

    def test_set_value_sends_correct_body(self):
        session = _session((200, b""))
        grp = ResourcesGroup(session)
        grp.set_value("VDD", "3.3")
        body_sent = json.loads(
            session.request.call_args[1].get("body") or session.request.call_args[0][2]
        )
        assert body_sent["Name"] == "VDD"
        assert body_sent["Value"] == "3.3"

    def test_get_values_returns_dict(self):
        session = _session((200, {"resources": {"VDD": "3.3", "GND": "0"}}))
        grp = ResourcesGroup(session)
        result = grp.get_values(["VDD", "GND"])
        assert result == {"VDD": "3.3", "GND": "0"}


# ---------------------------------------------------------------------------
# CommGroup - UART
# ---------------------------------------------------------------------------

_UART_RESPONSE = {
    "deviceName": "MyUart",
    "action": "SendReceive",
    "received": "41424344",
    "numberOfBytesReceived": 4,
}


class TestCommGroupUart:
    def test_returns_bus_transaction_response(self):
        session = _session((200, _UART_RESPONSE))
        grp = CommGroup(session)
        resp = grp.uart(
            "MyUart", BusActions.SEND_RECEIVE, data_to_send=b"\x2a", number_of_bytes_to_receive=4
        )
        assert isinstance(resp, BusTransactionResponse)
        assert resp.received == b"ABCD"
        assert resp.number_of_bytes_received == 4

    def test_default_fields_sent(self):
        session = _session((200, _UART_RESPONSE))
        grp = CommGroup(session)
        grp.uart("MyUart", BusActions.SEND, data_to_send=b"\xff")
        body = json.loads(
            session.request.call_args[1].get("body") or session.request.call_args[0][2]
        )
        assert body["BaudRate"] == 9600
        assert body["BusType"] == "RS232"
        assert body["FlowControl"] == "None"
        assert body["Parity"] == "None"
        assert body["UseTerminationByte"] is False
        assert body["TerminationByte"] == "0A"

    def test_custom_baud_and_parity(self):
        session = _session((200, _UART_RESPONSE))
        grp = CommGroup(session)
        grp.uart(
            "MyUart",
            BusActions.SEND,
            baud_rate=115200,
            parity=ParityTypes.ODD,
            flow_control=FlowControlTypes.RTS_CTS,
            bus_type=UartBusTypes.RS485,
            data_to_send=b"\x01",
        )
        body = json.loads(
            session.request.call_args[1].get("body") or session.request.call_args[0][2]
        )
        assert body["BaudRate"] == 115200
        assert body["Parity"] == "Odd"
        assert body["FlowControl"] == "RTS_CTS"
        assert body["BusType"] == "RS485"

    def test_data_to_send_hex_encoded(self):
        session = _session((200, _UART_RESPONSE))
        grp = CommGroup(session)
        grp.uart("MyUart", BusActions.SEND, data_to_send=bytes([0xDE, 0xAD, 0xBE, 0xEF]))
        body = json.loads(
            session.request.call_args[1].get("body") or session.request.call_args[0][2]
        )
        assert body["DataToSend"] == "DEADBEEF"

    def test_no_data_omits_field(self):
        session = _session((200, _UART_RESPONSE))
        grp = CommGroup(session)
        grp.uart("MyUart", BusActions.RECEIVE, number_of_bytes_to_receive=8)
        body = json.loads(
            session.request.call_args[1].get("body") or session.request.call_args[0][2]
        )
        assert "DataToSend" not in body

    def test_uart_short_read_is_tolerated(self):
        # UART is timeout-bounded: a short read is normal and must NOT raise.
        session = _session((200, _UART_RESPONSE))  # returns 4 bytes
        grp = CommGroup(session)
        resp = grp.uart("MyUart", BusActions.RECEIVE, number_of_bytes_to_receive=8)
        assert resp.number_of_bytes_received == 4


# ---------------------------------------------------------------------------
# CommGroup - short-read guard (I2C/SPI)
# ---------------------------------------------------------------------------


def _i2c_response(received_hex: str, count: int) -> dict:
    return {
        "deviceName": "dev",
        "action": "Receive",
        "received": received_hex,
        "numberOfBytesReceived": count,
    }


class TestCommGroupShortRead:
    def test_i2c_receive_short_read_raises(self):
        # Requested 1 byte, agent reports success with 0 -> loud failure.
        session = _session((200, _i2c_response("", 0)))
        grp = CommGroup(session)
        with pytest.raises(AccordionQ2ShortReadError) as ei:
            grp.i2c("dev", address=0x50, action=BusActions.RECEIVE, number_of_bytes_to_receive=1)
        assert ei.value.requested_bytes == 1
        assert ei.value.received_bytes == 0

    def test_i2c_send_receive_short_read_raises(self):
        session = _session((200, _i2c_response("4142", 2)))
        grp = CommGroup(session)
        with pytest.raises(AccordionQ2ShortReadError):
            grp.i2c(
                "dev",
                address=0x50,
                action=BusActions.SEND_RECEIVE,
                data_to_send=b"\x00",
                number_of_bytes_to_receive=4,
            )

    def test_i2c_full_read_ok(self):
        session = _session((200, _i2c_response("41424344", 4)))
        grp = CommGroup(session)
        resp = grp.i2c("dev", address=0x50, action=BusActions.RECEIVE, number_of_bytes_to_receive=4)
        assert resp.received == b"ABCD"

    def test_i2c_scan_not_treated_as_short_read(self):
        # Scan carries no requested length; its returned bytes are the address list.
        session = _session(
            (
                200,
                {
                    "deviceName": "dev",
                    "action": "Scan",
                    "received": "20505770",
                    "numberOfBytesReceived": 4,
                },
            )
        )
        grp = CommGroup(session)
        resp = grp.i2c("dev", address=0x00, action=BusActions.SCAN)
        assert resp.number_of_bytes_received == 4

    def test_spi_receive_short_read_raises(self):
        session = _session(
            (
                200,
                {
                    "deviceName": "dev",
                    "action": "Receive",
                    "received": "",
                    "numberOfBytesReceived": 0,
                },
            )
        )
        grp = CommGroup(session)
        with pytest.raises(AccordionQ2ShortReadError):
            grp.spi("dev", action=BusActions.RECEIVE, number_of_bytes_to_receive=2)

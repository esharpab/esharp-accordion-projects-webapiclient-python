"""Unit tests for the API group classes (mocked HTTP layer)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from accordionq2._base import HttpSession
from accordionq2.channels import ChannelsGroup
from accordionq2.exceptions import AccordionQ2ApiError
from accordionq2.models import ChannelConfigRequest, ChannelDto
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
    "channelIndex": 0, "index": 0, "enabled": True,
    "usage": "UserAllocatable", "deviceName": "Dev",
    "channelType": "Analog", "channelTypeCapability": "Analog",
    "alias": "CH0", "netName": "NET0", "groupName": "",
    "capability": 3, "description": "", "direction": 1,
    "directionChanged": False, "defaultDirection": 1,
    "unit": "V", "isVirtual": False,
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
        body_sent = json.loads(session.request.call_args[1].get("body") or
                               session.request.call_args[0][2])
        assert body_sent["Alias"] == "CH0"
        assert "NetName" not in body_sent

    def test_get_channel_by_net_name(self):
        session = _session((200, _CHANNEL_DATA))
        grp = ChannelsGroup(session)
        grp.get_channel(net_name="NET0")
        body_sent = json.loads(session.request.call_args[1].get("body") or
                               session.request.call_args[0][2])
        assert body_sent["NetName"] == "NET0"
        assert "Alias" not in body_sent

    def test_configure_sends_partial_update(self):
        session = _session((200, b""))
        grp = ChannelsGroup(session)
        cfg = ChannelConfigRequest(alias="CH0", enabled=False)
        grp.configure(cfg)
        body_sent = json.loads(session.request.call_args[1].get("body") or
                               session.request.call_args[0][2])
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
        body_sent = json.loads(session.request.call_args[1].get("body") or
                               session.request.call_args[0][2])
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
        body_sent = json.loads(session.request.call_args[1].get("body") or
                               session.request.call_args[0][2])
        assert body_sent["Name"] == "VDD"
        assert body_sent["Value"] == "3.3"

    def test_get_values_returns_dict(self):
        session = _session((200, {"resources": {"VDD": "3.3", "GND": "0"}}))
        grp = ResourcesGroup(session)
        result = grp.get_values(["VDD", "GND"])
        assert result == {"VDD": "3.3", "GND": "0"}

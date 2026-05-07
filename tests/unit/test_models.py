"""Unit tests for data model serialisation and deserialisation."""

from __future__ import annotations

from typing import ClassVar

import pytest

from accordionq2.enums import (
    AppTypes,
    ChannelTypes,
    DirectionTypes,
    MpioUsageTypes,
    direction_to_json,
    parse_channel_types,
    parse_direction_types,
)
from accordionq2.models import (
    AppLicenseDto,
    BusTransactionResponse,
    ChannelConfigRequest,
    ChannelDto,
    ChannelLookupRequest,
    ConnectionStatusDto,
    ModuleSettingsDto,
    NumericMeasureResultDto,
    NumericResultChannelDto,
    PhysicalSystemDto,
)

# ---------------------------------------------------------------------------
# Enum helpers
# ---------------------------------------------------------------------------

class TestParseDirectionTypes:
    def test_integer_in(self):
        assert parse_direction_types(1) == DirectionTypes.IN

    def test_integer_out(self):
        assert parse_direction_types(2) == DirectionTypes.OUT

    def test_integer_undefined(self):
        assert parse_direction_types(0) == DirectionTypes.UNDEFINED

    def test_string_in(self):
        assert parse_direction_types("IN") == DirectionTypes.IN

    def test_string_out(self):
        assert parse_direction_types("OUT") == DirectionTypes.OUT

    def test_string_combined(self):
        result = parse_direction_types("IN, OUT")
        assert DirectionTypes.IN in result
        assert DirectionTypes.OUT in result

    def test_unknown_string_returns_undefined(self):
        assert parse_direction_types("BOGUS") == DirectionTypes.UNDEFINED


class TestParseChannelTypes:
    def test_integer(self):
        assert parse_channel_types(1) == ChannelTypes.ANALOG

    def test_string_analog(self):
        assert parse_channel_types("Analog") == ChannelTypes.ANALOG

    def test_string_i2c(self):
        assert parse_channel_types("I2C") == ChannelTypes.I2C

    def test_string_uart(self):
        assert parse_channel_types("UART") == ChannelTypes.UART

    def test_string_combined(self):
        result = parse_channel_types("Analog, Digital")
        assert ChannelTypes.ANALOG in result
        assert ChannelTypes.DIGITAL in result

    def test_unknown_string_returns_undefined(self):
        assert parse_channel_types("BOGUS") == ChannelTypes.UNDEFINED


class TestDirectionToJson:
    def test_in(self):
        assert direction_to_json(DirectionTypes.IN) == "IN"

    def test_out(self):
        assert direction_to_json(DirectionTypes.OUT) == "OUT"

    def test_undefined(self):
        assert direction_to_json(DirectionTypes.UNDEFINED) == "Undefined"

    def test_combined(self):
        result = direction_to_json(DirectionTypes.IN | DirectionTypes.OUT)
        assert "IN" in result
        assert "OUT" in result


# ---------------------------------------------------------------------------
# ConnectionStatusDto
# ---------------------------------------------------------------------------

class TestConnectionStatusDto:
    def test_from_dict_connected(self):
        dto = ConnectionStatusDto.from_dict({"isConnected": True, "lastError": None})
        assert dto.is_connected is True
        assert dto.last_error is None

    def test_from_dict_disconnected_with_error(self):
        dto = ConnectionStatusDto.from_dict({"isConnected": False, "lastError": "Timeout"})
        assert dto.is_connected is False
        assert dto.last_error == "Timeout"

    def test_from_dict_defaults(self):
        dto = ConnectionStatusDto.from_dict({})
        assert dto.is_connected is False
        assert dto.last_error is None

    def test_frozen(self):
        dto = ConnectionStatusDto.from_dict({})
        with pytest.raises(AttributeError):
            dto.is_connected = True  # type: ignore[misc]

    def test_instances_independent(self):
        a = ConnectionStatusDto.from_dict({"isConnected": True})
        b = ConnectionStatusDto.from_dict({"isConnected": False})
        assert a.is_connected is True
        assert b.is_connected is False


# ---------------------------------------------------------------------------
# AppLicenseDto
# ---------------------------------------------------------------------------

class TestAppLicenseDto:
    def test_from_dict(self):
        dto = AppLicenseDto.from_dict({
            "name": "MyApp", "key": "K1", "expires": "2030-01-01",
            "type": "SoftwareModule",
        })
        assert dto.name == "MyApp"
        assert dto.type == AppTypes.SOFTWARE_MODULE

    def test_unknown_type_falls_back(self):
        dto = AppLicenseDto.from_dict({"type": "FutureType"})
        assert dto.type == AppTypes.UNKNOWN

    def test_defaults(self):
        dto = AppLicenseDto.from_dict({})
        assert dto.name == ""
        assert dto.key == ""


# ---------------------------------------------------------------------------
# ModuleSettingsDto
# ---------------------------------------------------------------------------

class TestModuleSettingsDto:
    def test_round_trip(self):
        data = {
            "name": "Mod1", "enabled": True, "className": "Cls",
            "assemblyPath": "path.dll", "namespace": "NS",
            "imageName": "img.png", "initialData": {"k": "v"},
        }
        dto = ModuleSettingsDto.from_dict(data)
        d = dto.to_dict()
        assert d["Name"] == "Mod1"
        assert d["Enabled"] is True
        assert d["InitialData"] == {"k": "v"}

    def test_initial_data_defaults_to_empty_dict(self):
        dto = ModuleSettingsDto.from_dict({})
        assert dto.initial_data == {}

    def test_instances_have_independent_initial_data(self):
        a = ModuleSettingsDto.from_dict({})
        b = ModuleSettingsDto.from_dict({})
        # frozen=True means we can't mutate, but initial_data dict itself is independent
        assert a.initial_data is not b.initial_data


# ---------------------------------------------------------------------------
# PhysicalModuleDto / PhysicalSystemDto
# ---------------------------------------------------------------------------

class TestPhysicalSystemDto:
    def test_from_dict_with_modules(self):
        data = {
            "host": "agent64",
            "ethIpV4": "192.168.1.1",
            "ethIpV6": "",
            "firmware": "1.0.0",
            "mac": "AA:BB:CC:DD:EE:FF",
            "modules": [
                {"index": 0, "name": "Base", "productID": "ESH001",
                 "revision": 1, "serialNumber": "SN123"},
            ],
            "networkInterfaces": {},
        }
        dto = PhysicalSystemDto.from_dict(data)
        assert dto.host == "agent64"
        assert len(dto.modules) == 1
        assert dto.modules[0].product_id == "ESH001"

    def test_modules_is_tuple(self):
        dto = PhysicalSystemDto.from_dict({"modules": []})
        assert isinstance(dto.modules, tuple)

    def test_empty_modules_default(self):
        dto = PhysicalSystemDto.from_dict({})
        assert dto.modules == ()


# ---------------------------------------------------------------------------
# ChannelDto
# ---------------------------------------------------------------------------

class TestChannelDto:
    _FULL: ClassVar[dict] = {
        "channelIndex": 3, "index": 3, "enabled": True,
        "usage": "UserAllocatable", "deviceName": "Dev1",
        "channelType": "Analog", "channelTypeCapability": "Analog",
        "alias": "MY_CH", "netName": "NET1", "groupName": "GRP",
        "capability": 3, "description": "Test", "direction": 1,
        "directionChanged": False, "defaultDirection": 1,
        "unit": "V", "isVirtual": False,
    }

    def test_from_dict_full(self):
        dto = ChannelDto.from_dict(self._FULL)
        assert dto.alias == "MY_CH"
        assert dto.enabled is True
        assert dto.usage == MpioUsageTypes.USER_ALLOCATABLE
        assert dto.channel_type == ChannelTypes.ANALOG
        assert dto.direction == DirectionTypes.IN

    def test_defaults(self):
        dto = ChannelDto.from_dict({})
        assert dto.channel_index == 0
        assert dto.alias == ""
        assert dto.usage == MpioUsageTypes.UNDEFINED

    def test_frozen(self):
        dto = ChannelDto.from_dict({})
        with pytest.raises(AttributeError):
            dto.alias = "mutated"  # type: ignore[misc]

    def test_unknown_usage_falls_back(self):
        dto = ChannelDto.from_dict({"usage": "FutureUsage"})
        assert dto.usage == MpioUsageTypes.UNDEFINED

    def test_repr_contains_alias(self):
        dto = ChannelDto.from_dict({"alias": "X1"})
        assert "X1" in repr(dto)

    def test_equality(self):
        a = ChannelDto.from_dict(self._FULL)
        b = ChannelDto.from_dict(self._FULL)
        assert a == b

    def test_instances_independent(self):
        a = ChannelDto.from_dict({"alias": "A"})
        b = ChannelDto.from_dict({"alias": "B"})
        assert a.alias != b.alias


# ---------------------------------------------------------------------------
# ChannelLookupRequest / ChannelConfigRequest
# ---------------------------------------------------------------------------

class TestChannelLookupRequest:
    def test_alias_only(self):
        r = ChannelLookupRequest(alias="MY_CH")
        assert r.to_dict() == {"Alias": "MY_CH"}

    def test_net_name_only(self):
        r = ChannelLookupRequest(net_name="NET1")
        assert r.to_dict() == {"NetName": "NET1"}

    def test_both(self):
        r = ChannelLookupRequest(alias="A", net_name="N")
        d = r.to_dict()
        assert d["Alias"] == "A"
        assert d["NetName"] == "N"

    def test_empty(self):
        assert ChannelLookupRequest().to_dict() == {}


class TestChannelConfigRequest:
    def test_only_set_fields_serialised(self):
        r = ChannelConfigRequest(alias="MY_CH", enabled=True)
        d = r.to_dict()
        assert d == {"Alias": "MY_CH", "Enabled": True}
        assert "Direction" not in d

    def test_direction_serialised(self):
        r = ChannelConfigRequest(direction=DirectionTypes.OUT)
        d = r.to_dict()
        assert d["Direction"] == "OUT"

    def test_all_none_produces_empty_dict(self):
        assert ChannelConfigRequest().to_dict() == {}

    def test_mutable(self):
        r = ChannelConfigRequest()
        r.alias = "changed"
        assert r.alias == "changed"


# ---------------------------------------------------------------------------
# BusTransactionResponse
# ---------------------------------------------------------------------------

class TestBusTransactionResponse:
    def test_hex_decoded(self):
        dto = BusTransactionResponse.from_dict({
            "deviceName": "Dev", "action": "Receive",
            "received": "DEADBEEF", "numberOfBytesReceived": 4,
        })
        assert dto.received == bytes([0xDE, 0xAD, 0xBE, 0xEF])
        assert dto.number_of_bytes_received == 4

    def test_empty_received(self):
        dto = BusTransactionResponse.from_dict({})
        assert dto.received == b""

    def test_invalid_hex_falls_back_to_empty(self):
        dto = BusTransactionResponse.from_dict({"received": "NOT_HEX"})
        assert dto.received == b""


# ---------------------------------------------------------------------------
# NumericResultChannelDto
# ---------------------------------------------------------------------------

class TestNumericResultChannelDto:
    def test_from_dict(self):
        dto = NumericResultChannelDto.from_dict({
            "netName": "NR1", "alias": "NR_A",
            "possibleTargetNames": ["T1", "T2"],
            "sampleRate": 1000, "defaultSamples": 500,
        })
        assert dto.net_name == "NR1"
        assert dto.possible_target_names == ("T1", "T2")
        assert dto.sample_rate == 1000

    def test_possible_target_names_is_tuple(self):
        dto = NumericResultChannelDto.from_dict({"possibleTargetNames": ["A"]})
        assert isinstance(dto.possible_target_names, tuple)


# ---------------------------------------------------------------------------
# NumericMeasureResultDto
# ---------------------------------------------------------------------------

class TestNumericMeasureResultDto:
    def test_from_dict(self):
        dto = NumericMeasureResultDto.from_dict({
            "channelNetName": "NR1", "targetNetName": "V1",
            "sampleCount": 1000, "sampleRate": 1000,
            "reducedSet": True, "started": "T0", "stopped": "T1", "duration": "1s",
        })
        assert dto.channel_net_name == "NR1"
        assert dto.sample_count == 1000
        assert dto.reduced_set is True

"""Unit tests for stable module names and JTAG ports (the firmware's Drummer/PORTS.md):
``modules.get_present()``, ``client.jtag_ports``, ``DrummerTarget.port()`` and ``bind_port()``, the
capabilities' ``names``. No network."""

from __future__ import annotations

import json

import pytest

from accordionq2 import AccordionQ2ApiError, ModulePresenceDto
from accordionq2.capabilities import CapabilitiesGroup
from accordionq2.drummer import DrummerGroup
from accordionq2.jtag_ports import JtagPortsGroup, JtagPortState, port_name
from accordionq2.modules import ModulesGroup

from .conftest import make_session

PORT_STATE = {
    "port": "MicroHAPS.JTAG.A",
    "owner": "MicroHAPS",
    "label": "FT4232H J020324 interface A",
    "seq": 42,
    "state": "held",
    "holder": {
        "kind": "borrower",
        "name": "Drummer",
        "what": None,
        "since": "2026-11-20T10:00:00.0000000Z",
    },
    "why": None,
    "bound": "Drummer",
    "max_tck_hz": 7500000,
    "xvc": {
        "enabled": True,
        "engine": "drummer",
        "listen": "0.0.0.0:2542",
        "allow": ["192.168.0.12"],
        "client": None,
        "waiting": False,
        "sessions": 3,
        "last_end": "the client closed the connection",
    },
    "since": "2026-11-20T10:00:00.0000000Z",
}


def _sent(session: object) -> list[tuple[str, str, object]]:
    calls = session.request.call_args_list  # type: ignore[attr-defined]
    return [
        (c.args[0], c.args[1], json.loads(c.kwargs["body"]) if c.kwargs.get("body") else None)
        for c in calls
    ]


class TestPresent:
    def test_lists_hardware_and_software_modules(self):
        session = make_session(
            [
                (
                    200,
                    [
                        {
                            "kind": "hardware",
                            "address": "0.2",
                            "prefix": "0.2.ESH10000560",
                            "name": "MPIO-96 SPI Module",
                            "productId": "ESH10000560",
                            "revision": 3,
                            "serialNumber": "A001234",
                            "className": None,
                        },
                        {
                            "kind": "software",
                            "address": "MicroHAPS",
                            "prefix": "MicroHAPS",
                            "name": "MicroHAPS",
                            "productId": None,
                            "revision": None,
                            "serialNumber": None,
                            "className": "MicroHapsHandler.MicroHaps",
                        },
                    ],
                )
            ]
        )
        present = ModulesGroup(session).get_present()

        assert _sent(session) == [("GET", "api/modules/present", None)]
        assert present[0] == ModulePresenceDto(
            "hardware",
            "0.2",
            "0.2.ESH10000560",
            "MPIO-96 SPI Module",
            "ESH10000560",
            3,
            "A001234",
            None,
        )
        assert present[0].is_hardware
        assert not present[1].is_hardware
        assert present[1].address == "MicroHAPS"
        assert present[1].revision is None
        assert present[1].class_name == "MicroHapsHandler.MicroHaps"

    def test_older_firmware_answers_404(self):
        session = make_session([(404, {"error": "not found"})])
        with pytest.raises(AccordionQ2ApiError) as error:
            ModulesGroup(session).get_present()
        assert error.value.status_code == 404


class TestJtagPorts:
    def test_get_all_finds_ports_by_the_unit_of_their_state_channels(self):
        session = make_session(
            [
                (
                    200,
                    [
                        {
                            "netName": "MicroHAPS.JTAG.A.State",
                            "unit": "jtag-port",
                            "channelType": "Register",
                        },
                        {
                            "netName": "MicroHAPS.JTAG.A.Xvc",
                            "unit": "jtag-port:xvc",
                            "channelType": "Digital",
                        },
                        {
                            "netName": "JTAG_FTDI.JTAG.A.State",
                            "unit": "jtag-port",
                            "channelType": "Register",
                        },
                        {"netName": "0.2.ESH10000560.CH1", "unit": "V", "channelType": "Analog"},
                    ],
                ),
                (
                    200,
                    {
                        "resources": {
                            "MicroHAPS.JTAG.A.State": json.dumps(PORT_STATE),
                            "JTAG_FTDI.JTAG.A.State": "not json",
                        }
                    },
                ),
            ]
        )
        ports = JtagPortsGroup(session).get_all()

        assert [p.name for p in ports] == ["JTAG_FTDI.JTAG.A", "MicroHAPS.JTAG.A"]
        _, path, body = _sent(session)[1]
        assert path == "api/resources/values/get"
        assert sorted(body["Names"]) == ["JTAG_FTDI.JTAG.A.State", "MicroHAPS.JTAG.A.State"]
        assert ports[0].state is None
        s = ports[1].state
        assert s is not None
        assert s.state == "held"
        assert s.seq == 42
        assert s.holder is not None and s.holder.kind == "borrower" and s.holder.name == "Drummer"
        assert s.bound == "Drummer"
        assert s.max_tck_hz == 7_500_000
        assert s.xvc.enabled and s.xvc.listen == "0.0.0.0:2542" and s.xvc.allow == ("192.168.0.12",)
        assert ports[1].xvc_channel == "MicroHAPS.JTAG.A.Xvc"

    def test_get_all_is_empty_without_ports(self):
        session = make_session([(200, [{"netName": "0.2.ESH10000560.CH1", "unit": "V"}])])
        assert JtagPortsGroup(session).get_all() == []
        assert len(_sent(session)) == 1

    def test_set_xvc_writes_the_ports_switch(self):
        session = make_session([(200, {}), (200, {})])
        g = JtagPortsGroup(session)
        g.set_xvc("MicroHAPS.JTAG.A", True)
        g.set_xvc("MicroHAPS.JTAG.A.State", False)
        assert _sent(session) == [
            ("POST", "api/resources/value/set", {"Name": "MicroHAPS.JTAG.A.Xvc", "Value": "True"}),
            ("POST", "api/resources/value/set", {"Name": "MicroHAPS.JTAG.A.Xvc", "Value": "False"}),
        ]

    def test_get_state_and_port_name(self):
        session = make_session([(200, {"value": json.dumps(PORT_STATE)})])
        s = JtagPortsGroup(session).get_state("MicroHAPS.JTAG.A.Xvc")
        assert _sent(session)[0][2] == {"Name": "MicroHAPS.JTAG.A.State"}
        assert s is not None and s.owner == "MicroHAPS"
        assert port_name("x.JTAG.A.state") == "x.JTAG.A"
        assert JtagPortState.parse("") is None
        assert JtagPortState.parse("[1]") is None
        with pytest.raises(ValueError):
            port_name("  ")


class TestDisturbed:
    def test_the_state_carries_the_ports_incarnation_and_disturbances(self):
        data = {
            **PORT_STATE,
            "incarnation": "9f2c4e1a7b3d5f60",
            "disturbed": {
                "count": 7,
                "why": "MicroHAPS's use: a POWER cycle",
                "since": "2026-11-08T15:02:00.0000000Z",
            },
        }
        s = JtagPortState.from_dict(data)
        assert s.incarnation == "9f2c4e1a7b3d5f60"
        assert s.disturbed is not None
        assert s.disturbed.count == 7
        assert s.disturbed.why == "MicroHAPS's use: a POWER cycle"
        assert s.disturbed.since == "2026-11-08T15:02:00.0000000Z"

    def test_older_firmware_has_none(self):
        s = JtagPortState.from_dict(PORT_STATE)
        assert s.incarnation == ""
        assert s.disturbed is None


class TestDrummerPort:
    def test_port_and_bind_port_use_target_port(self):
        session = make_session([(200, {"value": " MicroHAPS.JTAG.A "}), (200, {}), (200, {})])
        t = DrummerGroup(session).target("Drummer")
        assert t.port() == "MicroHAPS.JTAG.A"
        t.bind_port("JTAG_FTDI.JTAG.A")
        t.bind_port(None)
        assert _sent(session) == [
            ("POST", "api/resources/value/get", {"Name": "Drummer.Target.Port"}),
            (
                "POST",
                "api/resources/value/set",
                {"Name": "Drummer.Target.Port", "Value": "JTAG_FTDI.JTAG.A"},
            ),
            ("POST", "api/resources/value/set", {"Name": "Drummer.Target.Port", "Value": ""}),
        ]


class TestNamesCapability:
    def test_stable_names_and_the_old_names_map(self):
        session = make_session(
            [
                (
                    200,
                    {
                        "apiVersion": 1,
                        "features": [],
                        "names": {
                            "stable": True,
                            "oldNamesAccepted": True,
                            "legacy": {
                                "prefixes": {
                                    "MicroHAPS_PMBUS_LTPP": "MicroHAPS.MicroHAPS_PMBUS_LTPP"
                                },
                                "positions": {"5": "ModuleForwarder", "x": "junk"},
                            },
                        },
                    },
                ),
                (200, {"apiVersion": 1, "features": []}),
            ]
        )
        caps = CapabilitiesGroup(session).get()
        assert caps.names is not None
        assert caps.names.stable and caps.names.old_names_accepted
        assert caps.names.legacy_prefixes == {
            "MicroHAPS_PMBUS_LTPP": "MicroHAPS.MicroHAPS_PMBUS_LTPP"
        }
        assert caps.names.legacy_positions == {5: "ModuleForwarder"}
        assert CapabilitiesGroup(session).get().names is None

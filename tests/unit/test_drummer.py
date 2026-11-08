"""Unit tests for ``client.drummer`` (Drummer/CONTROL.md section 11): operations as transactions on
Call channels, the capability check, job following, the SIB_ prefix, 409. No network."""

from __future__ import annotations

import json

import pytest

from accordionq2 import AccordionQ2ApiError, AccordionQ2NotSupportedError
from accordionq2.capabilities import CapabilitiesDto
from accordionq2.drummer import DrummerGroup, DrummerModuleRef, DrummerTarget, segment

from .conftest import make_session

WITH_FEATURE = {"apiVersion": 1, "features": ["events", "resources.transact"]}
WITHOUT_FEATURE = {"apiVersion": 1, "features": ["events"]}


def _sent(session: object) -> list[tuple[str, str, object]]:
    """(method, path, JSON body or None) of each request made."""
    calls = session.request.call_args_list  # type: ignore[attr-defined]
    return [
        (c.args[0], c.args[1], json.loads(c.kwargs["body"]) if c.kwargs.get("body") else None)
        for c in calls
    ]


def _value(answer: object) -> dict[str, str]:
    """What ``api/resources/transact`` and ``value/get`` answer: ``{"value": "<text>"}``."""
    return {"value": answer if isinstance(answer, str) else json.dumps(answer)}


def _transactions(session: object) -> list[tuple[str, dict]]:
    """(channel, request JSON) of each transaction."""
    return [
        (body["Name"], json.loads(body["Value"]))
        for _, path, body in _sent(session)
        if path == "api/resources/transact"
    ]


class TestCall:
    def test_sends_the_operation_on_the_segments_call_channel(self):
        session = make_session(
            [
                (200, WITH_FEATURE),
                (200, _value({"count": 600123, "hz": 6001230.0, "ms": 101.3, "seq": 12})),
            ]
        )
        t = DrummerGroup(session).target("Drummer")
        r = t.call("SIB_CLK", "clock_measure", gate=1_200_000, channel=2)

        assert r == {"count": 600123, "hz": 6001230.0, "ms": 101.3, "seq": 12}
        assert _sent(session)[0] == ("GET", "api/capabilities", None)
        assert _transactions(session) == [
            (
                "Drummer.CLK.Call",
                {"call": "clock_measure", "gate": 1_200_000, "channel": 2, "wait_ms": 10_000},
            )
        ]

    def test_arguments_named_op_name_or_instrument_pass_through(self):
        session = make_session([(200, WITH_FEATURE), (200, _value({"ms": 1.0})), (200, _value({}))])
        t = DrummerGroup(session).target("Drummer")
        t.call("MEM", "mem_start", {"pattern": "PRBS31"}, op="write_read", name="x", instrument="y")
        t.module_call("la_group_read")

        assert _transactions(session) == [
            (
                "Drummer.MEM.Call",
                {
                    "call": "mem_start",
                    "pattern": "PRBS31",
                    "op": "write_read",
                    "name": "x",
                    "instrument": "y",
                    "wait_ms": 10_000,
                },
            ),
            ("Drummer.Target.Call", {"call": "la_group_read", "wait_ms": 10_000}),
        ]

    def test_call_and_job_are_not_arguments(self):
        session = make_session([])
        t = DrummerGroup(session).target("Drummer")
        with pytest.raises(ValueError):
            t.call("GPIO", "read", call="x")
        with pytest.raises(ValueError):
            t.call("GPIO", "read", {"job": "x"})
        assert _sent(session) == []

    def test_a_running_job_is_followed_until_it_has_ended(self):
        running = {
            "job": "3f9c0a1b2d4e5f60",
            "state": "running",
            "call": "bram_read",
            "sib": "SIB_LA_MEM",
            "progress": "",
            "ms": 10000.4,
        }
        session = make_session(
            [
                (200, WITH_FEATURE),
                (200, _value(running)),
                (200, _value(running)),
                (200, _value({"words": [1, 2, 3], "ms": 21000.0, "seq": 7})),
            ]
        )
        r = DrummerGroup(session).target("Drummer").call("LA_MEM", "bram_read", addr=0, count=3)

        assert r["words"] == [1, 2, 3]
        follows = _transactions(session)[1:]
        assert (
            follows
            == [
                (
                    "Drummer.LA_MEM.Call",
                    {"call": "job", "job": "3f9c0a1b2d4e5f60", "wait_ms": 10_000},
                )
            ]
            * 2
        )

    def test_a_job_running_past_the_timeout_names_its_id_and_is_left_running(self):
        running = {
            "job": "00aa",
            "state": "running",
            "call": "gt_ch_prbs",
            "sib": "SIB_GT0",
            "ms": 1e4,
        }
        session = make_session([(200, WITH_FEATURE)] + [(200, _value(running))] * 5)
        t = DrummerGroup(session).target("Drummer")
        now = [0.0]

        def clock() -> float:
            now[0] += 7.0  # 7 s per reading
            return now[0]

        t._clock = clock
        with pytest.raises(TimeoutError, match="job 00aa") as e:
            t.call("GT0", "gt_ch_prbs", seconds=30, timeout_s=20.0)
        assert "goes on in the module" in str(e.value)
        # the second follow waits only what is left of the timeout
        assert [b["wait_ms"] for _, b in _transactions(session)[1:]] == [10_000, 6_000]

    def test_without_the_capability_nothing_is_sent(self):
        session = make_session([(200, WITHOUT_FEATURE)])
        with pytest.raises(AccordionQ2NotSupportedError) as e:
            DrummerGroup(session).target("Drummer").call("GPIO", "read")
        assert e.value.feature == CapabilitiesDto.RESOURCES_TRANSACT == "resources.transact"
        assert "runs transactions for Admin only, under the engine lock" in str(e.value)
        assert _transactions(session) == []

    def test_the_capability_is_asked_again_after_a_failed_call(self):
        session = make_session(
            [
                (200, WITH_FEATURE),
                (200, _value({})),
                (500, {"error": "boom"}),
                (200, WITH_FEATURE),
                (200, _value({})),
            ]
        )
        t = DrummerGroup(session).target("Drummer")
        t.call("GPIO", "read")
        with pytest.raises(AccordionQ2ApiError):
            t.call("GPIO", "read")
        t.call("GPIO", "read")
        assert [p for _, p, _ in _sent(session)] == [
            "api/capabilities",
            "api/resources/transact",
            "api/resources/transact",
            "api/capabilities",
            "api/resources/transact",
        ]

    def test_a_busy_target_is_409_with_the_stations_message(self):
        message = "la_read on LA holds the JTAG now; try again when it has ended"
        session = make_session([(200, WITH_FEATURE), (409, {"error": message})])
        with pytest.raises(AccordionQ2ApiError) as e:
            DrummerGroup(session).target("Drummer").call("MMCM", "mmcm_info")
        assert e.value.status_code == 409
        assert "holds the JTAG" in str(e.value)


class TestChannels:
    def test_reads_and_writes_go_below_the_module(self):
        session = make_session(
            [
                (200, _value({"connected": True})),
                (200, _value([])),
                (200, _value({"stale": "busy", "fields": None})),
                (200, _value("233250000")),
                (200, {}),
            ]
        )
        t = DrummerGroup(session).target("Drummer.")
        assert t.prefix == "Drummer"
        assert t.status() == {"connected": True}
        assert t.jobs() == []
        assert t.snapshot("SIB_MEM")["fields"] is None
        assert t.read("CLK.Freq0") == "233250000"
        t.write("GPIO.GPIO0", "True")
        assert [b["Name"] for _, _, b in _sent(session)] == [
            "Drummer.Target.Status",
            "Drummer.Target.Jobs",
            "Drummer.MEM.Snapshot",
            "Drummer.CLK.Freq0",
            "Drummer.GPIO.GPIO0",
        ]
        assert _sent(session)[-1] == (
            "POST",
            "api/resources/value/set",
            {"Name": "Drummer.GPIO.GPIO0", "Value": "True"},
        )

    def test_segment_drops_sib(self):
        assert segment("SIB_MEM") == "MEM"
        assert segment(" LA ") == "LA"
        with pytest.raises(ValueError):
            segment("SIB_")
        assert DrummerTarget.WAIT_MS == 10_000


class TestFind:
    def test_by_the_drummer_instrument(self):
        session = make_session(
            [
                (
                    200,
                    [
                        {
                            "netName": "Drummer.Drummer",
                            "instrumentName": "Drummer",
                            "type": "Drummer",
                        },
                        {"netName": "0.4.ESH10000662.PS", "type": "PowerSupply"},
                    ],
                )
            ]
        )
        assert DrummerGroup(session).find() == [DrummerModuleRef("Drummer", "Drummer")]

    def test_by_target_status_beside_target_package_on_older_firmware(self):
        session = make_session(
            [
                (404, {"error": "not found"}),
                (
                    200,
                    ["Drummer.Target.Status", "Drummer.Target.Package", "0.2.X.Target.Status"],
                ),
            ]
        )
        assert DrummerGroup(session).find() == [DrummerModuleRef("Drummer", "Drummer")]


SHA = "4f0c1a2b" + "0" * 52 + "beef"


def _writes(session: object) -> list[tuple[str, str]]:
    return [
        (body["Name"], body["Value"])
        for _, path, body in _sent(session)
        if path == "api/resources/value/set"
    ]


class TestLibrary:
    """The package library and build identity (the firmware's Drummer/PACKAGES.md section 8)."""

    def test_library_reads_target_library(self):
        library = {
            "dir": "/home/accordion/drummer/library",
            "selection": {"source": "library", "sha256": SHA},
            "packages": [{"sha256": SHA, "file": "mh.drummer", "selected_by": ["Drummer"]}],
        }
        session = make_session([(200, _value(library))])
        assert DrummerGroup(session).target("Drummer").library() == library
        assert _sent(session)[0][2]["Name"] == "Drummer.Target.Library"

    def test_select_unselect_and_delete_write_their_channels(self):
        session = make_session([(200, {}), (200, {}), (200, {}), (200, {})])
        t = DrummerGroup(session).target("Drummer")
        t.select_package(SHA)
        t.select_package("4F0C1A2B")
        t.unselect_package()
        t.delete_package(" 9a1b2c3d ")
        assert _writes(session) == [
            ("Drummer.Target.Select", SHA),
            ("Drummer.Target.Select", "4F0C1A2B"),
            ("Drummer.Target.Select", ""),
            ("Drummer.Target.Delete", "9a1b2c3d"),
        ]

    @pytest.mark.parametrize("bad", ["4f0c", "../x", "4f0c 1a2b", "", "a" * 65, "zzzzzzzz"])
    def test_a_sha_text_that_is_not_8_to_64_hex_digits_is_refused_before_anything_is_sent(self, bad):
        session = make_session([])
        t = DrummerGroup(session).target("Drummer")
        with pytest.raises(ValueError, match="is not a SHA-256"):
            t.select_package(bad)
        with pytest.raises(ValueError, match="is not a SHA-256"):
            t.delete_package(bad)
        assert _sent(session) == []

    def test_a_delete_refused_while_selected_is_a_409_naming_the_instances(self):
        session = make_session(
            [(409, {"error": "4f0c1a2b (mh.drummer) is selected by Drummer, DUT_A: select another package there first"})]
        )
        with pytest.raises(AccordionQ2ApiError) as e:
            DrummerGroup(session).target("Drummer").delete_package(SHA)
        assert e.value.status_code == 409
        assert "selected by Drummer, DUT_A" in str(e.value)

    def test_build_is_target_status_build(self):
        build = {"rule": "marker", "runs_package": True, "text": "FPGA runs build unknown"}
        session = make_session([(200, _value({"state": "connected", "build": build}))])
        assert DrummerGroup(session).target("Drummer").build() == build
        assert _sent(session)[0][2]["Name"] == "Drummer.Target.Status"

    def test_build_is_none_on_firmware_without_build_identity(self):
        session = make_session([(200, _value({"state": "connected"}))])
        assert DrummerGroup(session).target("Drummer").build() is None

    def test_upload_package_posts_to_target_package_and_waits_until_it_is_kept(self, tmp_path):
        file = tmp_path / "mh.drummer"
        file.write_bytes(b"PK\x03\x04")
        session = make_session(
            [
                (202, {"state": "validating"}),
                (200, {"state": "done", "message": "mh.drummer: kept in the library as 4f0c1a2b (new), selected"}),
            ]
        )
        status = DrummerGroup(session).target("Drummer").upload_package(file)

        assert status.state == "done"
        assert "kept in the library" in status.message
        calls = session.request.call_args_list  # type: ignore[attr-defined]
        assert calls[0].args[0] == "POST"
        assert "api/channels/bytestream?name=Drummer.Target.Package" in calls[0].args[1]
        assert "fileName=mh.drummer" in calls[0].args[1]
        assert calls[1].args[0] == "GET"
        assert calls[1].args[1] == "api/channels/bytestream?name=Drummer.Target.Package"
        assert len(calls) == 2


def test_the_client_has_the_group():
    from accordionq2 import AccordionQ2Client

    with AccordionQ2Client("http://station:5000") as client:
        assert isinstance(client.drummer, DrummerGroup)

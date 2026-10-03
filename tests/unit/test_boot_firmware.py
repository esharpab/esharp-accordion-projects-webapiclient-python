"""Unit tests for boot.config and firmware (accordionq2 contract sections 11 and 12)."""

from __future__ import annotations

import http.client
import json

import pytest

from accordionq2._base import HttpSession
from accordionq2.boot import BootAddress, BootAliasFile, BootGroup, BootService, BootWifi
from accordionq2.exceptions import AccordionQ2ApiError
from accordionq2.firmware import FirmwareGroup
from accordionq2.system import SystemGroup


class FakeSession(HttpSession):
    """An HttpSession answering from a list and recording what was sent.

    An exception in the list is raised instead of answering, as a dropped connection would be.
    """

    def __init__(self, *responses: tuple[int, object] | BaseException) -> None:
        super().__init__("http://localhost:5000", timeout=5.0)
        self.responses = list(responses)
        self.sent: list[tuple[str, str, bytes | None, dict[str, str]]] = []

    def request(self, method, path, body=None, headers=None):  # type: ignore[override]
        self.sent.append((method, path, body, headers or {}))
        answer = self.responses.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        status, payload = answer
        return status, payload if isinstance(payload, bytes) else json.dumps(payload).encode()


BOOT = {
    "enabled": False,
    "modified": "2026-10-03T11:07:02.2880357Z",
    "description": "Default boot configuration file.",
    "aliasFiles": [{"path": "station.csv", "enabled": True, "order": 0}],
    "modules": [
        {
            "name": "Snowball",
            "assemblyPath": "additional/Snowball.dll",
            "className": "Ns.Snowball",
            "namespace": "Ns",
            "enabled": True,
        }
    ],
    "ipConfigurations": [{"interface": "eth0", "staticIp": "192.168.0.222/24", "enabled": False}],
    "wifi": {"enabled": False, "ssid": "lab", "passwordSet": True},
    "disableUsbPorts": False,
    "enableMediaDevices": False,
    "services": [{"name": "Swagger", "serviceFile": "accordionq2-webapi", "enabled": True}],
    "protectedServices": ["accordion", "accordionq2-webapi"],
}


def test_boot_is_reached_from_the_system_group():
    assert isinstance(SystemGroup(FakeSession()).boot, BootGroup)


def test_boot_config_is_read_without_the_password():
    boot = BootGroup(FakeSession((200, BOOT))).get()
    assert not boot.enabled and boot.wifi.password_set and boot.wifi.ssid == "lab"
    assert boot.alias_files[0].path == "station.csv"
    assert boot.modules[0].assembly_path == "additional/Snowball.dll"
    assert boot.ip_configurations[0].static_ip == "192.168.0.222/24"
    assert boot.protected_services == ("accordion", "accordionq2-webapi")


def test_set_startup_sends_only_the_switch_and_the_alias_files():
    session = FakeSession((200, BOOT))
    BootGroup(session).set_startup(
        enabled=True, alias_files=[BootAliasFile("a.csv"), BootAliasFile("b.csv", False)]
    )
    method, path, body, _ = session.sent[0]
    assert (method, path) == ("PUT", "api/system/boot/startup")
    assert json.loads(body) == {
        "enabled": True,
        "aliasFiles": [{"path": "a.csv", "enabled": True}, {"path": "b.csv", "enabled": False}],
    }


def test_update_sends_the_sections_given_and_keeps_the_password():
    session = FakeSession((200, BOOT))
    BootGroup(session).update(
        if_modified=BOOT["modified"],
        enabled=True,
        ip_configurations=[BootAddress("eth0", "10.0.0.5/24", True)],
        wifi=BootWifi(True, "lab", password_set=False),
        services=[BootService("NodeRed", "node-red-dashboard", False)],
    )
    method, path, body, _ = session.sent[0]
    assert (method, path) == ("PUT", "api/system/boot")
    assert json.loads(body) == {
        "ifModified": BOOT["modified"],
        "enabled": True,
        "ipConfigurations": [{"interface": "eth0", "staticIp": "10.0.0.5/24", "enabled": True}],
        "wifi": {"enabled": True, "ssid": "lab", "password": None},
        "services": [{"name": "NodeRed", "serviceFile": "node-red-dashboard", "enabled": False}],
    }


def test_update_can_clear_the_password_but_only_with_the_wifi_section():
    session = FakeSession((200, BOOT))
    BootGroup(session).update(wifi=BootWifi(False, "", False), wifi_password="")
    assert json.loads(session.sent[0][2])["wifi"] == {"enabled": False, "ssid": "", "password": ""}
    with pytest.raises(ValueError):
        BootGroup(FakeSession()).update(wifi_password="secret12")


def test_a_stale_edit_raises_409():
    session = FakeSession((409, {"error": "boot.config changed since it was read"}))
    with pytest.raises(AccordionQ2ApiError) as raised:
        BootGroup(session).update(if_modified="2026-09-01T00:00:00Z", enabled=True)
    assert raised.value.status_code == 409


STATE = {
    "current": "5.18.0",
    "source": {
        "kind": "url",
        "location": "https://esharp.blob.core.windows.net/accfirmware",
        "isDefault": True,
    },
    "defaultSource": "https://esharp.blob.core.windows.net/accfirmware",
    "supported": True,
    "minimumVersion": "6.0.0",
    "update": {"state": "idle"},
}


def test_firmware_state_is_read():
    state = FirmwareGroup(FakeSession((200, STATE))).get_state()
    assert state.current == "5.18.0" and state.minimum_version == "6.0.0" and state.supported
    assert state.source.is_default and state.update.finished


def test_releases_carry_whether_they_can_be_installed():
    releases = {
        "source": STATE["source"],
        "releases": [
            {"version": "6.0.0", "fileName": "rel-6.0.0.zip", "beta": True, "installable": True},
            {"version": "5.19.0", "fileName": "rel-5.19.0.zip", "installable": False},
        ],
        "error": None,
    }
    session = FakeSession((200, releases))
    result = FirmwareGroup(session).get_releases(include_beta=True)
    assert session.sent[0][1] == "api/system/firmware/releases?includeBeta=true"
    assert [(r.version, r.beta, r.installable) for r in result.releases] == [
        ("6.0.0", True, True),
        ("5.19.0", False, False),
    ]


def test_set_source_sends_the_location():
    session = FakeSession(
        (200, {"kind": "folder", "location": "/media/usb/fw", "isDefault": False})
    )
    source = FirmwareGroup(session).set_source("/media/usb/fw")
    assert json.loads(session.sent[0][2]) == {"location": "/media/usb/fw"}
    assert source.kind == "folder"


def test_install_waits_through_the_restart():
    session = FakeSession(
        (202, {"state": "downloading", "version": "6.0.0"}),
        (200, {"state": "installing", "version": "6.0.0"}),
        ConnectionRefusedError(),
        http.client.RemoteDisconnected("gone"),
        (503, {"error": "Hardware not connected"}),
        (200, {"state": "succeeded", "version": "6.0.0", "message": "Updated to 6.0.0"}),
    )
    firmware = FirmwareGroup(session)
    status = firmware.install("6.0.0", include_beta=True, timeout=30)
    assert status.state == "succeeded" and status.finished
    assert json.loads(session.sent[0][2]) == {"version": "6.0.0", "includeBeta": True}


def test_wait_for_update_passes_other_errors_on(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    session = FakeSession((500, {"error": "boom"}))
    with pytest.raises(AccordionQ2ApiError):
        FirmwareGroup(session).wait_for_update(timeout=5)


def test_wait_for_update_gives_up_after_the_timeout(monkeypatch):
    # A clock that moves a second per look, so the test doesn't depend on how fast the machine is.
    clock = iter(range(1000))
    monkeypatch.setattr("accordionq2.firmware.time.monotonic", lambda: next(clock))
    monkeypatch.setattr("accordionq2.firmware.time.sleep", lambda _: None)
    session = FakeSession(*[ConnectionRefusedError() for _ in range(100)])
    with pytest.raises(TimeoutError):
        FirmwareGroup(session).wait_for_update(timeout=5, poll=0)
    assert len(session.sent) <= 6


def test_an_unsigned_package_is_refused_by_the_station():
    session = FakeSession((400, {"error": "Not installed: The package isn't signed"}))
    with pytest.raises(AccordionQ2ApiError) as raised:
        FirmwareGroup(session).upload_package(b"PK\x03\x04")
    assert raised.value.status_code == 400 and "signed" in str(raised.value)


def test_a_package_is_sent_from_a_file_and_installed(tmp_path, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    package = tmp_path / "rel-6.0.0.zip"
    package.write_bytes(b"PK zip bytes")
    session = FakeSession(
        (
            200,
            {
                "version": "6.0.0",
                "fileName": "rel-6.0.0.zip",
                "origin": "uploaded",
                "downloaded": True,
            },
        ),
        (202, {"state": "staging", "version": "6.0.0"}),
        (200, {"state": "succeeded", "version": "6.0.0"}),
    )
    status = FirmwareGroup(session).install_package(package)
    method, path, body, headers = session.sent[0]
    assert (method, path, body) == ("POST", "api/system/firmware/packages", b"PK zip bytes")
    assert headers["Content-Type"] == "application/octet-stream"
    assert json.loads(session.sent[1][2])["version"] == "6.0.0"
    assert status.state == "succeeded"


def test_delete_package_quotes_the_name():
    session = FakeSession((204, b""))
    FirmwareGroup(session).delete_package("rel-6.0.0.zip")
    assert session.sent[0][:2] == ("DELETE", "api/system/firmware/packages/rel-6.0.0.zip")

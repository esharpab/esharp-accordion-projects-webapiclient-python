"""Unit tests for client.security (firmware 7.1.0; FW7_PLAN CLI-05 follow-up).

The connection is mocked; each test checks the method, path and body sent against the WebApi's
security controllers (AccountsController, SecurityController, SecurityEventsController,
SecurityHostController, ExtensionsController, FactoryResetController) and how the answer is read.
"""

from __future__ import annotations

import json
import os
import traceback
from datetime import UTC
from typing import Any, ClassVar
from unittest.mock import MagicMock

import pytest

from accordionq2 import (
    AccordionQ2ApiError,
    AccordionQ2Client,
    AccordionQ2SecurityError,
    AccordionQ2SecurityReason,
    HostSettings,
    SecurityMode,
    StationRole,
)
from accordionq2 import security as security_module
from accordionq2._base import HttpSession
from accordionq2.security import SecurityGroup

KEY = "acc_Sentinel0123456789abcdefKEY"
TOKEN = "v1.k1.eyJzIjoiU2Vzc2lvbiJ9.c2lnbmF0dXJlU2VudGluZWw"
TOKEN2 = "v1.k1.eyJzIjoiUmVuZXdlZCJ9.c2lnbmF0dXJlU2VudGluZWwy"
PASSWORD = "correct horse battery staple"
USER = {
    "id": "9f8e7d6c",
    "name": "anna",
    "role": "Operator",
    "created": "2026-11-20T10:00:00+00:00",
    "createdBy": "user:1a2b3c4d:admin",
}


def _login(token: str = TOKEN) -> dict[str, object]:
    return {
        "token": token,
        "expiresAt": "2026-11-23T12:15:00+00:00",
        "user": USER,
        "expiresIn": 900,
    }


def _response(status: int, body: object, headers: dict[str, str] | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = body if isinstance(body, bytes) else json.dumps(body).encode()
    resp.headers = headers or {}
    return resp


class Station:
    """A security group on a session whose connection answers *answers* in order."""

    def __init__(self, *answers: tuple[int, object], url: str = "https://station:5001", **kw):
        self.session = HttpSession(url, timeout=5.0, verify=False, **kw)
        self.session._conn = MagicMock()
        self.session._conn.getresponse.side_effect = [_response(s, b) for s, b in answers]
        self.security = SecurityGroup(self.session)

    def sent(self, index: int = -1) -> tuple[str, str, object, dict[str, str]]:
        call = self.session._conn.request.call_args_list[index]  # type: ignore[union-attr]
        method, path = call.args
        body = call.kwargs["body"]
        return method, path, json.loads(body) if body else None, call.kwargs["headers"]

    @property
    def calls(self) -> int:
        return self.session._conn.request.call_count  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Logins and the bearer token
# ---------------------------------------------------------------------------


class TestLogin:
    def test_login_sends_the_name_and_password_and_uses_the_token(self):
        station = Station((200, _login()), (200, b"[]"))
        result = station.security.login("anna", PASSWORD)
        method, path, body, headers = station.sent()
        assert (method, path) == ("POST", "/api/security/login")
        assert body == {"name": "anna", "password": PASSWORD}
        assert "Authorization" not in headers
        assert result.token == TOKEN
        assert result.expires_in == 900
        assert result.user.name == "anna" and result.user.role == "Operator"
        assert result.user.created_by == "user:1a2b3c4d:admin"
        assert station.session.has_bearer_token
        station.security.get_users()
        assert station.sent()[3]["Authorization"] == f"Bearer {TOKEN}"

    def test_login_without_use_leaves_the_client_as_it_was(self):
        station = Station((200, _login()))
        station.security.login("anna", PASSWORD, use=False)
        assert not station.session.has_bearer_token

    def test_the_token_is_never_in_a_repr(self):
        station = Station((200, _login()))
        result = station.security.login("anna", PASSWORD)
        assert TOKEN not in repr(result)
        assert TOKEN not in repr(station.session)
        assert "bearer_token=set" in repr(station.session)
        headers = station.session.request_headers()
        assert TOKEN not in repr(headers)
        assert headers["Authorization"] == f"Bearer {TOKEN}"

    @pytest.mark.parametrize(
        "url",
        [
            "http://station:5000",
            "http://10.0.0.5:5000",
            "http://[fe80::1%25eth0]:5000",
            # A DNS name that looks like a loopback address resolves wherever its owner likes
            "http://127.example.com:5000",
            "http://127.0.0.1.example.com:5000",
            "http://localhost.example.com:5000",
        ],
    )
    def test_no_password_over_plain_http_to_another_host(self, url):
        station = Station(url=url)
        for call in (
            lambda: station.security.login("anna", PASSWORD),
            lambda: station.security.claim(PASSWORD),
            lambda: station.security.change_password(PASSWORD, PASSWORD + "!"),
            lambda: station.security.create_user("bo", "Viewer", PASSWORD),
            lambda: station.security.set_user_password("9f8e7d6c", PASSWORD),
            lambda: station.security.install_certificate("cert", "key"),
            lambda: station.security.recovery_reset_admin(PASSWORD),
        ):
            with pytest.raises(ValueError, match="HTTPS") as info:
                call()
            assert PASSWORD not in str(info.value)
        assert station.calls == 0

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost:5000",
            "http://127.0.0.1:5000",
            "http://127.1.2.3:5000",
            "http://[::1]:5000",
            "http://[::ffff:127.0.0.1]:5000",
        ],
    )
    def test_a_password_on_the_station_itself_is_sent(self, url):
        station = Station((200, _login()), url=url)
        station.security.login("anna", PASSWORD)
        assert station.calls == 1

    def test_a_wrong_password_is_a_login_refusal_not_a_key_problem(self):
        station = Station((401, {"error": "Wrong user name or password", "requires": "Anonymous"}))
        with pytest.raises(AccordionQ2SecurityError) as info:
            station.security.login("anna", "wrong password!")
        assert info.value.reason is AccordionQ2SecurityReason.LOGIN_REFUSED
        assert str(info.value) == "Wrong user name or password"
        assert not station.session.has_bearer_token

    def test_renew_sends_the_token_and_uses_the_new_one(self):
        station = Station((200, _login(TOKEN2)), bearer_token=TOKEN)
        result = station.security.renew()
        method, path, body, headers = station.sent()
        assert (method, path, body) == ("POST", "/api/security/token/renew", None)
        assert headers["Authorization"] == f"Bearer {TOKEN}"
        assert result.token == TOKEN2
        assert station.session.request_headers()["Authorization"] == f"Bearer {TOKEN2}"

    def test_renew_without_a_login(self):
        with pytest.raises(RuntimeError, match="log in first"):
            Station().security.renew()

    def test_renew_past_twelve_hours(self):
        refusal = {
            "error": "This login can't be renewed any more: log in again",
            "requires": "Anonymous",
        }
        station = Station((401, refusal), bearer_token=TOKEN)
        with pytest.raises(AccordionQ2SecurityError) as info:
            station.security.renew()
        assert info.value.reason is AccordionQ2SecurityReason.LOGIN_REFUSED

    def test_logout_sends_it_and_forgets_the_token(self):
        station = Station((204, b""), bearer_token=TOKEN)
        station.security.logout()
        method, path, _, headers = station.sent()
        assert (method, path) == ("POST", "/api/security/logout")
        assert headers["Authorization"] == f"Bearer {TOKEN}"
        assert not station.session.has_bearer_token

    def test_logout_forgets_the_token_when_the_station_cannot_be_reached(self):
        station = Station(bearer_token=TOKEN)
        station.session._conn.request.side_effect = ConnectionRefusedError("down")  # type: ignore[union-attr]
        station.session._open = MagicMock(return_value=station.session._conn)  # type: ignore[method-assign]
        with pytest.raises(OSError):
            station.security.logout()
        assert not station.session.has_bearer_token

    def test_logout_of_an_expired_token_is_no_error(self):
        # In On the station refuses an expired token (401, the role the endpoint needs) before
        # the logout runs; the login is over all the same.
        station = Station(
            (
                401,
                {
                    "error": "This station needs an API key in X-Api-Key or a login (a login "
                    "token that expired or isn't valid was sent)",
                    "requires": "Viewer",
                },
            ),
            bearer_token=TOKEN,
        )
        station.security.logout()
        assert station.calls == 1
        assert not station.session.has_bearer_token

    def test_logout_still_raises_other_refusals(self):
        station = Station((500, {"error": "boom"}), bearer_token=TOKEN)
        with pytest.raises(AccordionQ2ApiError):
            station.security.logout()
        assert not station.session.has_bearer_token

    @pytest.mark.parametrize("call", ["logout", "renew", "change_password"])
    def test_token_calls_go_without_the_api_key(self, call):
        # The station goes by X-Api-Key before the token, and would then not end, renew or
        # change the password of the login.
        station = Station((200, _login(TOKEN2)), api_key=KEY, bearer_token=TOKEN)
        if call == "change_password":
            station.security.change_password(PASSWORD, PASSWORD + "!")
        else:
            getattr(station.security, call)()
        _, _, _, headers = station.sent()
        assert not [n for n in headers if n.lower() == "x-api-key"]
        assert headers["Authorization"] == f"Bearer {TOKEN}"
        # Every other call still sends the key
        assert station.session.request_headers()["X-Api-Key"] == KEY

    def test_a_refused_token_only_call_names_the_token_not_the_key(self):
        station = Station(
            (401, {"error": "x", "requires": "Viewer"}), api_key=KEY, bearer_token=TOKEN
        )
        with pytest.raises(AccordionQ2SecurityError) as info:
            station.security.change_password(PASSWORD, PASSWORD + "!")
        assert info.value.reason is AccordionQ2SecurityReason.INVALID_TOKEN

    def test_logout_without_a_login_sends_nothing(self):
        station = Station()
        station.security.logout()
        assert station.calls == 0

    def test_me(self):
        me = {
            "mode": "On",
            "claimed": True,
            "caller": {
                "kind": "User",
                "id": "9f8e7d6c",
                "name": "anna",
                "role": "Operator",
                "expiresAt": "2026-11-23T12:15:00+00:00",
            },
            "loginAvailable": True,
        }
        result = Station((200, me)).security.me()
        assert result.mode == SecurityMode.ON
        assert result.claimed and result.login_available
        assert result.caller is not None
        assert (result.caller.kind, result.caller.role) == ("User", "Operator")
        anonymous = Station((200, {"mode": "Off", "claimed": False, "caller": None})).security.me()
        assert anonymous.caller is None and not anonymous.login_available

    def test_claim(self):
        station = Station((201, _login()))
        station.security.claim(PASSWORD, name="root-admin")
        method, path, body, _ = station.sent()
        assert (method, path) == ("POST", "/api/security/claim")
        assert body == {"password": PASSWORD, "name": "root-admin"}  # no setup code since 7.1.0
        assert station.session.has_bearer_token
        default = Station((201, _login()))
        default.security.claim(PASSWORD)
        assert "name" not in default.sent()[2]  # type: ignore[operator]

    def test_sign_out_all_forgets_the_own_token(self):
        station = Station((204, b""), bearer_token=TOKEN)
        station.security.sign_out_all()
        method, path, body, _ = station.sent()
        assert (method, path) == ("POST", "/api/security/sessions/sign-out-all")
        assert body is None
        assert not station.session.has_bearer_token

    def test_change_password_uses_the_new_token(self):
        station = Station((200, _login(TOKEN2)), bearer_token=TOKEN)
        station.security.change_password(PASSWORD, PASSWORD + " 2")
        method, path, body, _ = station.sent()
        assert (method, path) == ("PUT", "/api/security/password")
        assert body == {"currentPassword": PASSWORD, "newPassword": PASSWORD + " 2"}
        assert station.session.request_headers()["Authorization"] == f"Bearer {TOKEN2}"

    def test_a_wrong_current_password_keeps_the_login(self):
        station = Station(
            (401, {"error": "The current password is wrong", "requires": "Anonymous"}),
            bearer_token=TOKEN,
        )
        with pytest.raises(AccordionQ2SecurityError) as info:
            station.security.change_password("not it at all", PASSWORD)
        assert info.value.reason is AccordionQ2SecurityReason.LOGIN_REFUSED
        assert station.session.request_headers()["Authorization"] == f"Bearer {TOKEN}"


class TestBearerToken:
    def test_given_to_the_client(self):
        client = AccordionQ2Client("https://s:5001", bearer_token=TOKEN)
        assert client._session.request_headers()["Authorization"] == f"Bearer {TOKEN}"
        assert TOKEN not in repr(client)

    def test_replaces_basic_auth(self):
        session = HttpSession("https://s:5001", 1.0, auth=("bob", "pw"), bearer_token=TOKEN)
        headers = session.request_headers()
        assert [n for n in headers if n.lower() == "authorization"] == ["Authorization"]
        assert headers["Authorization"] == f"Bearer {TOKEN}"

    def test_sent_beside_the_api_key(self):
        session = HttpSession("https://s:5001", 1.0, api_key=KEY, bearer_token=TOKEN)
        headers = session.request_headers()
        assert headers["X-Api-Key"] == KEY
        assert headers["Authorization"] == f"Bearer {TOKEN}"

    @pytest.mark.parametrize("bad", ["", "  ", f"{TOKEN}\r\nX-Evil: 1", f"{TOKEN} x"])
    def test_a_token_a_header_cannot_carry_is_refused_without_echoing_it(self, bad):
        with pytest.raises(ValueError) as info:
            AccordionQ2Client("https://s:5001", bearer_token=bad)
        assert TOKEN not in str(info.value)

    def test_an_expired_token_is_named(self):
        station = Station(
            (
                401,
                {
                    "error": "This station needs an API key in X-Api-Key or a login (a login "
                    "token that expired or isn't valid was sent)",
                    "requires": "Viewer",
                },
            ),
            bearer_token=TOKEN,
        )
        with pytest.raises(AccordionQ2SecurityError) as info:
            station.security.get_users()
        assert info.value.reason is AccordionQ2SecurityReason.INVALID_TOKEN
        assert "log in again" in str(info.value)
        assert info.value.required_role == "Viewer"

    def test_with_a_key_too_the_key_is_named(self):
        # The station identifies a request by its key first.
        station = Station(
            (401, {"error": "x", "requires": "Viewer"}), api_key=KEY, bearer_token=TOKEN
        )
        with pytest.raises(AccordionQ2SecurityError) as info:
            station.security.get_users()
        assert info.value.reason is AccordionQ2SecurityReason.INVALID_API_KEY

    def test_server_text_with_the_token_is_withheld(self):
        station = Station((500, {"error": f"bad token {TOKEN}"}), bearer_token=TOKEN)
        with pytest.raises(AccordionQ2ApiError) as info:
            station.security.get_users()
        assert TOKEN not in str(info.value)
        assert "withheld" in str(info.value)

    def test_a_traceback_with_locals_shows_no_token(self):
        session = HttpSession("https://s:5001", 1.0, bearer_token=TOKEN)
        conn = MagicMock()
        conn.request.side_effect = ConnectionRefusedError("refused")
        session._open = MagicMock(return_value=conn)  # type: ignore[method-assign]
        with pytest.raises(OSError) as info:
            SecurityGroup(session).get_users()
        text = "".join(
            traceback.TracebackException.from_exception(info.value, capture_locals=True).format()
        )
        assert TOKEN not in text
        assert "<login token>" in text

    def test_a_traceback_with_locals_shows_no_password(self):
        session = HttpSession("https://s:5001", 1.0)
        conn = MagicMock()
        conn.request.side_effect = ConnectionRefusedError("refused")
        session._open = MagicMock(return_value=conn)  # type: ignore[method-assign]
        security = SecurityGroup(session)
        pem = "-----BEGIN PRIVATE KEY-----SentinelKeyMaterial-----END PRIVATE KEY-----"
        for call in (
            lambda: security.login("anna", PASSWORD),
            lambda: security.claim(PASSWORD),
            lambda: security.create_user("bo", "Viewer", PASSWORD),
            lambda: security.set_user_password("9f8e7d6c", PASSWORD),
            lambda: security.install_certificate("cert", pem, password=PASSWORD),
        ):
            with pytest.raises(OSError) as info:
                call()
            frames = traceback.TracebackException.from_exception(info.value, capture_locals=True)
            # The client's own frames; http.client's beneath them hold the request bytes (as
            # for the key, docs/security.md)
            package = os.path.dirname(os.path.abspath(security_module.__file__))
            text = "".join(
                f"{f.name} {f.locals}"
                for f in frames.stack
                if os.path.dirname(os.path.abspath(f.filename)) == package
            )
            assert PASSWORD not in text
            assert "SentinelKeyMaterial" not in text
            assert "<secret>" in text
            assert "<request body with a secret>" in text  # HttpSession.request's frame

    def test_set_and_cleared(self):
        session = HttpSession("https://s:5001", 1.0)
        session.set_bearer_token(TOKEN)
        assert session.has_bearer_token
        session.set_bearer_token(None)
        assert "Authorization" not in session.request_headers()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class TestUsers:
    def test_list(self):
        users = Station((200, [USER])).security.get_users()
        assert [u.id for u in users] == ["9f8e7d6c"]

    def test_create(self):
        station = Station((201, USER))
        user = station.security.create_user("anna", StationRole.OPERATOR, PASSWORD)
        assert station.sent()[:3] == (
            "POST",
            "/api/security/users",
            {"name": "anna", "role": "Operator", "password": PASSWORD},
        )
        assert user.name == "anna"

    def test_set_password(self):
        station = Station((204, b""))
        station.security.set_user_password("9f 8e", PASSWORD)
        assert station.sent()[:3] == (
            "PUT",
            "/api/security/users/9f%208e/password",
            {"password": PASSWORD},
        )

    def test_set_role(self):
        station = Station((200, {**USER, "role": "Admin"}))
        assert station.security.set_user_role("9f8e7d6c", "Admin").role == "Admin"
        assert station.sent()[:3] == ("PUT", "/api/security/users/9f8e7d6c/role", {"role": "Admin"})

    def test_remove(self):
        station = Station((204, b""))
        station.security.remove_user("9f8e7d6c")
        assert station.sent()[:2] == ("DELETE", "/api/security/users/9f8e7d6c")

    def test_the_first_admin_refusal_is_the_stations_409(self):
        station = Station((409, {"error": "Claim the station first", "requires": "Admin"}))
        with pytest.raises(AccordionQ2ApiError) as info:
            station.security.create_user("root", "Admin", PASSWORD)
        assert info.value.status_code == 409


# ---------------------------------------------------------------------------
# The mode, keys and certificate
# ---------------------------------------------------------------------------


CERT = {
    "source": "SelfSigned",
    "sha256": "3F:A2:7C",
    "subject": "CN=A004166",
    "issuer": "CN=A004166",
    "notBefore": "2026-01-01T00:00:00+00:00",
    "notAfter": "2036-01-01T00:00:00+00:00",
    "expired": False,
    "dnsNames": ["A004166", "A004166.local"],
    "ipAddresses": ["10.0.0.5"],
    "chain": ["CN=A004166"],
    "selfSignedSha256": "3F:A2:7C",
    "nameMatchesHost": True,
    "cloned": None,
    "certificatePem": "-----BEGIN CERTIFICATE-----",
}


class TestModeKeysCertificate:
    def test_state(self):
        state = Station(
            (
                200,
                {
                    "mode": "Report",
                    "keys": [
                        {
                            "id": "1a2b3c4d",
                            "name": "assert-st01",
                            "role": "Operator",
                            "created": "2026-10-01T00:00:00+00:00",
                            "createdBy": "admin",
                            "issuedOver": None,
                        }
                    ],
                    "users": [USER],
                    "claimed": True,
                    "throttled": [
                        {
                            "client": "10.0.0.9",
                            "purpose": "Key",
                            "failures": 12,
                            "until": "2026-11-23T12:00:04+00:00",
                        }
                    ],
                    "extensionUploadsUntil": None,
                    "moduleImageRole": "Operator",
                    "extensionCheck": {
                        "release": "7.1.0",
                        "problem": None,
                        "failed": ["x"],
                        "unsigned": [],
                    },
                },
            )
        ).security.get_state()
        assert state.mode == "Report"
        assert state.keys[0].issued_over is None
        assert state.users[0].name == "anna"
        assert state.throttled is not None and state.throttled[0].failures == 12
        assert state.module_image_role == "Operator"
        assert state.extension_check is not None and state.extension_check.failed == ("x",)
        assert state.warnings is None

    def test_state_of_an_older_station(self):
        state = Station((200, {"mode": "Off", "keys": []})).security.get_state()
        assert state.throttled is None and state.users == () and state.module_image_role == "Admin"

    def test_set_mode(self):
        station = Station((200, {"mode": "On", "keys": [], "warnings": ["Firewall not loaded"]}))
        state = station.security.set_mode(SecurityMode.ON)
        assert station.sent()[:3] == ("PUT", "/api/security/mode", {"mode": "On"})
        assert state.warnings == ("Firewall not loaded",)

    def test_create_key_never_shows_the_key_in_a_repr(self):
        station = Station(
            (
                201,
                {
                    "info": {
                        "id": "1a2b3c4d",
                        "name": "line-3",
                        "role": "Operator",
                        "created": "2026-11-23T00:00:00+00:00",
                        "createdBy": "admin",
                        "issuedOver": "Https",
                    },
                    "key": KEY,
                },
            )
        )
        created = station.security.create_key("line-3", "Operator")
        assert station.sent()[:3] == (
            "POST",
            "/api/security/keys",
            {"name": "line-3", "role": "Operator"},
        )
        assert created.key == KEY and created.info.issued_over == "Https"
        assert KEY not in repr(created)
        assert created.warnings is None

    def test_revoke_key(self):
        station = Station((204, b""))
        station.security.revoke_key("1a2b3c4d")
        assert station.sent()[:2] == ("DELETE", "/api/security/keys/1a2b3c4d")

    def test_get_certificate(self):
        cert = Station((200, CERT)).security.get_certificate()
        assert cert.sha256 == "3F:A2:7C" and cert.dns_names == ("A004166", "A004166.local")
        assert cert.cloned is None and cert.open_connections_closed is None

    def test_install_pem(self):
        station = Station(
            (200, {**CERT, "source": "Site", "openConnectionsClosed": 2, "warnings": []})
        )
        cert = station.security.install_certificate("CERT", "KEY", password="pw")
        assert station.sent()[:3] == (
            "PUT",
            "/api/security/certificate",
            {"certificatePem": "CERT", "privateKeyPem": "KEY", "password": "pw"},
        )
        assert cert.source == "Site" and cert.open_connections_closed == 2

    def test_install_pfx(self):
        station = Station((200, CERT))
        station.security.install_certificate(pfx=b"\x30\x82", password="pw")
        assert station.sent()[2] == {"pfxBase64": "MII=", "password": "pw"}

    def test_remove_and_regenerate(self):
        station = Station((200, CERT), (200, CERT), (200, CERT))
        station.security.remove_certificate()
        assert station.sent()[:2] == ("DELETE", "/api/security/certificate")
        station.security.regenerate_certificate()
        assert station.sent()[:3] == ("POST", "/api/security/certificate/regenerate", None)
        station.security.regenerate_certificate(["station-12.lab", "10.0.0.5"])
        assert station.sent()[2] == {"extraNames": ["station-12.lab", "10.0.0.5"]}

    def test_expiry_warning_and_default_request_names(self):
        cert = Station(
            (
                200,
                {
                    **CERT,
                    "warnings": ["expires 2026-12-01"],
                    "defaultRequestNames": ["A004166", "A004166.local"],
                },
            )
        ).security.get_certificate()
        assert cert.warnings == ("expires 2026-12-01",)
        assert cert.default_request_names == ("A004166", "A004166.local")
        assert Station((200, CERT)).security.get_certificate().default_request_names is None

    def test_certificate_request(self):
        made = {
            "names": ["A004166", "10.0.0.5"],
            "created": "2026-11-23T10:00:00+00:00",
            "createdBy": "user 1 'admin'",
            "csrPem": "-----BEGIN CERTIFICATE REQUEST-----",
            "publicKeySha256": "8C:1D",
            "replaced": True,
            "warnings": ["It replaced the pending request"],
        }
        station = Station(
            (200, made),
            (200, {**made, "replaced": None, "warnings": None}),
            (200, made),
            (404, {"error": "No certificate request is pending", "requires": "Admin"}),
            (204, b""),
        )
        request = station.security.request_certificate(["A004166", "10.0.0.5"])
        assert station.sent()[:3] == (
            "POST",
            "/api/security/certificate/request",
            {"names": ["A004166", "10.0.0.5"]},
        )
        assert request.names == ("A004166", "10.0.0.5") and request.replaced is True
        assert request.csr_pem.startswith("-----BEGIN CERTIFICATE REQUEST-----")
        assert request.public_key_sha256 == "8C:1D" and request.created_by == "user 1 'admin'"
        request = station.security.request_certificate()
        assert station.sent()[:3] == ("POST", "/api/security/certificate/request", None)
        assert request.replaced is None and request.warnings is None
        pending = station.security.get_certificate_request()
        assert station.sent()[:2] == ("GET", "/api/security/certificate/request")
        assert pending is not None and pending.names[0] == "A004166"
        assert station.security.get_certificate_request() is None
        station.security.delete_certificate_request()
        assert station.sent()[:2] == ("DELETE", "/api/security/certificate/request")

    def test_install_signed_certificate(self):
        station = Station((200, {**CERT, "source": "Site", "openConnectionsClosed": 1}))
        cert = station.security.install_signed_certificate("LEAF+CHAIN")
        assert station.sent()[:3] == (
            "PUT",
            "/api/security/certificate",
            {"certificatePem": "LEAF+CHAIN"},
        )
        assert cert.source == "Site"
        with pytest.raises(ValueError):
            station.security.install_signed_certificate("  ")


# ---------------------------------------------------------------------------
# The security event log
# ---------------------------------------------------------------------------


class TestEvents:
    ANSWER: ClassVar[dict[str, Any]] = {
        "events": [
            {
                "time": "2026-11-23T11:00:00+00:00",
                "kind": "LoginFailed",
                "who": "-",
                "client": "10.0.0.9",
                "forwardedFor": None,
                "mode": "On",
                "endpoint": "POST /api/security/login",
                "data": {"why": "wrongPassword", "user": "anna"},
            }
        ],
        "maxAgeDays": 365,
        "maxBytes": 10485760,
        "oldest": "2026-01-01T00:00:00+00:00",
    }

    def test_default(self):
        station = Station((200, self.ANSWER))
        result = station.security.get_events()
        assert station.sent()[:2] == ("GET", "/api/security/events?tail=200")
        assert result.events[0].kind == "LoginFailed"
        assert result.events[0].data == {"why": "wrongPassword", "user": "anna"}
        assert result.max_bytes == 10485760

    def test_since_and_kinds(self):
        from datetime import UTC, datetime, timedelta, timezone

        station = Station((200, self.ANSWER), (200, self.ANSWER))
        station.security.get_events(
            tail=50,
            since=datetime(2026, 11, 23, 12, 0, tzinfo=timezone(timedelta(hours=1))),
            kinds=["LoginFailed", "Throttled"],
        )
        assert station.sent()[1] == (
            "/api/security/events?tail=50&since=2026-11-23T12%3A00%3A00%2B01%3A00"
            "&kind=LoginFailed&kind=Throttled"
        )
        station.security.get_events(since=datetime(2026, 11, 23, tzinfo=UTC).isoformat())
        assert "since=2026-11-23T00%3A00%3A00%2B00%3A00" in station.sent()[1]


# ---------------------------------------------------------------------------
# The firewall
# ---------------------------------------------------------------------------


class TestHost:
    ANSWER: ClassVar[dict[str, Any]] = {
        "settings": {"xvcPorts": [2542], "xvcFrom": []},
        "firewall": {"state": "Applied", "problem": None, "at": "2026-11-23T11:00:00+00:00"},
        "ssh": {"state": "Failed", "problem": "sshd -t failed", "at": None},
        "tcpPorts": [5001, 443],
        "sshPort": 22,
        "warnings": ["The firewall isn't loaded: x"],
    }

    def test_get(self):
        host = Station((200, self.ANSWER)).security.get_host()
        assert host.settings == HostSettings((2542,), ())
        # An earlier 7.1.0 beta's members are read past
        old = {"sshAllowed": False, "containerPorts": [7000]}
        assert HostSettings.from_dict(old) == HostSettings()
        assert host.firewall.state == "Applied" and host.ssh.problem == "sshd -t failed"
        assert host.tcp_ports == (5001, 443) and host.ssh_port == 22
        assert host.warnings == ("The firewall isn't loaded: x",)

    def test_set(self):
        station = Station((200, self.ANSWER))
        station.security.set_host(HostSettings(xvc_ports=(2542,), xvc_from=("10.0.0.7",)))
        assert station.sent()[:3] == (
            "PUT",
            "/api/security/host",
            {"xvcPorts": [2542], "xvcFrom": ["10.0.0.7"]},
        )

    def test_no_ssh_key_calls(self):
        # SSH is E-Sharp's service access: the client has no SSH key calls
        for name in ("get_ssh_keys", "add_ssh_key", "remove_ssh_key"):
            assert not hasattr(Station((200, {})).security, name)


# ---------------------------------------------------------------------------
# Extensions and module images
# ---------------------------------------------------------------------------


FOLDER = {
    "folder": "MicroHAPS",
    "state": "Unsigned",
    "digest": "ab12",
    "files": 3,
    "changedFiles": [],
    "missingFiles": [],
    "extraFiles": [],
    "links": [],
    "acceptedBy": None,
    "acceptedAt": None,
    "referencedBy": ["MicroHAPS"],
    "unreadable": [],
}


class TestExtensions:
    def test_report(self):
        report = Station(
            (
                200,
                {
                    "release": {
                        "version": "7.1.0",
                        "source": "copy",
                        "signer": "CN=E-Sharp",
                        "signedAt": None,
                        "problem": None,
                    },
                    "folders": [FOLDER],
                    "outside": [
                        {
                            "module": "X",
                            "assemblyPath": "/opt/x.dll",
                            "source": "boot.config",
                            "enabled": True,
                            "folder": None,
                        }
                    ],
                },
            )
        ).security.get_extensions()
        assert report.release.version == "7.1.0"
        assert report.folders[0].state == "Unsigned" and report.folders[0].referenced_by == (
            "MicroHAPS",
        )
        assert report.outside[0].folder is None and report.outside[0].assembly_path == "/opt/x.dll"

    def test_accept_and_withdraw(self):
        station = Station(
            (200, {"folder": {**FOLDER, "state": "Accepted"}, "warnings": ["unsigned code"]}),
            (204, b""),
        )
        folder, warnings = station.security.accept_extension("MicroHAPS", "ab12")
        assert station.sent()[:3] == (
            "POST",
            "/api/security/extensions/accept",
            {"folder": "MicroHAPS", "digest": "ab12"},
        )
        assert folder.state == "Accepted" and warnings == ["unsigned code"]
        station.security.withdraw_extension("Micro HAPS")
        assert station.sent()[:2] == (
            "DELETE",
            "/api/security/extensions/accept?folder=Micro%20HAPS",
        )

    def test_a_changed_folder_is_the_stations_409(self):
        station = Station(
            (409, {"error": "MicroHAPS changed since it was read", "requires": "Admin"})
        )
        with pytest.raises(AccordionQ2ApiError) as info:
            station.security.accept_extension("MicroHAPS", "old")
        assert info.value.status_code == 409

    def test_upload_window_and_module_image_role(self):
        station = Station(
            (
                200,
                {"extensionUploadsUntil": "2026-11-23T13:00:00+00:00", "warnings": ["Until ..."]},
            ),
            (200, {"extensionUploadsUntil": None, "warnings": None}),
            (200, {"moduleImageRole": "Operator", "warnings": ["Operators may load ..."]}),
        )
        until, warnings = station.security.set_extension_uploads(60)
        assert station.sent()[:3] == ("PUT", "/api/security/extension-uploads", {"minutes": 60})
        assert until == "2026-11-23T13:00:00+00:00" and warnings == ["Until ..."]
        assert station.security.set_extension_uploads(0) == (None, [])
        role, _ = station.security.set_module_image_role(StationRole.OPERATOR)
        assert station.sent()[:3] == ("PUT", "/api/security/module-images", {"role": "Operator"})
        assert role == "Operator"


# ---------------------------------------------------------------------------
# The factory reset
# ---------------------------------------------------------------------------


class TestFactoryReset:
    def test_preview(self):
        preview = Station(
            (
                200,
                {
                    "hostName": "A004166",
                    "keys": 2,
                    "users": 1,
                    "certificate": True,
                    "stationSettings": True,
                    "aliasFiles": 3,
                    "stateMachines": 0,
                    "captures": 4,
                    "calibrationFiles": 5,
                    "unshippedExtensions": ["X"],
                    "extensionListPresent": True,
                    "drummerFiles": 0,
                    "authorizedKeys": True,
                    "erased": ["keys"],
                    "kept": ["firmware"],
                },
            )
        ).security.factory_reset_preview()
        assert preview.host_name == "A004166" and preview.calibration_files == 5
        assert preview.unshipped_extensions == ("X",) and preview.kept == ("firmware",)

    def test_start(self):
        station = Station(
            (202, {"unit": "accordion-factory-reset", "message": "The station stops"})
        )
        started = station.security.factory_reset("A004166", erase_calibration=True)
        assert station.sent()[:3] == (
            "POST",
            "/api/security/factory-reset",
            {"confirm": "A004166", "eraseCalibration": True},
        )
        assert started.unit == "accordion-factory-reset"

    def test_a_wrong_name_is_the_stations_400(self):
        station = Station((400, {"error": "Type the station's host name", "requires": "Admin"}))
        with pytest.raises(AccordionQ2ApiError) as info:
            station.security.factory_reset("wrong")
        assert info.value.status_code == 400

    def test_last(self):
        station = Station(
            (
                200,
                {
                    "time": "2026-11-01T00:00:00+00:00",
                    "by": "user:1:admin",
                    "client": "10.0.0.9",
                    "version": "7.1.0",
                    "calibrationErased": False,
                    "erased": ["keys"],
                    "kept": ["firmware"],
                    "warnings": [],
                    "rebooted": True,
                },
            ),
            (404, {"error": "This station has no record of a factory reset", "requires": "Admin"}),
        )
        record = station.security.last_factory_reset()
        assert record is not None and record.rebooted and record.by == "user:1:admin"
        assert station.security.last_factory_reset() is None


# ---------------------------------------------------------------------------
# The recovery drive (firmware 7.1.0)
# ---------------------------------------------------------------------------


class TestRecoveryDrive:
    def test_the_window(self):
        station = Station(
            (
                200,
                {
                    "window": "open",
                    "until": "2026-11-23T12:15:00+00:00",
                    "usbPortsOff": True,
                    "hint": "A recovery drive for this station is in it",
                    "steps": ["one", "two"],
                },
            ),
            (404, b""),
        )
        window = station.security.get_recovery()
        assert window is not None and window.is_open and window.usb_ports_off
        assert window.until == "2026-11-23T12:15:00+00:00"
        assert window.steps == ("one", "two")
        assert station.sent()[:2] == ("GET", "/api/security/recovery")
        assert station.security.get_recovery() is None  # a station before 7.1.0

    def test_the_window_names_the_station_and_the_drive(self):
        station = Station(
            (
                200,
                {
                    "window": "closed",
                    "until": None,
                    "usbPortsOff": False,
                    "hint": "made by an earlier firmware",
                    "steps": [],
                    "station": "A002531",
                    "created": "2026-11-24T08:00:00+00:00",
                    "why": "Outdated",
                },
            )
        )
        window = station.security.get_recovery()
        assert window is not None and not window.is_open
        assert (window.station, window.created, window.why) == (
            "A002531",
            "2026-11-24T08:00:00+00:00",
            "Outdated",
        )

    def test_the_hash_vector(self):
        # The vector the station, the Web UI and the .NET client test too
        secret = bytes(range(32))
        expected = "c99869a7262e1fc9bf8806c9dde1ee147b87cf24ac8668913e7e934bb8227d2b"
        assert (
            security_module.recovery_drive_hash(secret, "a002531", "2026-11-24T08:00:00Z")
            == expected
        )
        assert (
            security_module.recovery_drive_hash(secret, " A002531 ", "2026-11-24T08:00:00Z")
            == expected
        )
        assert (
            security_module.recovery_drive_hash(secret, "A002531", "2026-11-24T08:00:01Z")
            != expected
        )

    def test_the_client_makes_the_drive_and_keeps_the_secret(self, tmp_path):
        from datetime import datetime

        station = Station()
        data = station.security.make_recovery_drive(
            "A002531", datetime(2026, 11, 24, 9, 0, 0, 123000, tzinfo=UTC)
        )
        assert station.calls == 0  # the station doesn't make it
        text = data.decode("utf-8")
        assert text.endswith("}\n")
        file = json.loads(text)
        assert list(file) == ["kind", "station", "created", "hash"]
        assert (file["kind"], file["station"], file["created"]) == (
            "accordion-recovery",
            "A002531",
            "2026-11-24T09:00:00Z",
        )
        key = station.security.recovery_key
        assert key is not None and len(key.secret) == 64
        assert key.secret not in text and key.secret not in repr(key)
        assert file["hash"] == security_module.recovery_drive_hash(
            bytes.fromhex(key.secret), "A002531", "2026-11-24T09:00:00Z"
        )
        station.security.save_recovery_key(tmp_path / "key.json")
        saved = json.loads((tmp_path / "key.json").read_text(encoding="utf-8"))
        assert saved == {
            "kind": "accordion-recovery-key",
            "station": "A002531",
            "created": "2026-11-24T09:00:00Z",
            "secret": key.secret,
        }
        other = Station()
        assert other.security.load_recovery_key(tmp_path / "key.json") == key
        (tmp_path / "bad.json").write_text(
            '{"kind":"accordion-recovery-key","station":"A","created":"x","secret":"zz"}'
        )
        with pytest.raises(ValueError):
            other.security.load_recovery_key(tmp_path / "bad.json")
        station.security.make_recovery_drive("A002531")
        assert station.security.recovery_key.secret != key.secret  # a new drive, a new secret

    @pytest.mark.skipif(
        os.name == "nt", reason="Windows: the key file gets its folder's permissions"
    )
    def test_the_key_file_is_readable_by_its_owner_only(self, tmp_path):
        path = tmp_path / "key.json"
        path.write_text("old", encoding="utf-8")
        path.chmod(0o644)  # a file that was there, readable by everyone
        station = Station()
        station.security.make_recovery_drive("A002531")
        station.security.save_recovery_key(path)
        assert path.stat().st_mode & 0o777 == 0o600
        assert Station().security.load_recovery_key(path) == station.security.recovery_key
        fresh = tmp_path / "fresh.json"
        station.security.save_recovery_key(fresh)
        assert fresh.stat().st_mode & 0o777 == 0o600

    def test_the_key_file_is_one_line_of_json(self, tmp_path):
        station = Station()
        station.security.make_recovery_drive("A002531")
        station.security.save_recovery_key(tmp_path / "key.json")
        data = (tmp_path / "key.json").read_bytes()
        assert data.endswith(b"}\n") and b"\r" not in data

    def test_the_drive_can_be_made_at_the_stations_time(self):
        station = Station(
            (
                200,
                {
                    "window": "closed",
                    "hint": "",
                    "steps": [],
                    "station": "A002531",
                    "why": "ClockBehind",
                    "now": "2026-11-21T08:00:00+00:00",
                },
            )
        )
        window = station.security.get_recovery()
        assert window is not None and window.now == "2026-11-21T08:00:00+00:00"
        data = station.security.make_recovery_drive(window.station, window.now)
        assert json.loads(data)["created"] == "2026-11-21T08:00:00Z"
        assert station.security.recovery_key.created == "2026-11-21T08:00:00Z"

    def test_the_reset_goes_without_the_key_and_the_token_and_doesnt_log_in(self):
        answer = {
            "user": {**USER, "name": "admin", "role": "Admin"},
            "created": False,
            "message": "Sign in",
        }
        station = Station((200, answer), (200, answer), api_key=KEY, bearer_token=TOKEN)
        station.security.make_recovery_drive("A002531")
        secret = station.security.recovery_key.secret
        result = station.security.recovery_reset_admin(PASSWORD)
        method, path, body, headers = station.sent()
        assert (method, path) == ("POST", "/api/security/recovery/reset-admin")
        assert body == {"password": PASSWORD, "secret": secret}
        assert "X-Api-Key" not in headers and "Authorization" not in headers
        assert result.user.name == "admin" and not result.created
        assert station.session.request_headers()["Authorization"] == f"Bearer {TOKEN}"
        station.security.recovery_reset_admin(PASSWORD, user="lab")
        assert station.sent()[2] == {"password": PASSWORD, "secret": secret, "user": "lab"}

    def test_without_a_key_nothing_is_sent(self):
        station = Station()
        with pytest.raises(ValueError, match="make_recovery_drive"):
            station.security.recovery_reset_admin(PASSWORD)
        assert station.calls == 0
        with pytest.raises(ValueError):
            station.security.save_recovery_key("unused.json")

    def test_a_drive_made_elsewhere_is_the_stations_403(self):
        station = Station(
            (
                403,
                {
                    "error": "This recovery drive was made in another browser; "
                    "make a new one in this browser",
                    "requires": "Anonymous",
                },
            )
        )
        station.security.make_recovery_drive("A002531")
        with pytest.raises(AccordionQ2ApiError) as info:
            station.security.recovery_reset_admin(PASSWORD)
        assert info.value.status_code == 403
        assert "made in another browser" in str(info.value)
        assert station.security.recovery_key.secret not in str(info.value)

    def test_without_a_drive_it_is_the_stations_409(self):
        station = Station(
            (
                409,
                {
                    "error": "No recovery drive is in the station: insert the recovery drive",
                    "requires": "Anonymous",
                },
            )
        )
        station.security.make_recovery_drive("A002531")
        with pytest.raises(AccordionQ2ApiError) as info:
            station.security.recovery_reset_admin(PASSWORD)
        assert info.value.status_code == 409
        assert "insert the recovery drive" in str(info.value)
        assert PASSWORD not in str(info.value)


def test_on_the_client():
    assert isinstance(AccordionQ2Client("https://s:5001").security, SecurityGroup)


def test_use_token():
    station = Station((200, [USER]))
    assert not station.security.has_token
    station.security.use_token(TOKEN)
    assert station.security.has_token
    station.security.get_users()
    assert station.sent()[3]["Authorization"] == f"Bearer {TOKEN}"
    station.security.use_token(None)
    assert not station.security.has_token

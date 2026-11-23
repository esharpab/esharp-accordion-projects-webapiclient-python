"""The station's security calls (firmware 7.1.0; FW7_PLAN CLI-05 follow-up).

Everything under ``/api/security`` of the WebApi's six security controllers: the mode,
API keys and the TLS certificate (``SecurityController``), logins, the claim and the users
(``AccountsController``), the security event log (``SecurityEventsController``), the firewall,
SSH and the ``accordion`` user's SSH keys (``SecurityHostController``), extensions and module
images (``ExtensionsController``) and the factory reset (``FactoryResetController``).

All of it is Admin (in mode ``Off`` that is anyone) except the logins: ``login``, ``me`` and
``claim`` are anonymous, ``renew``, ``logout`` and ``change_password`` need a login. Nothing
here needs the control lease. Calls that carry a password or a private key are refused by the
client before sending over plain HTTP to another host (the station refuses them too, but only
after they crossed the network in clear text).

Fields the station returns are kept as it sends them: times as ISO 8601 strings, enums
(``"Admin"``, ``"On"``) as str, so a later value doesn't break an older client.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from urllib.parse import quote, urlencode

from ._base import ApiGroupBase
from .exceptions import AccordionQ2ApiError


class SecurityMode(StrEnum):
    """What the station does about authentication."""

    #: As 6.x: nobody is refused.
    OFF = "Off"
    #: Nobody is refused, but what ``On`` would refuse is logged.
    REPORT = "Report"
    #: Requests without a valid key or login are refused (401), too low a role too (403).
    ON = "On"


class StationRole(StrEnum):
    """Who may call an endpoint, lowest first."""

    ANONYMOUS = "Anonymous"
    VIEWER = "Viewer"
    OPERATOR = "Operator"
    ADMIN = "Admin"


def _strs(value: object) -> tuple[str, ...]:
    return tuple(str(v) for v in value) if isinstance(value, list) else ()


def _opt_strs(value: object) -> tuple[str, ...] | None:
    return _strs(value) if isinstance(value, list) else None


def _opt_str(value: object) -> str | None:
    return None if value is None else str(value)


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


# ---------------------------------------------------------------------------
# Users and logins (AccountsController)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UserInfo:
    """A user as listed: never the password or its hash."""

    id: str
    name: str
    #: ``Viewer``, ``Operator`` or ``Admin``.
    role: str
    #: When it was made (ISO 8601).
    created: str
    created_by: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> UserInfo:
        return cls(
            id=str(d.get("id", "")),
            name=str(d.get("name", "")),
            role=str(d.get("role", "")),
            created=str(d.get("created", "")),
            created_by=str(d.get("createdBy", "")),
        )


@dataclass(frozen=True, slots=True)
class LoginResponse:
    """A login token for ``Authorization: Bearer``, and whose it is.

    The token lasts 15 minutes and can be renewed (:meth:`SecurityGroup.renew`) until 12 hours
    after the login. Time it by :attr:`expires_in` on this computer's clock, not by
    :attr:`expires_at`, which is the station's clock.
    """

    #: The token; never shown by ``repr()``.
    token: str = field(repr=False)
    #: When it expires, by the station's clock (ISO 8601).
    expires_at: str
    user: UserInfo
    #: Seconds it lasts from this answer; None from a station before it was added.
    expires_in: int | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LoginResponse:
        expires_in = d.get("expiresIn")
        return cls(
            token=str(d.get("token", "")),
            expires_at=str(d.get("expiresAt", "")),
            user=UserInfo.from_dict(_dict(d.get("user"))),
            expires_in=int(expires_in) if isinstance(expires_in, (int, float)) else None,
        )


@dataclass(frozen=True, slots=True)
class CallerInfo:
    """Who a request was identified as: a key or a login."""

    #: ``Key`` or ``User``.
    kind: str
    id: str
    name: str
    role: str
    #: When a login token expires (ISO 8601); None for a key.
    expires_at: str | None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CallerInfo:
        return cls(
            kind=str(d.get("kind", "")),
            id=str(d.get("id", "")),
            name=str(d.get("name", "")),
            role=str(d.get("role", "")),
            expires_at=_opt_str(d.get("expiresAt")),
        )


@dataclass(frozen=True, slots=True)
class MeInfo:
    """The mode, whether the station is claimed, who this client is, whether logins work."""

    mode: str
    #: Whether an admin user exists.
    claimed: bool
    #: None: this client sent no credential, or one the station doesn't accept.
    caller: CallerInfo | None
    #: False when logins are off on the station (its signing keys couldn't be read).
    login_available: bool

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MeInfo:
        caller = d.get("caller")
        return cls(
            mode=str(d.get("mode", "")),
            claimed=bool(d.get("claimed")),
            caller=CallerInfo.from_dict(caller) if isinstance(caller, dict) else None,
            login_available=bool(d.get("loginAvailable")),
        )


# ---------------------------------------------------------------------------
# The mode, keys and certificate (SecurityController)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ApiKeyInfo:
    """An API key as listed: never the key itself."""

    id: str
    name: str
    role: str
    created: str
    created_by: str
    #: ``Https``, ``Loopback`` or ``Http``; None for keys made before 7.0.5 (counted as HTTP).
    issued_over: str | None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ApiKeyInfo:
        return cls(
            id=str(d.get("id", "")),
            name=str(d.get("name", "")),
            role=str(d.get("role", "")),
            created=str(d.get("created", "")),
            created_by=str(d.get("createdBy", "")),
            issued_over=_opt_str(d.get("issuedOver")),
        )


@dataclass(frozen=True, slots=True)
class CreatedApiKey:
    """A new API key: :attr:`key` is shown this once only, so store it."""

    info: ApiKeyInfo
    #: The key (``acc_...``); never shown by ``repr()``.
    key: str = field(repr=False)
    #: E.g. that it was issued over plain HTTP; None for none.
    warnings: tuple[str, ...] | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CreatedApiKey:
        return cls(
            info=ApiKeyInfo.from_dict(_dict(d.get("info"))),
            key=str(d.get("key", "")),
            warnings=_opt_strs(d.get("warnings")),
        )


@dataclass(frozen=True, slots=True)
class ThrottledClient:
    """A client address the failed-credential throttle blocks now."""

    #: The address key (an IPv6 address by its /64).
    client: str
    #: ``Key`` or ``Password``.
    purpose: str
    failures: int
    #: Blocked until (ISO 8601).
    until: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ThrottledClient:
        return cls(
            client=str(d.get("client", "")),
            purpose=str(d.get("purpose", "")),
            failures=int(d.get("failures", 0)),
            until=str(d.get("until", "")),
        )


@dataclass(frozen=True, slots=True)
class ExtensionCheckSummary:
    """The last extension check: the release checked against, failed and unsigned folders."""

    #: The release's version; None when none applies (see :attr:`problem`).
    release: str | None
    problem: str | None
    #: Folders that failed their check (``Changed``).
    failed: tuple[str, ...]
    #: ``Unsigned`` folders a module loads from.
    unsigned: tuple[str, ...]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExtensionCheckSummary:
        return cls(
            release=_opt_str(d.get("release")),
            problem=_opt_str(d.get("problem")),
            failed=_strs(d.get("failed")),
            unsigned=_strs(d.get("unsigned")),
        )


@dataclass(frozen=True, slots=True)
class SecurityState:
    """``GET /api/security``: the mode, the keys, the users and what is blocked."""

    mode: str
    keys: tuple[ApiKeyInfo, ...]
    #: After a mode change: keys whose secrets crossed the network in clear text, and what
    #: else acted on the change (the firewall, SSH). None for none.
    warnings: tuple[str, ...] | None = None
    users: tuple[UserInfo, ...] = ()
    #: Whether an admin user exists.
    claimed: bool = False
    #: The clients blocked now for failed credentials; None for none.
    throttled: tuple[ThrottledClient, ...] | None = None
    #: Until when the extension upload window is open (ISO 8601); None: closed.
    extension_uploads_until: str | None = None
    #: The role module images need in mode ``On``.
    module_image_role: str = "Admin"
    #: The last extension check; None before the first.
    extension_check: ExtensionCheckSummary | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SecurityState:
        throttled = d.get("throttled")
        check = d.get("extensionCheck")
        return cls(
            mode=str(d.get("mode", "")),
            keys=tuple(ApiKeyInfo.from_dict(k) for k in d.get("keys") or ()),
            warnings=_opt_strs(d.get("warnings")),
            users=tuple(UserInfo.from_dict(u) for u in d.get("users") or ()),
            claimed=bool(d.get("claimed")),
            throttled=tuple(ThrottledClient.from_dict(t) for t in throttled)
            if isinstance(throttled, list)
            else None,
            extension_uploads_until=_opt_str(d.get("extensionUploadsUntil")),
            module_image_role=str(d.get("moduleImageRole") or "Admin"),
            extension_check=ExtensionCheckSummary.from_dict(check)
            if isinstance(check, dict)
            else None,
        )


@dataclass(frozen=True, slots=True)
class CertificateInfo:
    """The certificate HTTPS serves: public parts only, never the key.

    :attr:`sha256` is what a client pins (``cert_sha256=``).
    """

    #: ``SelfSigned`` or ``Site``.
    source: str
    sha256: str
    subject: str
    issuer: str
    not_before: str
    not_after: str
    expired: bool
    dns_names: tuple[str, ...]
    ip_addresses: tuple[str, ...]
    #: The subjects, leaf first.
    chain: tuple[str, ...]
    #: The station's own self-signed certificate's fingerprint, also while a site one serves.
    self_signed_sha256: str | None
    name_matches_host: bool
    #: ``{"madeOnBoard": ..., "thisBoard": ...}`` when this start found the certificate made on
    #: another board (a cloned SD card) and made a new one; None otherwise.
    cloned: dict[str, Any] | None
    #: The public certificate as PEM, to import as trusted.
    certificate_pem: str
    #: Install, remove, regenerate: the open TLS connections the change closed.
    open_connections_closed: int | None = None
    warnings: tuple[str, ...] | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CertificateInfo:
        cloned = d.get("cloned")
        closed = d.get("openConnectionsClosed")
        return cls(
            source=str(d.get("source", "")),
            sha256=str(d.get("sha256", "")),
            subject=str(d.get("subject", "")),
            issuer=str(d.get("issuer", "")),
            not_before=str(d.get("notBefore", "")),
            not_after=str(d.get("notAfter", "")),
            expired=bool(d.get("expired")),
            dns_names=_strs(d.get("dnsNames")),
            ip_addresses=_strs(d.get("ipAddresses")),
            chain=_strs(d.get("chain")),
            self_signed_sha256=_opt_str(d.get("selfSignedSha256")),
            name_matches_host=bool(d.get("nameMatchesHost")),
            cloned=cloned if isinstance(cloned, dict) else None,
            certificate_pem=str(d.get("certificatePem", "")),
            open_connections_closed=int(closed) if isinstance(closed, int) else None,
            warnings=_opt_strs(d.get("warnings")),
        )


# ---------------------------------------------------------------------------
# The security event log (SecurityEventsController)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SecurityEvent:
    """One security event: when, what, who, from which client, and details."""

    time: str
    #: E.g. ``LoginFailed``, ``KeyCreated``, ``Throttled`` (the station's SecurityEventKind).
    kind: str
    #: ``key:<id>:<name>``, ``user:<id>:<name>``, ``-``, ``station``, ``installer``,
    #: ``ssh:accordion``.
    who: str
    client: str
    #: The X-Forwarded-For a client claimed (logged, never trusted).
    forwarded_for: str | None
    mode: str
    endpoint: str | None
    data: dict[str, str] | None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SecurityEvent:
        data = d.get("data")
        return cls(
            time=str(d.get("time", "")),
            kind=str(d.get("kind", "")),
            who=str(d.get("who", "")),
            client=str(d.get("client", "")),
            forwarded_for=_opt_str(d.get("forwardedFor")),
            mode=str(d.get("mode", "")),
            endpoint=_opt_str(d.get("endpoint")),
            data={str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else None,
        )


@dataclass(frozen=True, slots=True)
class SecurityEvents:
    """Security events, newest first, and how much the log keeps."""

    events: tuple[SecurityEvent, ...]
    max_age_days: int
    max_bytes: int
    #: The oldest event kept (ISO 8601); None for none.
    oldest: str | None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SecurityEvents:
        return cls(
            events=tuple(SecurityEvent.from_dict(e) for e in d.get("events") or ()),
            max_age_days=int(d.get("maxAgeDays", 0)),
            max_bytes=int(d.get("maxBytes", 0)),
            oldest=_opt_str(d.get("oldest")),
        )


# ---------------------------------------------------------------------------
# The firewall, SSH and SSH keys (SecurityHostController)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HostSettings:
    """The firewall and SSH settings, applied in mode ``On`` only.

    A source list holds CIDRs or single addresses, IPv4 and IPv6; empty means any source.
    """

    ssh_allowed: bool = True
    ssh_from: tuple[str, ...] = ()
    #: XVC ports to open (at most 8); empty: closed.
    xvc_ports: tuple[int, ...] = ()
    xvc_from: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "sshAllowed": self.ssh_allowed,
            "sshFrom": list(self.ssh_from),
            "xvcPorts": list(self.xvc_ports),
            "xvcFrom": list(self.xvc_from),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> HostSettings:
        return cls(
            ssh_allowed=bool(d.get("sshAllowed", True)),
            ssh_from=_strs(d.get("sshFrom")),
            xvc_ports=tuple(int(p) for p in d.get("xvcPorts") or ()),
            xvc_from=_strs(d.get("xvcFrom")),
        )


@dataclass(frozen=True, slots=True)
class HostPart:
    """The firewall's or SSH's state and when it was last reconciled."""

    #: ``NotApplied``, ``Applied``, ``Failed`` or ``Unsupported`` (not on a station).
    state: str
    #: The helper's message when it failed.
    problem: str | None
    at: str | None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> HostPart:
        return cls(
            state=str(d.get("state", "")),
            problem=_opt_str(d.get("problem")),
            at=_opt_str(d.get("at")),
        )


@dataclass(frozen=True, slots=True)
class HostSecurity:
    """The firewall and SSH: settings, what is in effect, ports, SSH keys and warnings."""

    settings: HostSettings
    firewall: HostPart
    ssh: HostPart
    #: The TCP ports the firewall opens in ``On``.
    tcp_ports: tuple[int, ...]
    ssh_port: int
    #: How many SSH keys are installed.
    ssh_keys: int
    #: E.g. "SSH accepts nobody until a key is installed"; None for none.
    warnings: tuple[str, ...] | None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> HostSecurity:
        return cls(
            settings=HostSettings.from_dict(_dict(d.get("settings"))),
            firewall=HostPart.from_dict(_dict(d.get("firewall"))),
            ssh=HostPart.from_dict(_dict(d.get("ssh"))),
            tcp_ports=tuple(int(p) for p in d.get("tcpPorts") or ()),
            ssh_port=int(d.get("sshPort", 0)),
            ssh_keys=int(d.get("sshKeys", 0)),
            warnings=_opt_strs(d.get("warnings")),
        )


@dataclass(frozen=True, slots=True)
class SshKey:
    """One line of the ``accordion`` user's authorized_keys."""

    id: str
    fingerprint: str
    #: E.g. ``ssh-ed25519``; ``unreadable`` for a line that can't be read.
    type: str
    bits: int
    comment: str
    has_options: bool

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SshKey:
        return cls(
            id=str(d.get("id", "")),
            fingerprint=str(d.get("fingerprint", "")),
            type=str(d.get("type", "")),
            bits=int(d.get("bits", 0)),
            comment=str(d.get("comment", "")),
            has_options=bool(d.get("hasOptions")),
        )


@dataclass(frozen=True, slots=True)
class SshKeyChange:
    """An SSH key added (:attr:`keys` holds it alone) or the keys left after a removal."""

    keys: tuple[SshKey, ...]
    warnings: tuple[str, ...] | None


# ---------------------------------------------------------------------------
# Extensions and module images (ExtensionsController)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ExtensionFolder:
    """A folder of hw/additional (``""`` for the files at its top) against the signed release."""

    folder: str
    #: ``Signed``, ``Accepted``, ``Unsigned``, ``Changed`` or ``Unverified``.
    state: str
    #: What :meth:`SecurityGroup.accept_extension` takes.
    digest: str
    files: int
    changed_files: tuple[str, ...]
    missing_files: tuple[str, ...]
    extra_files: tuple[str, ...]
    links: tuple[str, ...]
    accepted_by: str | None
    accepted_at: str | None
    referenced_by: tuple[str, ...]
    unreadable: tuple[str, ...]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExtensionFolder:
        return cls(
            folder=str(d.get("folder", "")),
            state=str(d.get("state", "")),
            digest=str(d.get("digest", "")),
            files=int(d.get("files", 0)),
            changed_files=_strs(d.get("changedFiles")),
            missing_files=_strs(d.get("missingFiles")),
            extra_files=_strs(d.get("extraFiles")),
            links=_strs(d.get("links")),
            accepted_by=_opt_str(d.get("acceptedBy")),
            accepted_at=_opt_str(d.get("acceptedAt")),
            referenced_by=_strs(d.get("referencedBy")),
            unreadable=_strs(d.get("unreadable")),
        )


@dataclass(frozen=True, slots=True)
class ExtensionReference:
    """A module entry that loads an assembly; :attr:`folder` None when outside hw/additional."""

    module: str
    assembly_path: str
    source: str
    enabled: bool
    folder: str | None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExtensionReference:
        return cls(
            module=str(d.get("module", "")),
            assembly_path=str(d.get("assemblyPath", "")),
            source=str(d.get("source", "")),
            enabled=bool(d.get("enabled")),
            folder=_opt_str(d.get("folder")),
        )


@dataclass(frozen=True, slots=True)
class ExtensionRelease:
    """The release extensions are checked against, or why it can't be used."""

    version: str | None
    #: Where its manifest was read: a signed copy, the package, or root's install record.
    source: str | None
    signer: str | None
    signed_at: str | None
    problem: str | None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExtensionRelease:
        return cls(
            version=_opt_str(d.get("version")),
            source=_opt_str(d.get("source")),
            signer=_opt_str(d.get("signer")),
            signed_at=_opt_str(d.get("signedAt")),
            problem=_opt_str(d.get("problem")),
        )


@dataclass(frozen=True, slots=True)
class ExtensionsReport:
    """The release, the folders of hw/additional, and the modules loading from outside it."""

    release: ExtensionRelease
    folders: tuple[ExtensionFolder, ...]
    outside: tuple[ExtensionReference, ...]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExtensionsReport:
        return cls(
            release=ExtensionRelease.from_dict(_dict(d.get("release"))),
            folders=tuple(ExtensionFolder.from_dict(f) for f in d.get("folders") or ()),
            outside=tuple(ExtensionReference.from_dict(r) for r in d.get("outside") or ()),
        )


# ---------------------------------------------------------------------------
# The factory reset (FactoryResetController)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FactoryResetPreview:
    """What a factory reset would erase and keep now (counts only, no secrets)."""

    #: What :meth:`SecurityGroup.factory_reset` must be given to confirm.
    host_name: str
    keys: int
    users: int
    certificate: bool
    station_settings: bool
    alias_files: int
    state_machines: int
    captures: int
    calibration_files: int
    unshipped_extensions: tuple[str, ...]
    extension_list_present: bool
    drummer_files: int
    authorized_keys: bool
    erased: tuple[str, ...]
    kept: tuple[str, ...]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FactoryResetPreview:
        return cls(
            host_name=str(d.get("hostName", "")),
            keys=int(d.get("keys", 0)),
            users=int(d.get("users", 0)),
            certificate=bool(d.get("certificate")),
            station_settings=bool(d.get("stationSettings")),
            alias_files=int(d.get("aliasFiles", 0)),
            state_machines=int(d.get("stateMachines", 0)),
            captures=int(d.get("captures", 0)),
            calibration_files=int(d.get("calibrationFiles", 0)),
            unshipped_extensions=_strs(d.get("unshippedExtensions")),
            extension_list_present=bool(d.get("extensionListPresent")),
            drummer_files=int(d.get("drummerFiles", 0)),
            authorized_keys=bool(d.get("authorizedKeys")),
            erased=_strs(d.get("erased")),
            kept=_strs(d.get("kept")),
        )


@dataclass(frozen=True, slots=True)
class FactoryResetStarted:
    """The reset's systemd unit and what happens now."""

    unit: str
    message: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FactoryResetStarted:
        return cls(unit=str(d.get("unit", "")), message=str(d.get("message", "")))


@dataclass(frozen=True, slots=True)
class FactoryResetRecord:
    """The last factory reset: when, who and from where, and what it erased and kept."""

    time: str
    by: str
    client: str | None
    version: str | None
    calibration_erased: bool
    erased: tuple[str, ...]
    kept: tuple[str, ...]
    warnings: tuple[str, ...]
    rebooted: bool

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FactoryResetRecord:
        return cls(
            time=str(d.get("time", "")),
            by=str(d.get("by", "")),
            client=_opt_str(d.get("client")),
            version=_opt_str(d.get("version")),
            calibration_erased=bool(d.get("calibrationErased")),
            erased=_strs(d.get("erased")),
            kept=_strs(d.get("kept")),
            warnings=_strs(d.get("warnings")),
            rebooted=bool(d.get("rebooted")),
        )


def _q(value: str) -> str:
    return quote(value, safe="")


class SecurityGroup(ApiGroupBase):
    """The station's security: logins, users, keys, the certificate, the event log, the
    firewall and SSH, extensions and the factory reset (firmware 7.1.0).

    A person logs in, and the client sends the token from then on::

        client = AccordionQ2Client("https://station-12:5001", cert_sha256="3F:A2:...")
        login = client.security.login("anna", getpass.getpass())
        ...
        client.security.renew()   # before login.expires_in runs out; up to 12 h
        client.security.logout()

    A station before 7.1.0 answers these calls 404 (401 or 403 in mode ``On``).
    """

    # ----- the mode, keys and certificate -----

    def get_state(self) -> SecurityState:
        """The mode, the keys and users (never secrets), and the clients blocked now."""
        return SecurityState.from_dict(self._obj(self._get_json("api/security")))

    def set_mode(self, mode: str) -> SecurityState:
        """Set ``Off``, ``Report`` or ``On``; the answer's ``warnings`` say what to check.

        ``On`` needs an admin key or login on this client, HTTPS on the station, and this
        request over HTTPS or on the station.
        """
        return SecurityState.from_dict(
            self._obj(self._put_json("api/security/mode", {"mode": str(mode)}))
        )

    def create_key(self, name: str, role: str) -> CreatedApiKey:
        """Make an API key; :attr:`CreatedApiKey.key` is shown this once only. Over HTTPS."""
        return CreatedApiKey.from_dict(
            self._obj(self._post_json("api/security/keys", {"name": name, "role": str(role)}))
        )

    def revoke_key(self, key_id: str) -> None:
        """Revoke an API key by its id: it stops working at once."""
        self._delete(f"api/security/keys/{_q(key_id)}")

    def get_certificate(self) -> CertificateInfo:
        """The certificate HTTPS serves, its fingerprint, and the station's own self-signed one."""
        return CertificateInfo.from_dict(self._obj(self._get_json("api/security/certificate")))

    def install_certificate(
        self,
        certificate_pem: str | None = None,
        private_key_pem: str | None = None,
        *,
        pfx: bytes | None = None,
        password: str | None = None,
    ) -> CertificateInfo:
        """Install the site's own certificate: PEM (leaf and intermediates, and the key) or
        PKCS#12 (*pfx*), *password* for an encrypted key or the .pfx.

        It serves from the next handshake and open TLS connections are closed, so pinned
        clients need the new fingerprint (:attr:`CertificateInfo.sha256`). Over HTTPS or on
        the station only: the body carries the private key.
        """
        self._session.require_https_or_loopback("Installing a certificate")
        body: dict[str, Any] = {}
        if certificate_pem is not None:
            body["certificatePem"] = certificate_pem
        if private_key_pem is not None:
            body["privateKeyPem"] = private_key_pem
        if pfx is not None:
            body["pfxBase64"] = base64.b64encode(pfx).decode("ascii")
        if password is not None:
            body["password"] = password
        return CertificateInfo.from_dict(
            self._obj(self._put_json("api/security/certificate", body))
        )

    def remove_certificate(self) -> CertificateInfo:
        """Remove the site certificate: the station's self-signed one serves again."""
        raw = self._request("DELETE", "api/security/certificate")
        return CertificateInfo.from_dict(self._obj(json.loads(raw)))

    def regenerate_certificate(self, extra_names: list[str] | None = None) -> CertificateInfo:
        """A new self-signed certificate, optionally with extra DNS names or IP addresses.

        A new fingerprint: every pinned client must be given it. An installed site
        certificate keeps serving.
        """
        body = None if extra_names is None else {"extraNames": list(extra_names)}
        return CertificateInfo.from_dict(
            self._obj(self._post_json("api/security/certificate/regenerate", body))
        )

    # ----- logins -----

    @property
    def has_token(self) -> bool:
        """Whether this client sends a login token (the token itself is never exposed)."""
        return self._session.has_bearer_token

    def use_token(self, token: str | None) -> None:
        """Send *token* (e.g. a :attr:`LoginResponse.token` kept elsewhere) as
        ``Authorization: Bearer`` from now on; None stops sending one."""
        self._session.set_bearer_token(token)

    def login(self, name: str, password: str, *, use: bool = True) -> LoginResponse:
        """Log in with a user name and password; with *use* (default) this client sends the
        token from now on.

        Over HTTPS or on the station only (``ValueError`` before sending otherwise). A wrong
        name or password raises :class:`AccordionQ2SecurityError` (401, reason
        ``LOGIN_REFUSED``); too many raise :class:`AccordionQ2ThrottledError` (429). If this
        client also has an API key, the station goes by the key.
        """
        self._session.require_https_or_loopback("Logging in")
        result = self._login("POST", "api/security/login", {"name": name, "password": password})
        if use:
            self._session.set_bearer_token(result.token)
        return result

    def renew(self) -> LoginResponse:
        """A new token for this client's login, until 12 hours after it; this client sends it.

        401 (``LOGIN_REFUSED``) once the login can't be renewed any more: log in again.
        """
        if not self._session.has_bearer_token:
            raise RuntimeError("This client has no login token to renew; log in first")
        result = self._login("POST", "api/security/token/renew", None)
        self._session.set_bearer_token(result.token)
        return result

    def logout(self) -> None:
        """Log out: this token, and every token renewed from the same login, stops working.

        The client stops sending the token even when the station can't be reached.
        """
        if not self._session.has_bearer_token:
            return
        try:
            self._post("api/security/logout")
        finally:
            self._session.set_bearer_token(None)

    def me(self) -> MeInfo:
        """Who this client is (a key, a login, or None), the mode, and whether it is claimed."""
        return MeInfo.from_dict(self._obj(self._get_json("api/security/me")))

    def claim(
        self, setup_code: str, password: str, name: str | None = None, *, use: bool = True
    ) -> LoginResponse:
        """Claim an unclaimed station: its first admin user (*name*, default ``admin``) with
        the setup code read over SSH (``cat ~/webapi/config/setup-code``).

        From the station's own network segment, over HTTPS or on the station. The new admin is
        logged in; with *use* this client sends the token.
        """
        self._session.require_https_or_loopback("Claiming a station")
        body: dict[str, Any] = {"setupCode": setup_code, "password": password}
        if name is not None:
            body["name"] = name
        result = self._login("POST", "api/security/claim", body)
        if use:
            self._session.set_bearer_token(result.token)
        return result

    def change_password(self, current_password: str, new_password: str) -> LoginResponse:
        """Change this login's own password (12 to 128 characters). The user's other logins
        end; the answer is a new token for this one, which this client sends from now on.
        """
        self._session.require_https_or_loopback("Changing a password")
        result = self._login(
            "PUT",
            "api/security/password",
            {"currentPassword": current_password, "newPassword": new_password},
        )
        self._session.set_bearer_token(result.token)
        return result

    # ----- users -----

    def get_users(self) -> list[UserInfo]:
        """The users (never their passwords)."""
        return [UserInfo.from_dict(u) for u in self._list(self._get_json("api/security/users"))]

    def create_user(self, name: str, role: str, password: str) -> UserInfo:
        """Make a user (over HTTPS or on the station). 409 for a first admin of an unclaimed
        station, which only the claim, an admin key in ``On`` or the SSH tool makes.
        """
        self._session.require_https_or_loopback("Making a user")
        body = {"name": name, "role": str(role), "password": password}
        return UserInfo.from_dict(self._obj(self._post_json("api/security/users", body)))

    def set_user_password(self, user_id: str, password: str) -> None:
        """Set a user's password (over HTTPS or on the station): their logins end everywhere."""
        self._session.require_https_or_loopback("Setting a password")
        self._request(
            "PUT", f"api/security/users/{_q(user_id)}/password", body={"password": password}
        )

    def set_user_role(self, user_id: str, role: str) -> UserInfo:
        """Set a user's role; refused (400) when it would leave mode ``On`` without an admin."""
        return UserInfo.from_dict(
            self._obj(self._put_json(f"api/security/users/{_q(user_id)}/role", {"role": str(role)}))
        )

    def remove_user(self, user_id: str) -> None:
        """Remove a user: their logins end at once."""
        self._delete(f"api/security/users/{_q(user_id)}")

    # ----- the security event log -----

    def get_events(
        self,
        tail: int = 200,
        since: str | datetime | None = None,
        kinds: list[str] | None = None,
    ) -> SecurityEvents:
        """The newest security events first: at most *tail* (1 to 5000), optionally since a
        time (ISO 8601 or an aware ``datetime``) and of some *kinds* (e.g. ``LoginFailed``).
        """
        query: list[tuple[str, str]] = [("tail", str(tail))]
        if since is not None:
            query.append(("since", since.isoformat() if isinstance(since, datetime) else since))
        query.extend(("kind", str(k)) for k in kinds or ())
        return SecurityEvents.from_dict(
            self._obj(self._get_json(f"api/security/events?{urlencode(query)}"))
        )

    # ----- the firewall, SSH and SSH keys -----

    def get_host(self) -> HostSecurity:
        """The firewall and SSH settings, whether they are in effect, ports and warnings."""
        return HostSecurity.from_dict(self._obj(self._get_json("api/security/host")))

    def set_host(self, settings: HostSettings) -> HostSecurity:
        """Set the firewall and SSH settings: stored in every mode, applied at once in ``On``."""
        return HostSecurity.from_dict(
            self._obj(self._put_json("api/security/host", settings.to_dict()))
        )

    def get_ssh_keys(self) -> list[SshKey]:
        """The ``accordion`` user's SSH keys (authorized_keys)."""
        return [SshKey.from_dict(k) for k in self._list(self._get_json("api/security/ssh-keys"))]

    def add_ssh_key(self, line: str) -> SshKeyChange:
        """Install an SSH key for the ``accordion`` user: one authorized_keys line without
        options (Ed25519, ECDSA, the FIDO kinds, or RSA of 3072 bits or more).

        :attr:`SshKeyChange.keys` holds the new key alone. In ``On`` that is how SSH lets
        anyone in, and the key's holder gets a shell on the station.
        """
        d = self._obj(self._post_json("api/security/ssh-keys", {"key": line}))
        return SshKeyChange((SshKey.from_dict(_dict(d.get("info"))),), _opt_strs(d.get("warnings")))

    def remove_ssh_key(self, key_id: str) -> SshKeyChange:
        """Remove an SSH key by its id; the keys left, and a warning when that was the last
        one in ``On``."""
        raw = self._request("DELETE", f"api/security/ssh-keys/{_q(key_id)}")
        d = self._obj(json.loads(raw))
        return SshKeyChange(
            tuple(SshKey.from_dict(k) for k in d.get("keys") or ()), _opt_strs(d.get("warnings"))
        )

    # ----- extensions and module images -----

    def get_extensions(self) -> ExtensionsReport:
        """Every folder of hw/additional against the installed release's signed manifest."""
        return ExtensionsReport.from_dict(self._obj(self._get_json("api/security/extensions")))

    def accept_extension(self, folder: str, digest: str) -> tuple[ExtensionFolder, list[str]]:
        """Accept a folder's content as it is now (``""`` for the top of hw/additional), by the
        digest read from :meth:`get_extensions`: it then loads in ``On`` while it stays the
        same. 409 when it changed since. Returns the folder and the warnings.
        """
        d = self._obj(
            self._post_json("api/security/extensions/accept", {"folder": folder, "digest": digest})
        )
        return ExtensionFolder.from_dict(_dict(d.get("folder"))), list(_strs(d.get("warnings")))

    def withdraw_extension(self, folder: str) -> None:
        """Withdraw a folder's acceptance (404 when it isn't accepted)."""
        self._delete(f"api/security/extensions/accept?folder={_q(folder)}")

    def set_extension_uploads(self, minutes: int) -> tuple[str | None, list[str]]:
        """Open the file API's changes to the extensions folder in ``On`` for 1 to 1440
        minutes, or close them (0). Returns until when (ISO 8601, None: closed) and warnings.
        """
        d = self._obj(self._put_json("api/security/extension-uploads", {"minutes": int(minutes)}))
        return _opt_str(d.get("extensionUploadsUntil")), list(_strs(d.get("warnings")))

    def set_module_image_role(self, role: str) -> tuple[str, list[str]]:
        """The role module images (FPGA images, Drummer packages) need in ``On``: ``Admin``
        (the default) or ``Operator``. Returns the role set and warnings.
        """
        d = self._obj(self._put_json("api/security/module-images", {"role": str(role)}))
        return str(d.get("moduleImageRole", "")), list(_strs(d.get("warnings")))

    # ----- the factory reset -----

    def factory_reset_preview(self) -> FactoryResetPreview:
        """What a factory reset would erase and keep now."""
        return FactoryResetPreview.from_dict(
            self._obj(self._get_json("api/security/factory-reset/preview"))
        )

    def factory_reset(self, confirm: str, erase_calibration: bool = False) -> FactoryResetStarted:
        """Reset the station to its production state; *confirm* is its host name (see
        :meth:`factory_reset_preview`).

        The WebApi stops, the station erases its data and reboots, and comes back in mode
        ``Off``, unclaimed, on DHCP, with a new certificate. 400 for a wrong name, 409 while a
        firmware update runs or the lease is held, 501 off a station.
        """
        body = {"confirm": confirm, "eraseCalibration": bool(erase_calibration)}
        return FactoryResetStarted.from_dict(
            self._obj(self._post_json("api/security/factory-reset", body))
        )

    def last_factory_reset(self) -> FactoryResetRecord | None:
        """The last factory reset's record; None when the station has none (404)."""
        try:
            d = self._get_json("api/security/factory-reset")
        except AccordionQ2ApiError as error:
            if error.status_code == 404:
                return None
            raise
        return FactoryResetRecord.from_dict(self._obj(d))

    # ----- helpers -----

    def _login(self, method: str, path: str, body: object) -> LoginResponse:
        return LoginResponse.from_dict(
            self._obj(json.loads(self._request(method, path, body=body)))
        )

    @staticmethod
    def _obj(value: object) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise AccordionQ2ApiError(200, "The station's answer isn't a JSON object")
        return value

    @staticmethod
    def _list(value: object) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            raise AccordionQ2ApiError(200, "The station's answer isn't a JSON array")
        return [v for v in value if isinstance(v, dict)]

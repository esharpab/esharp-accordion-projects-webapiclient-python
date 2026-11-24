"""The station's security calls (firmware 7.1.0; FW7_PLAN CLI-05 follow-up).

Everything under ``/api/security`` of the WebApi's six security controllers: the mode,
API keys and the TLS certificate (``SecurityController``), logins, the claim and the users
(``AccountsController``), the security event log (``SecurityEventsController``), the firewall
(``SecurityHostController``), extensions and module
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
import hashlib
import json
import os
import secrets
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from ._base import API_KEY_HEADER, ApiGroupBase, _hide
from .exceptions import AccordionQ2ApiError, AccordionQ2SecurityError


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
    #: A change's warnings; from :meth:`SecurityGroup.get_certificate` (firmware 7.1.0): an
    #: expired certificate, or one that expires within 30 days, with the date.
    warnings: tuple[str, ...] | None = None
    #: The names :meth:`SecurityGroup.request_certificate` uses when given none (firmware
    #: 7.1.0); None from older firmware.
    default_request_names: tuple[str, ...] | None = None

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
            default_request_names=_opt_strs(d.get("defaultRequestNames")),
        )


@dataclass(frozen=True, slots=True)
class CertificateRequest:
    """A certificate request made on the station (firmware 7.1.0): never its key.

    :attr:`csr_pem` is what the site's CA signs; the key stays on the station until the
    signed certificate is installed with :meth:`SecurityGroup.install_signed_certificate`.
    """

    #: DNS names and IP addresses; the first is the subject's common name.
    names: tuple[str, ...]
    created: str
    created_by: str | None
    csr_pem: str
    #: SHA-256 over the request's public key (SubjectPublicKeyInfo), hex pairs with colons.
    public_key_sha256: str
    #: When made: whether it replaced a pending request, whose key is then gone.
    replaced: bool | None = None
    warnings: tuple[str, ...] | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CertificateRequest:
        replaced = d.get("replaced")
        return cls(
            names=_strs(d.get("names")),
            created=str(d.get("created", "")),
            created_by=_opt_str(d.get("createdBy")),
            csr_pem=str(d.get("csrPem", "")),
            public_key_sha256=str(d.get("publicKeySha256", "")),
            replaced=replaced if isinstance(replaced, bool) else None,
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
# The firewall (SecurityHostController)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HostSettings:
    """The firewall settings, applied in mode ``On`` only.

    A source list holds CIDRs or single addresses, IPv4 and IPv6; empty means any source. In
    ``On`` the firewall drops connections forwarded to containers from outside the station.
    """

    #: XVC ports to open (at most 8); empty: closed.
    xvc_ports: tuple[int, ...] = ()
    xvc_from: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "xvcPorts": list(self.xvc_ports),
            "xvcFrom": list(self.xvc_from),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> HostSettings:
        return cls(
            xvc_ports=tuple(int(p) for p in d.get("xvcPorts") or ()),
            xvc_from=_strs(d.get("xvcFrom")),
        )


@dataclass(frozen=True, slots=True)
class HostPart:
    """The firewall's or the service access's state and when it was last reconciled."""

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
    """The firewall: settings, what is in effect, ports and warnings."""

    settings: HostSettings
    firewall: HostPart
    #: E-Sharp's service access (SSH), keys only in ``On``.
    ssh: HostPart
    #: The TCP ports the firewall opens in ``On``.
    tcp_ports: tuple[int, ...]
    #: The service access's port.
    ssh_port: int
    #: E.g. "The firewall isn't loaded: ..."; None for none.
    warnings: tuple[str, ...] | None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> HostSecurity:
        return cls(
            settings=HostSettings.from_dict(_dict(d.get("settings"))),
            firewall=HostPart.from_dict(_dict(d.get("firewall"))),
            ssh=HostPart.from_dict(_dict(d.get("ssh"))),
            tcp_ports=tuple(int(p) for p in d.get("tcpPorts") or ()),
            ssh_port=int(d.get("sshPort", 0)),
            warnings=_opt_strs(d.get("warnings")),
        )


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


@dataclass(frozen=True, slots=True)
class RecoveryWindow:
    """Whether a recovery drive for the station is in it (firmware 7.1.0).

    ``window`` is ``open`` while an admin password can be set (until 24 hours after the drive
    was made, until the drive is taken out, one reset per insertion), else ``closed``.
    """

    window: str
    #: When it closes at the latest (ISO 8601); None while closed.
    until: str | None
    #: Whether the station's USB ports are off: the drive then needs a restart of the station.
    usb_ports_off: bool
    hint: str
    steps: tuple[str, ...]
    #: The station's name (its serial number), which a drive must carry
    #: (:meth:`SecurityGroup.make_recovery_drive`).
    station: str | None = None
    #: When the drive in the station was made (ISO 8601); None without one.
    created: str | None = None
    #: Why the window is closed: ``None`` (open), ``NoDrive``, ``Expired``, ``DriveGone``, ``Used``,
    #: ``Invalid``, ``Outdated`` (made by an earlier firmware).
    why: str | None = None
    #: The station's clock (ISO 8601, UTC) when it answered: a drive's time is judged by it (a time
    #: ahead of it is accepted). When it is more than an hour ahead of this computer's, pass it to
    #: :meth:`SecurityGroup.make_recovery_drive` as *now*.
    now: str | None = None

    @property
    def is_open(self) -> bool:
        return self.window.lower() == "open"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RecoveryWindow:
        return cls(
            window=str(d.get("window", "closed")),
            until=_opt_str(d.get("until")),
            usb_ports_off=bool(d.get("usbPortsOff")),
            hint=str(d.get("hint", "")),
            steps=_strs(d.get("steps")),
            station=_opt_str(d.get("station")),
            created=_opt_str(d.get("created")),
            why=_opt_str(d.get("why")),
            now=_opt_str(d.get("now")),
        )


@dataclass(frozen=True, slots=True)
class RecoveryReset:
    """What a reset with the recovery drive did: the user, whether it was made, what to do now."""

    user: UserInfo
    created: bool
    message: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RecoveryReset:
        user = d.get("user")
        return cls(
            user=UserInfo.from_dict(user if isinstance(user, dict) else {}),
            created=bool(d.get("created")),
            message=str(d.get("message", "")),
        )


#: The recovery drive's file, in the top folder of a FAT32 or exFAT USB drive.
RECOVERY_DRIVE_FILE = "accordion-recovery.json"
_RECOVERY_KIND = "accordion-recovery"
_RECOVERY_KEY_KIND = "accordion-recovery-key"
#: The recovery drive's secret: 32 random bytes, sent as 64 hex digits.
RECOVERY_SECRET_BYTES = 32


def recovery_drive_hash(secret: bytes, station: str, created: str) -> str:
    """The recovery drive's hash: lower-case hex SHA-256 over the secret's bytes, a 0x00 byte,
    the station's name in upper case (UTF-8), a 0x00 byte and *created* as the file carries it
    (UTF-8). The station, the Web UI and the .NET client compute the same."""
    data = (
        secret
        + b"\x00"
        + station.strip().upper().encode("utf-8")
        + b"\x00"
        + created.encode("utf-8")
    )
    return hashlib.sha256(data).hexdigest()


def format_recovery_created(at: datetime | str) -> str:
    """A time as the recovery drive's file carries it: ``YYYY-MM-DDTHH:MM:SSZ`` (UTC). A string is
    read as ISO 8601 (such as :attr:`RecoveryWindow.now`)."""
    if isinstance(at, str):
        at = datetime.fromisoformat(at)
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True, slots=True)
class RecoveryDriveKey:
    """What the client keeps of a recovery drive it made: the station, when it was made and the
    secret (64 hex digits). The secret is the drive's password: keep the key where only you can
    read it. Its ``repr()`` doesn't show the secret."""

    station: str
    created: str
    secret: str = field(repr=False)

    def to_json(self) -> str:
        """The key as JSON (kind, station, created, secret), as the .NET client writes it too."""
        return json.dumps(
            {
                "kind": _RECOVERY_KEY_KIND,
                "station": self.station,
                "created": self.created,
                "secret": self.secret,
            },
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, text: str) -> RecoveryDriveKey:
        """A key from :meth:`to_json`; ``ValueError`` for anything else."""
        try:
            d = json.loads(text)
        except json.JSONDecodeError as error:
            raise ValueError(f"Not a recovery drive key: {error.msg}") from None
        if (
            not isinstance(d, dict)
            or d.get("kind") != _RECOVERY_KEY_KIND
            or not all(isinstance(d.get(k), str) for k in ("station", "created", "secret"))
        ):
            raise ValueError("Not a recovery drive key")
        secret = d["secret"]
        if len(secret) != 2 * RECOVERY_SECRET_BYTES or any(
            c not in "0123456789abcdefABCDEF" for c in secret
        ):
            raise ValueError("The recovery drive key's secret isn't 64 hex digits")
        return cls(station=d["station"], created=d["created"], secret=secret.lower())

    def save(self, path: str | Path) -> None:
        """Write the key to *path* (the caller chooses where: it holds the secret).

        On Linux and macOS the file is readable by its owner only (0600), also when it was there
        already; on Windows it gets the folder's permissions, so choose a folder only you can read.
        """
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0)
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as file:
            if sys.platform != "win32":
                os.fchmod(file.fileno(), 0o600)  # a file that was there keeps its mode otherwise
            file.write(self.to_json() + "\n")

    @classmethod
    def load(cls, path: str | Path) -> RecoveryDriveKey:
        """Read a key :meth:`save` wrote."""
        return cls.from_json(Path(path).read_text(encoding="utf-8"))


def make_recovery_drive_file(
    station: str, now: datetime | str | None = None
) -> tuple[bytes, RecoveryDriveKey]:
    """A new recovery drive for *station* made at *now* (default: this computer's clock): the
    bytes of ``accordion-recovery.json`` (kind, station, created, hash; never the secret) and the
    key to keep."""
    if not station or not station.strip():
        raise ValueError("The station's name is needed")
    raw = secrets.token_bytes(RECOVERY_SECRET_BYTES)
    created = format_recovery_created(now or datetime.now(UTC))
    body = {
        "kind": _RECOVERY_KIND,
        "station": station.strip(),
        "created": created,
        "hash": recovery_drive_hash(raw, station, created),
    }
    key = RecoveryDriveKey(station=station.strip().upper(), created=created, secret=raw.hex())
    return (json.dumps(body, separators=(",", ":")) + "\n").encode("utf-8"), key


def _q(value: str) -> str:
    return quote(value, safe="")


# The headers of a call that must go by the login token: no X-Api-Key, because the station goes
# by the key when both are sent, and would then not renew, log out or change the login's password
# (CLI-05 follow-up). A None value drops the header (HttpSession.request_headers).
_TOKEN_ONLY: dict[str, str] = {API_KEY_HEADER: None}  # type: ignore[dict-item]

# The headers of a call that goes without any credential (the recovery drive's reset): neither the
# key nor the login token rides on it.
_NO_CREDENTIALS: dict[str, str] = {API_KEY_HEADER: None, "Authorization": None}  # type: ignore[dict-item]


class SecurityGroup(ApiGroupBase):
    """The station's security: logins, users, keys, the certificate, the event log, the
    firewall, extensions and the factory reset (firmware 7.1.0).

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
        # Hidden from a traceback's local variables, like the API key (CLI-05 follow-up)
        private_key_pem, password = _hide(private_key_pem), _hide(password)
        self._session.require_https_or_loopback("Installing a certificate")
        body: dict[str, Any] = {}
        if certificate_pem is not None:
            body["certificatePem"] = certificate_pem
        if private_key_pem is not None:
            body["privateKeyPem"] = private_key_pem
        if pfx is not None:
            body["pfxBase64"] = _hide(base64.b64encode(pfx).decode("ascii"))
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

    # ----- the certificate request (firmware 7.1.0, FW7 CERT-01) -----

    def request_certificate(self, names: list[str] | None = None) -> CertificateRequest:
        """Make a certificate request on the station: a new key pair whose private key never
        leaves it, and the CSR (:attr:`CertificateRequest.csr_pem`) for the site's CA.

        *names* are DNS names or IP addresses, the first the subject's common name (at most
        32, no wildcards); None: the station's default names
        (:attr:`CertificateInfo.default_request_names`). It replaces a pending request, whose
        key is then deleted. Over HTTPS or on the station (400 over plain HTTP from another
        host: no secret is sent, but the station keeps one rule for certificate changes).
        """
        body = None if names is None else {"names": list(names)}
        return CertificateRequest.from_dict(
            self._obj(self._post_json("api/security/certificate/request", body))
        )

    def get_certificate_request(self) -> CertificateRequest | None:
        """The pending certificate request (never its key); None when none is pending (404)."""
        try:
            d = self._get_json("api/security/certificate/request")
        except AccordionQ2ApiError as error:
            if error.status_code == 404:
                return None
            raise
        return CertificateRequest.from_dict(self._obj(d))

    def delete_certificate_request(self) -> None:
        """Discard the pending request: its key is deleted, so a certificate signed for it no
        longer installs (404 when none is pending)."""
        self._delete("api/security/certificate/request")

    def install_signed_certificate(self, certificate_pem: str) -> CertificateInfo:
        """Install the certificate the CA signed for the pending request: the leaf and its
        intermediates as PEM, no key (the key is the request's, on the station).

        It serves as the site certificate (the same checks and warnings as
        :meth:`install_certificate`; open TLS connections are closed) and the request is used
        up. 400 when no request is pending or the certificate's public key isn't the
        request's, and over plain HTTP from another host.
        """
        if not certificate_pem or not certificate_pem.strip():
            raise ValueError("The signed certificate (PEM) is empty")
        return CertificateInfo.from_dict(
            self._obj(
                self._put_json("api/security/certificate", {"certificatePem": certificate_pem})
            )
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
        client also has an API key, the station goes by the key for every call but
        :meth:`renew`, :meth:`logout` and :meth:`change_password`, which send only the token.
        """
        password = _hide(password)
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
        result = self._login("POST", "api/security/token/renew", None, token_only=True)
        self._session.set_bearer_token(result.token)
        return result

    def logout(self) -> None:
        """Log out: this token, and every token renewed from the same login, stops working.

        The client stops sending the token even when the station can't be reached. A token
        the station no longer accepts (expired, already logged out) is logged out already:
        no error then, so a ``finally: logout()`` after a long idle doesn't hide the script's
        own exception. The call goes without the API key, so the station ends the login even
        when this client has a key too.
        """
        if not self._session.has_bearer_token:
            return
        try:
            self._request("POST", "api/security/logout", headers=dict(_TOKEN_ONLY))
        except AccordionQ2SecurityError as e:
            # In On an expired token is refused (401) before the logout runs; in Off and
            # Report the same call answers 204. Either way the login is over.
            if e.status_code != 401:
                raise
        finally:
            self._session.set_bearer_token(None)

    def me(self) -> MeInfo:
        """Who this client is (a key, a login, or None), the mode, and whether it is claimed."""
        return MeInfo.from_dict(self._obj(self._get_json("api/security/me")))

    def claim(self, password: str, name: str | None = None, *, use: bool = True) -> LoginResponse:
        """Claim an unclaimed station in security mode ``Off`` or ``Report``: its first admin
        user (*name*, default ``admin``) with *password*, over HTTPS. No setup code (firmware
        7.1.0).

        The new admin is logged in; with *use* this client sends the token. 409 when the
        station is claimed already, and in mode ``On``: an unclaimed station is claimed there
        with the recovery drive (:meth:`recovery_reset_admin` while the drive is in it).
        """
        password = _hide(password)
        self._session.require_https_or_loopback("Claiming a station")
        body: dict[str, Any] = {"password": password}
        if name is not None:
            body["name"] = name
        result = self._login("POST", "api/security/claim", body)
        if use:
            self._session.set_bearer_token(result.token)
        return result

    def change_password(self, current_password: str, new_password: str) -> LoginResponse:
        """Change this login's own password (12 to 128 characters). The user's other logins
        end; the answer is a new token for this one, which this client sends from now on.
        It goes without the API key, which the station would go by instead of the login.
        """
        current_password, new_password = _hide(current_password), _hide(new_password)
        self._session.require_https_or_loopback("Changing a password")
        result = self._login(
            "PUT",
            "api/security/password",
            {"currentPassword": current_password, "newPassword": new_password},
            token_only=True,
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
        password = _hide(password)
        self._session.require_https_or_loopback("Making a user")
        body = {"name": name, "role": str(role), "password": password}
        return UserInfo.from_dict(self._obj(self._post_json("api/security/users", body)))

    def set_user_password(self, user_id: str, password: str) -> None:
        """Set a user's password (over HTTPS or on the station): their logins end everywhere."""
        password = _hide(password)
        self._session.require_https_or_loopback("Setting a password")
        self._request(
            "PUT", f"api/security/users/{_q(user_id)}/password", body={"password": password}
        )

    def sign_out_all(self) -> None:
        """Sign everyone out (Admin): every login token on the station ends at once, also
        after a restart, this client's own too (it stops sending it). API keys keep working.
        """
        self._request("POST", "api/security/sessions/sign-out-all")
        self._session.set_bearer_token(None)

    def set_user_role(self, user_id: str, role: str) -> UserInfo:
        """Set a user's role; 409 for the last admin user while the station has no admin
        API key (every mode)."""
        return UserInfo.from_dict(
            self._obj(self._put_json(f"api/security/users/{_q(user_id)}/role", {"role": str(role)}))
        )

    def remove_user(self, user_id: str) -> None:
        """Remove a user: their logins end at once. 409 for the last admin user while the
        station has no admin API key (every mode)."""
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

    # ----- the firewall -----

    def get_host(self) -> HostSecurity:
        """The firewall settings (the XVC ports), whether they are in effect, ports and warnings."""
        return HostSecurity.from_dict(self._obj(self._get_json("api/security/host")))

    def set_host(self, settings: HostSettings) -> HostSecurity:
        """Set the firewall settings (the XVC ports): stored in every mode, applied in ``On``."""
        return HostSecurity.from_dict(
            self._obj(self._put_json("api/security/host", settings.to_dict()))
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

    # ----- the recovery drive (firmware 7.1.0) -----

    def get_recovery(self) -> RecoveryWindow | None:
        """Whether a recovery drive for this station is in it (anyone, every mode); None on a
        station before 7.1.0 (404)."""
        try:
            d = self._get_json("api/security/recovery")
        except AccordionQ2ApiError as error:
            if error.status_code == 404:
                return None
            raise
        return RecoveryWindow.from_dict(self._obj(d))

    @property
    def recovery_key(self) -> RecoveryDriveKey | None:
        """The key of the recovery drive this client made (:meth:`make_recovery_drive`) or
        loaded (:meth:`load_recovery_key`); :meth:`recovery_reset_admin` sends its secret."""
        return getattr(self, "_recovery_key", None)

    @recovery_key.setter
    def recovery_key(self, key: RecoveryDriveKey | None) -> None:
        self._recovery_key = key

    def make_recovery_drive(self, station: str, now: datetime | str | None = None) -> bytes:
        """Make a recovery drive for *station* here, without the station.

        *station* is the station's name (its serial number; :meth:`get_recovery` answers it as
        ``station``). Returns the bytes of ``accordion-recovery.json``: save them under that name
        in the top folder of a FAT32 or exFAT USB drive. The drive's random secret stays in
        :attr:`recovery_key` (save it with :meth:`save_recovery_key` to reset from another
        process); the file holds a hash, never the secret. A drive opens the station's recovery
        window until 24 hours after it was made, on the station's clock (this computer's time may
        be ahead of the station's by any amount). When the station's clock is more than an hour
        ahead of this computer's, pass it, :attr:`RecoveryWindow.now`, as *now*.
        """
        data, key = make_recovery_drive_file(station, now)
        self.recovery_key = key
        return data

    def save_recovery_key(self, path: str | Path) -> None:
        """Write :attr:`recovery_key` to *path*, which the caller chooses: it holds the secret."""
        if self.recovery_key is None:
            raise ValueError("This client hasn't made a recovery drive (make_recovery_drive)")
        self.recovery_key.save(path)

    def load_recovery_key(self, path: str | Path) -> RecoveryDriveKey:
        """Read a key :meth:`save_recovery_key` wrote into :attr:`recovery_key`."""
        self.recovery_key = RecoveryDriveKey.load(path)
        return self.recovery_key

    def recovery_reset_admin(self, password: str, user: str | None = None) -> RecoveryReset:
        """Set an admin's password while a recovery drive for this station is in it (anyone,
        over HTTPS or on the station). Sent without the key or the login token, with the secret
        of :attr:`recovery_key`: only the client that made the drive can use it.

        *user* (default ``admin``) gets the password; it is made as Admin if missing, made
        Admin if not, and its logins end. The mode, the keys and the other users stay. One
        reset per insertion of the drive. 409 when no recovery drive is in the station, 403 when
        the drive was made by another client or browser (counted like a wrong password), 400 for
        a password the station refuses. ``ValueError`` without a :attr:`recovery_key` (nothing
        is sent). This client doesn't log in: call :meth:`login`.
        """
        password = _hide(password)
        self._session.require_https_or_loopback("A password reset with the recovery drive")
        key = self.recovery_key
        if key is None:
            raise ValueError(
                "This client has no recovery drive key: make the drive with make_recovery_drive, "
                "or load its key with load_recovery_key"
            )
        body: dict[str, Any] = {"password": password, "secret": _hide(key.secret)}
        if user is not None:
            body["user"] = user
        return RecoveryReset.from_dict(
            self._obj(
                json.loads(
                    self._request(
                        "POST",
                        "api/security/recovery/reset-admin",
                        body=body,
                        headers=dict(_NO_CREDENTIALS),
                    )
                )
            )
        )

    # ----- helpers -----

    def _login(
        self, method: str, path: str, body: object, *, token_only: bool = False
    ) -> LoginResponse:
        headers = dict(_TOKEN_ONLY) if token_only else None
        return LoginResponse.from_dict(
            self._obj(json.loads(self._request(method, path, body=body, headers=headers)))
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

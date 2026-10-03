"""Firmware updates through the WebApi (accordionq2 contract section 12)."""

from __future__ import annotations

import http.client
import json
import time
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any
from urllib.parse import quote

from ._base import ApiGroupBase
from .exceptions import AccordionQ2ApiError

#: The states an update ends in.
FINAL_STATES = frozenset({"idle", "succeeded", "failed", "rolledBack", "unknown"})


@dataclass(frozen=True, slots=True)
class FirmwareSource:
    """Where the station looks for releases."""

    #: ``url`` or ``folder`` (a folder on the Pi).
    kind: str
    location: str
    is_default: bool

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FirmwareSource:
        return cls(d.get("kind", ""), d.get("location", ""), bool(d.get("isDefault")))


@dataclass(frozen=True, slots=True)
class FirmwareUpdateStatus:
    """How the current or last update stands."""

    #: ``idle``, ``downloading``, ``staging``, ``installing``, then ``succeeded``, ``failed`` or
    #: ``rolledBack``.
    state: str
    version: str | None = None
    message: str | None = None
    #: While downloading.
    bytes: int | None = None
    total_bytes: int | None = None
    #: ISO 8601.
    time: str | None = None

    @property
    def finished(self) -> bool:
        """True once the update has ended, however it went."""
        return self.state in FINAL_STATES

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FirmwareUpdateStatus:
        return cls(
            d.get("state", "idle"),
            d.get("version"),
            d.get("message"),
            d.get("bytes"),
            d.get("totalBytes"),
            d.get("time"),
        )


@dataclass(frozen=True, slots=True)
class FirmwareRelease:
    """A release the station could install."""

    version: str
    file_name: str
    author: str | None = None
    #: Text, or a link to the release notes.
    release_notes: str | None = None
    beta: bool = False
    revoked: bool = False
    installed: bool = False
    #: On the station already, so installing needs no download.
    downloaded: bool = False
    #: ``catalogue``, or ``uploaded`` for a package only the station's cache has.
    origin: str = "catalogue"
    #: False below the station's minimum version (6.0.0); installing it is refused.
    installable: bool = True

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FirmwareRelease:
        return cls(
            version=d.get("version", ""),
            file_name=d.get("fileName", ""),
            author=d.get("author"),
            release_notes=d.get("releaseNotes"),
            beta=bool(d.get("beta")),
            revoked=bool(d.get("revoked")),
            installed=bool(d.get("installed")),
            downloaded=bool(d.get("downloaded")),
            origin=d.get("origin", "catalogue"),
            installable=bool(d.get("installable", True)),
        )


@dataclass(frozen=True, slots=True)
class FirmwareReleases:
    """The source's releases, newest first."""

    source: FirmwareSource
    releases: tuple[FirmwareRelease, ...] = field(default=())
    #: Why the source couldn't be read; ``releases`` then holds the cached packages only.
    error: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FirmwareReleases:
        return cls(
            FirmwareSource.from_dict(d.get("source") or {}),
            tuple(FirmwareRelease.from_dict(r) for r in d.get("releases") or ()),
            d.get("error"),
        )


@dataclass(frozen=True, slots=True)
class FirmwareState:
    """Firmware on a station."""

    #: The installed version, or None; ``pending`` after an interrupted update.
    current: str | None
    source: FirmwareSource
    default_source: str
    #: False off a station (a WebApi on a development PC): installing raises 501.
    supported: bool
    #: The oldest version the station installs.
    minimum_version: str
    update: FirmwareUpdateStatus

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FirmwareState:
        return cls(
            d.get("current"),
            FirmwareSource.from_dict(d.get("source") or {}),
            d.get("defaultSource", ""),
            bool(d.get("supported")),
            d.get("minimumVersion", ""),
            FirmwareUpdateStatus.from_dict(d.get("update") or {}),
        )


class FirmwareGroup(ApiGroupBase):
    """Firmware updates: releases, the release source, packages and installing.

    The station installs only releases signed by E-Sharp, whichever way they arrive; the check
    runs on the station and no client can skip it. Installing restarts the hardware app and the
    WebApi, so every client loses the station for a minute or two. Changes are writes: while
    another client holds the lease they raise 423.
    """

    def get_state(self) -> FirmwareState:
        """The installed version, the release source and how the last update went."""
        data = self._get_json("api/system/firmware")
        assert isinstance(data, dict)
        return FirmwareState.from_dict(data)

    def get_releases(self, include_beta: bool = False) -> FirmwareReleases:
        """The source's releases, newest first; revoked ones are left out.

        Packages only the station's cache has (uploaded ones) are listed too.
        """
        flag = "true" if include_beta else "false"
        data = self._get_json(f"api/system/firmware/releases?includeBeta={flag}")
        assert isinstance(data, dict)
        return FirmwareReleases.from_dict(data)

    def set_source(self, location: str | None) -> FirmwareSource:
        """Where the station looks for releases: an http(s) address or an absolute folder on the Pi.

        None goes back to the E-Sharp deployment.
        """
        data = self._put_json("api/system/firmware/source", {"location": location})
        assert isinstance(data, dict)
        return FirmwareSource.from_dict(data)

    def start_update(self, version: str, include_beta: bool = False) -> FirmwareUpdateStatus:
        """Start installing *version* and return at once; follow :meth:`get_update`.

        Raises 400 for a release below the minimum version or one that isn't signed by E-Sharp,
        404 for a version neither the source nor the cache has, 409 while an update runs, and 501
        off a station.
        """
        data = self._post_json(
            "api/system/firmware/update", {"version": version, "includeBeta": include_beta}
        )
        assert isinstance(data, dict)
        return FirmwareUpdateStatus.from_dict(data)

    def get_update(self) -> FirmwareUpdateStatus:
        """How the current or last update stands."""
        data = self._get_json("api/system/firmware/update")
        assert isinstance(data, dict)
        return FirmwareUpdateStatus.from_dict(data)

    def get_update_log(self) -> str:
        """The last update's log."""
        return self._get_bytes("api/system/firmware/update/log").decode("utf-8", errors="replace")

    def wait_for_update(self, timeout: float = 900.0, poll: float = 2.0) -> FirmwareUpdateStatus:
        """Wait until the update has ended and return how it went.

        The WebApi restarts during an install, so failed connections are expected for a while
        and are retried until *timeout* seconds have passed (then :class:`TimeoutError`).
        """
        deadline = time.monotonic() + timeout
        while True:
            try:
                status = self.get_update()
                if status.finished:
                    return status
            except (OSError, http.client.HTTPException):
                pass  # the station is restarting
            except AccordionQ2ApiError as error:
                if error.status_code not in (502, 503, 504):
                    raise
            if time.monotonic() >= deadline:
                raise TimeoutError(f"The update didn't finish within {timeout:.0f} s")
            time.sleep(poll)

    def install(
        self, version: str, include_beta: bool = False, timeout: float = 900.0
    ) -> FirmwareUpdateStatus:
        """Install *version* and wait until it has ended; check ``state == "succeeded"``."""
        self.start_update(version, include_beta)
        return self.wait_for_update(timeout)

    def upload_package(self, package: bytes | str | PathLike[str]) -> FirmwareRelease:
        """Send a release package (``rel-x.y.z.zip``) to the station, e.g. from this computer.

        *package* is the zip's bytes or a path to it. The station checks it, signature included,
        and keeps it by the version its folder names; install it with :meth:`start_update`.
        """
        data = package if isinstance(package, bytes) else Path(package).read_bytes()
        raw = self._request(
            "POST",
            "api/system/firmware/packages",
            body=data,
            headers={"Content-Type": "application/octet-stream"},
        )
        return FirmwareRelease.from_dict(json.loads(raw))

    def install_package(
        self, package: bytes | str | PathLike[str], timeout: float = 900.0
    ) -> FirmwareUpdateStatus:
        """Send a release package to the station, install it and wait until it has ended."""
        release = self.upload_package(package)
        return self.install(release.version, timeout=timeout)

    def delete_package(self, file_name: str) -> None:
        """Remove a package from the station's cache."""
        self._delete(f"api/system/firmware/packages/{quote(file_name, safe='')}")

"""Channel query and configuration operations."""

from __future__ import annotations

import io
import os
import time
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import quote

from ._base import ApiGroupBase
from .models import ChannelConfigRequest, ChannelDto, ChannelLookupRequest

#: The states a load ends in.
BYTESTREAM_ENDED = frozenset({"done", "failed"})
#: The states while a load runs.
BYTESTREAM_RUNNING = frozenset({"validating", "loading", "waitingDone"})


@dataclass(frozen=True, slots=True)
class ByteStreamImage:
    """The last image a ByteStream file channel took (only the last one is kept)."""

    file_name: str | None = None
    size: int = 0
    #: SHA-256 of what was loaded, lowercase hex.
    sha256: str | None = None
    #: ``bit`` or ``bin``.
    format: str | None = None
    #: The .bit header's design field (name, UserID, Vivado version).
    design: str | None = None
    #: The .bit header's part, e.g. ``xcku5p-ffvb676-1-e``.
    part: str | None = None
    built: str | None = None
    #: ISO 8601.
    started: str | None = None
    finished: str | None = None
    duration_ms: int | None = None
    #: ``ok``, or the error; ``None`` while the load runs.
    result: str | None = None
    #: The FPGA runs this image now; ``False`` once a POWER cycle or a PROGRAM_B pulse
    #: has replaced it.
    loaded: bool = False
    replaced: str | None = None
    #: The DesignID device's Info.Keys from the first HCI.Scan after the load.
    design_keys: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ByteStreamImage:
        return cls(
            file_name=d.get("fileName"),
            size=int(d.get("size") or 0),
            sha256=d.get("sha256"),
            format=d.get("format"),
            design=d.get("design"),
            part=d.get("part"),
            built=d.get("built"),
            started=d.get("started"),
            finished=d.get("finished"),
            duration_ms=d.get("durationMs"),
            result=d.get("result"),
            loaded=bool(d.get("loaded")),
            replaced=d.get("replaced"),
            design_keys=d.get("designKeys"),
        )


@dataclass(frozen=True, slots=True)
class ByteStreamStatus:
    """The status of a ByteStream file channel (MicroHAPS ``JTAG.FPGA_IMAGE``: an image load)."""

    #: ``idle``, ``validating``, ``loading``, ``waitingDone``, ``done`` or ``failed``.
    state: str = "idle"
    target: str | None = None
    #: 0 to 100 while loading (openFPGALoader's own percentage).
    progress: float = 0.0
    #: The progress bar's label, e.g. ``Load SRAM``.
    phase: str | None = None
    message: str | None = None
    label: str | None = None
    #: The extensions the channel takes, e.g. ``.bit``.
    accept: str | None = None
    targets: list[str] = field(default_factory=lambda: ["sram"])
    max_bytes: int = 0
    image: ByteStreamImage | None = None

    @property
    def running(self) -> bool:
        """A load is running."""
        return self.state in BYTESTREAM_RUNNING

    @property
    def ended(self) -> bool:
        """The load has ended, well or not."""
        return self.state in BYTESTREAM_ENDED

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ByteStreamStatus:
        image = d.get("image")
        return cls(
            state=d.get("state", "idle"),
            target=d.get("target"),
            progress=float(d.get("progress") or 0.0),
            phase=d.get("phase"),
            message=d.get("message"),
            label=d.get("label"),
            accept=d.get("accept"),
            targets=list(d.get("targets") or ["sram"]),
            max_bytes=int(d.get("maxBytes") or 0),
            image=ByteStreamImage.from_dict(image) if isinstance(image, dict) else None,
        )


class ByteStreamLoadError(Exception):
    """A load the station took but that failed (``state`` ``failed``); :attr:`status` says why."""

    def __init__(self, status: ByteStreamStatus) -> None:
        super().__init__(status.message or "the load failed")
        self.status = status


class ChannelsGroup(ApiGroupBase):
    """Operations for querying and configuring hardware channels."""

    def get_all(self) -> list[ChannelDto]:
        """Return all configured channels."""
        data = self._get_json("api/channels")
        assert isinstance(data, list)
        return [ChannelDto.from_dict(ch) for ch in data]

    def get_channel(self, alias: str | None = None, net_name: str | None = None) -> ChannelDto:
        """Look up a single channel by alias or net name.

        At least one of *alias* or *net_name* must be provided.
        """
        body = ChannelLookupRequest(alias=alias, net_name=net_name).to_dict()
        result = self._post_json("api/channels/channel", body)
        assert isinstance(result, dict)
        return ChannelDto.from_dict(result)

    def configure(self, config: ChannelConfigRequest) -> None:
        """Apply a partial update to a single channel.

        *config* is a :class:`~accordionq2.models.ChannelConfigRequest`.
        Only non-``None`` fields are applied.
        """
        self._post("api/channels/channel/configure", config.to_dict())

    def configure_many(self, configs: list[ChannelConfigRequest]) -> None:
        """Apply partial updates to multiple channels in one round-trip.

        *configs* is a list of
        :class:`~accordionq2.models.ChannelConfigRequest` objects.
        """
        self._post("api/channels/configure", [c.to_dict() for c in configs])

    def upload_bytestream(
        self,
        name: str,
        image: bytes | BinaryIO | str | PathLike[str],
        target: str = "sram",
        file_name: str | None = None,
        force: bool = False,
    ) -> ByteStreamStatus:
        """Send a file to a ByteStream file channel (firmware 7.0.5).

        For MicroHAPS's ``JTAG.FPGA_IMAGE`` the file is an FPGA image (a Vivado ``.bit`` for
        XCKU5P-FFVB676), loaded into the KU5P's SRAM by openFPGALoader without Vivado. *image* is
        the bytes, an open binary file or a path; a file is sent as it is read, not read whole.
        Returns once the station has taken the file and started the load (HTTP 202); follow it
        with :meth:`bytestream_status` or use :meth:`load_fpga_image`. Raises
        :class:`~accordionq2.AccordionQ2ApiError` with 400 (not a file channel, or the file refused,
        e.g. built for another part), 409 (a load, a POWER cycle or a PROGRAM pulse is running),
        413 (over 64 MB), 423 (leased by someone else), 501 (``target="flash"``: not in this
        firmware) or 504 (the station didn't take the file in time; read the status).
        *force* loads even while Vivado is connected to the station's XVC server.
        """
        headers = {"Content-Type": "application/octet-stream"}
        opened: BinaryIO | None = None
        body: bytes | BinaryIO
        if isinstance(image, (bytes, bytearray, memoryview)):
            body = bytes(image)
            file_name = file_name or "image.bit"
        elif hasattr(image, "read"):
            body = image  # type: ignore[assignment]
            file_name = file_name or Path(getattr(image, "name", "image.bit")).name
        else:
            opened = open(Path(image), "rb")
            body = opened
            file_name = file_name or Path(image).name
        try:
            if not isinstance(body, bytes):
                # The size up front: the station refuses a file that is too big before it is sent
                try:
                    remaining = os.fstat(body.fileno()).st_size - body.tell()
                    headers["Content-Length"] = str(remaining)
                except (AttributeError, OSError, io.UnsupportedOperation):
                    pass
            path = (
                f"api/channels/bytestream?name={quote(name, safe='')}"
                f"&fileName={quote(file_name, safe='')}&target={quote(target, safe='')}"
                + ("&force=true" if force else "")
            )
            raw = self._request("POST", path, body=body, headers=headers)
        finally:
            if opened is not None:
                opened.close()
        return ByteStreamStatus.from_dict(self._loads(raw))

    def bytestream_status(self, name: str) -> ByteStreamStatus:
        """The status of a ByteStream file channel: the load's state, progress and result, and the
        last image's name, size and SHA-256. Answered also while someone else holds the lease."""
        raw = self._request("GET", f"api/channels/bytestream?name={quote(name, safe='')}")
        return ByteStreamStatus.from_dict(self._loads(raw))

    def wait_bytestream(
        self, name: str, timeout: float = 120.0, poll: float = 0.5
    ) -> ByteStreamStatus:
        """Read the status every *poll* seconds until the load has ended and return it.

        A failed load is returned, not raised; :class:`TimeoutError` after *timeout* seconds.
        """
        deadline = time.monotonic() + timeout
        while True:
            status = self.bytestream_status(name)
            if status.ended:
                return status
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"{name}: still {status.state} ({status.progress:.0f} %) after {timeout:.0f} s"
                )
            time.sleep(poll)

    def load_fpga_image(
        self,
        name: str,
        image: bytes | BinaryIO | str | PathLike[str],
        target: str = "sram",
        timeout: float = 120.0,
        file_name: str | None = None,
        force: bool = False,
    ) -> ByteStreamStatus:
        """Upload an FPGA image and wait until it is loaded and the FPGA is configured.

        Raises :class:`ByteStreamLoadError` with the station's message when the load fails.
        Run ``HCI.Scan`` afterwards to see the new design's devices.
        """
        self.upload_bytestream(name, image, target=target, file_name=file_name, force=force)
        status = self.wait_bytestream(name, timeout=timeout)
        if status.state != "done":
            raise ByteStreamLoadError(status)
        return status

    @staticmethod
    def _loads(raw: bytes) -> dict[str, Any]:
        import json

        data = json.loads(raw) if raw else {}
        return data if isinstance(data, dict) else {}

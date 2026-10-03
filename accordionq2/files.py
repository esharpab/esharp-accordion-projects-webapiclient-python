"""Files in the station's own folders (accordionq2 contract section 10)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

from ._base import ApiGroupBase


@dataclass(frozen=True, slots=True)
class FileRoot:
    """A folder the file API reaches."""

    #: ``config``, ``alias``, ``fsms``, ``media``, ``extensions``, ``logs``, ``webapi-logs``.
    id: str
    description: str
    writable: bool
    #: False when the station doesn't have the folder.
    exists: bool

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FileRoot:
        return cls(
            d.get("id", ""),
            d.get("description", ""),
            bool(d.get("writable")),
            bool(d.get("exists")),
        )


@dataclass(frozen=True, slots=True)
class FileEntry:
    """A file or folder in a listing."""

    name: str
    directory: bool
    #: Bytes; None for a folder.
    size: int | None
    #: ISO 8601.
    modified: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FileEntry:
        return cls(
            d.get("name", ""), bool(d.get("directory")), d.get("size"), d.get("modified", "")
        )


@dataclass(frozen=True, slots=True)
class FileListing:
    """A folder's contents, folders first."""

    root: str
    path: str
    writable: bool
    entries: tuple[FileEntry, ...] = field(default=())


def _q(value: str) -> str:
    return quote(value, safe="")


class FilesGroup(ApiGroupBase):
    """Files in the station's own folders.

    A *path* is relative to its folder (*root*), with forward slashes; it can't
    leave the folder or pass a symbolic link. The log folders are read-only.
    """

    def get_roots(self) -> list[FileRoot]:
        """The folders the file API reaches."""
        data = self._get_json("api/files")
        assert isinstance(data, list)
        return [FileRoot.from_dict(r) for r in data]

    def list(self, root: str, path: str = "") -> FileListing:
        """What a folder holds."""
        data = self._get_json(f"api/files/{_q(root)}?path={_q(path)}")
        assert isinstance(data, dict)
        return FileListing(
            root=data.get("root", root),
            path=data.get("path", path),
            writable=bool(data.get("writable")),
            entries=tuple(FileEntry.from_dict(e) for e in data.get("entries") or ()),
        )

    def download(self, root: str, path: str) -> bytes:
        """A file's bytes."""
        return self._get_bytes(f"api/files/{_q(root)}/content?path={_q(path)}")

    def upload(self, root: str, path: str, data: bytes, overwrite: bool = False) -> FileEntry:
        """Upload a file; an existing one is replaced only with *overwrite* (409 otherwise)."""
        flag = "true" if overwrite else "false"
        raw = self._request(
            "PUT",
            f"api/files/{_q(root)}/content?path={_q(path)}&overwrite={flag}",
            body=data,
            headers={"Content-Type": "application/octet-stream"},
        )
        return FileEntry.from_dict(json.loads(raw))

    def create_folder(self, root: str, path: str) -> None:
        """Create a folder."""
        self._post(f"api/files/{_q(root)}/folder?path={_q(path)}")

    def move(self, root: str, source: str, target: str, overwrite: bool = False) -> None:
        """Rename or move a file or folder within its folder."""
        self._post(
            f"api/files/{_q(root)}/move", {"from": source, "to": target, "overwrite": overwrite}
        )

    def delete(self, root: str, path: str, recursive: bool = False) -> None:
        """Delete a file, or a folder: one with contents only with *recursive*."""
        self._delete(
            f"api/files/{_q(root)}?path={_q(path)}&recursive={'true' if recursive else 'false'}"
        )

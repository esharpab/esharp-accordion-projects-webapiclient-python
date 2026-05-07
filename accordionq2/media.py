"""Media file operations."""

from __future__ import annotations

from urllib.parse import quote

from ._base import ApiGroupBase


class MediaGroup(ApiGroupBase):
    """Operations for managing media files stored on the device."""

    def list_files(self) -> list[str]:
        """List all available media files."""
        result = self._get_json("api/media")
        assert isinstance(result, list)
        return result

    def download_file(self, file_name: str) -> bytes:
        """Download a media file as raw bytes."""
        return self._get_bytes("api/media/{}".format(quote(file_name, safe="")))

    def upload_file(self, file_name: str, data: bytes) -> None:
        """Upload a media file to the device."""
        self._post_multipart("api/media/upload", file_name, data)

    def delete_file(self, file_name: str) -> None:
        """Delete a media file from the device."""
        self._delete("api/media/{}".format(quote(file_name, safe="")))

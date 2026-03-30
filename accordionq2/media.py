"""Media file operations."""

from urllib.parse import quote

from ._base import ApiGroupBase


class MediaGroup(ApiGroupBase):
    """Operations for managing media files stored on the device."""

    def list_files(self):
        """List all available media files."""
        return self._get_json("api/media")

    def download_file(self, file_name):
        """Download a media file as raw bytes."""
        return self._get_bytes(
            "api/media/{}".format(quote(file_name, safe=""))
        )

    def upload_file(self, file_name, data):
        """Upload a media file to the device."""
        self._post_multipart("api/media/upload", file_name, data)

    def delete_file(self, file_name):
        """Delete a media file from the device."""
        self._delete("api/media/{}".format(quote(file_name, safe="")))

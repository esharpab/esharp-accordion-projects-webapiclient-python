"""Integration tests for media file operations."""

import pytest

pytestmark = pytest.mark.integration


def test_list_files_returns_list(client):
    files = client.media.list_files()
    print("Media files count: {}".format(len(files)))
    for f in files:
        print("  Media: {}".format(f))
    assert files is not None

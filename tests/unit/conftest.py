"""Shared fixtures and helpers for unit tests (no hardware required)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from accordionq2._base import HttpSession


def make_session(responses: list[tuple[int, object]]) -> HttpSession:
    """Return an HttpSession whose ``request`` method returns *responses* in order.

    Each entry is ``(status_code, body)`` where *body* may be a dict/list (serialised
    to JSON bytes automatically) or raw bytes.
    """
    session = HttpSession.__new__(HttpSession)
    session._scheme = "http"
    session._host = "localhost"
    session._port = 5000
    session._path_prefix = ""
    session._timeout = 5.0
    session._verify = True
    session._conn = None
    session._default_headers = {}

    import threading
    session._lock = threading.Lock()

    encoded = [
        (status, body if isinstance(body, bytes) else json.dumps(body).encode())
        for status, body in responses
    ]
    session.request = MagicMock(side_effect=encoded)
    return session

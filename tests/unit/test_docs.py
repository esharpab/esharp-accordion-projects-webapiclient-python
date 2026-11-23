"""Unit tests for client.docs (firmware 7.1.0, api/docs).

The connection is mocked; each test checks the method and path sent against the WebApi's
DocsController and how the answer is read.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from accordionq2 import AccordionQ2ApiError, AccordionQ2Client, DocsList, DocsPage
from accordionq2._base import HttpSession
from accordionq2.docs import NO_ENDPOINT_NOTE, DocsGroup

# As the WebApi serialises DocsListResponse (web defaults: camelCase)
LIST = {
    "baseUrl": "https://station-12/docs/",
    "llmsTxt": "https://station-12/docs/llms.txt",
    "pages": [
        {
            "path": "03-connectivity/security",
            "title": "Security",
            "section": "Connectivity and security",
            "summary": "The reference.",
            "html": "03-connectivity/security.html",
            "md": "03-connectivity/security.md",
        }
    ],
    "note": None,
}


def _response(status: int, body: object) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = body if isinstance(body, bytes) else json.dumps(body).encode()
    resp.headers = {}
    return resp


class Station:
    """A docs group on a session whose connection answers *answers* in order."""

    def __init__(self, *answers: tuple[int, object]):
        self.session = HttpSession("https://station-12:5001", timeout=5.0, verify=False)
        self.session._conn = MagicMock()
        self.session._conn.getresponse.side_effect = [_response(s, b) for s, b in answers]
        self.docs = DocsGroup(self.session)

    def sent(self, index: int = -1) -> tuple[str, str]:
        call = self.session._conn.request.call_args_list[index]  # type: ignore[union-attr]
        return call.args[0], call.args[1]


def test_the_client_has_the_group():
    client = AccordionQ2Client("https://station-12:5001", verify=False)
    assert isinstance(client.docs, DocsGroup)


def test_list_reads_the_pages_and_the_docs_url():
    station = Station((200, LIST))
    result = station.docs.list()
    assert station.sent() == ("GET", "/api/docs")
    assert isinstance(result, DocsList)
    assert result.base_url == "https://station-12/docs/"
    assert result.llms_txt == "https://station-12/docs/llms.txt"
    assert result.note is None
    assert result.pages == (
        DocsPage(
            path="03-connectivity/security",
            title="Security",
            section="Connectivity and security",
            summary="The reference.",
            html="03-connectivity/security.html",
            md="03-connectivity/security.md",
        ),
    )


def test_a_station_without_pages_answers_an_empty_list_with_its_note():
    station = Station((200, {"baseUrl": None, "llmsTxt": None, "pages": [], "note": "no pages"}))
    result = station.docs.list()
    assert result.pages == () and result.note == "no pages" and result.base_url is None


def test_a_station_before_7_1_0_is_an_empty_list_with_a_note():
    station = Station((404, {}))
    result = station.docs.list()
    assert result.pages == ()
    assert result.note == NO_ENDPOINT_NOTE


def test_get_is_the_markdown_and_with_html_the_html_page():
    station = Station(
        (200, "# Security\n\nKävlinge\n".encode()), (200, "<!doctype html><p>Kävlinge</p>".encode())
    )
    assert station.docs.get("03-connectivity/security") == "# Security\n\nKävlinge\n"
    assert station.sent() == ("GET", "/api/docs/03-connectivity/security")
    assert (
        station.docs.get("03-connectivity/security", html=True) == "<!doctype html><p>Kävlinge</p>"
    )
    assert station.sent() == ("GET", "/api/docs/03-connectivity/security?format=html")


def test_each_segment_is_escaped_and_the_slashes_kept():
    station = Station((200, b"x"))
    station.docs.get("/a page/x#y/")
    assert station.sent() == ("GET", "/api/docs/a%20page/x%23y")


@pytest.mark.parametrize("path", ["", "  "])
def test_an_empty_path_is_refused_before_sending(path):
    station = Station()
    with pytest.raises(ValueError):
        station.docs.get(path)


def test_a_page_that_isn_t_there_is_a_404():
    station = Station(
        (404, {"error": "No page 'x' in the documentation; GET /api/docs lists the pages"})
    )
    with pytest.raises(AccordionQ2ApiError) as info:
        station.docs.get("x")
    assert info.value.status_code == 404

"""The station's documentation (firmware 7.1.0, ``api/docs``), for scripts and AI agents.

The pages the station serves under ``/docs/`` on its Web UI port, listed and read as Markdown
(the default) or HTML. Anonymous in every security mode: no key is needed (one the client has
is sent as on every call).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from ._base import ApiGroupBase
from .exceptions import AccordionQ2ApiError

#: The note of the list from a station whose firmware has no ``api/docs`` (before 7.1.0).
NO_ENDPOINT_NOTE = "This station's firmware has no api/docs (it came with 7.1.0)."


@dataclass(frozen=True, slots=True)
class DocsPage:
    """A page of the station's documentation.

    :attr:`path` is what :meth:`DocsGroup.get` takes; :attr:`html` and :attr:`md` are the HTML
    page and its Markdown copy under ``/docs/`` on the station's Web UI.
    """

    path: str
    title: str
    section: str
    #: The page's first paragraph, shortened.
    summary: str
    html: str
    md: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DocsPage:
        return cls(
            path=str(d.get("path", "")),
            title=str(d.get("title", "")),
            section=str(d.get("section", "")),
            summary=str(d.get("summary", "")),
            html=str(d.get("html", "")),
            md=str(d.get("md", "")),
        )


@dataclass(frozen=True, slots=True)
class DocsList:
    """The station's documentation pages (``GET /api/docs``).

    :attr:`base_url` is ``/docs/`` on the station's Web UI port (None when the Web UI is off);
    :attr:`llms_txt` the pages in the llms.txt convention; :attr:`note` why the list is empty (a
    station without the pages, or firmware before 7.1.0).
    """

    base_url: str | None
    llms_txt: str | None
    pages: tuple[DocsPage, ...]
    note: str | None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DocsList:
        pages = d.get("pages")
        return cls(
            base_url=_opt_str(d.get("baseUrl")),
            llms_txt=_opt_str(d.get("llmsTxt")),
            pages=tuple(DocsPage.from_dict(p) for p in pages if isinstance(p, dict))
            if isinstance(pages, list)
            else (),
            note=_opt_str(d.get("note")),
        )


def _opt_str(value: object) -> str | None:
    return None if value is None else str(value)


class DocsGroup(ApiGroupBase):
    """The station's documentation (firmware 7.1.0): ``list()`` and ``get(path, html=False)``."""

    def list(self) -> DocsList:
        """The documentation's pages in the documentation's order, with ``/docs/``'s URL.

        Empty with a :attr:`DocsList.note` when the station has no pages or its firmware has no
        ``api/docs`` (404).
        """
        try:
            d = self._get_json("api/docs")
        except AccordionQ2ApiError as error:
            if error.status_code == 404:
                return DocsList(base_url=None, llms_txt=None, pages=(), note=NO_ENDPOINT_NOTE)
            raise
        if not isinstance(d, dict):
            raise AccordionQ2ApiError(200, "The station's answer isn't a JSON object")
        return DocsList.from_dict(d)

    def get(self, path: str, html: bool = False) -> str:
        """A page by its :attr:`DocsPage.path` (or its .md or .html file): its cleaned Markdown,
        or with *html* its HTML page. A path that isn't one of the pages raises
        :class:`AccordionQ2ApiError` with 404."""
        if not isinstance(path, str) or not path.strip():
            raise ValueError("A page's path from list()")
        escaped = "/".join(quote(part, safe="") for part in path.strip("/").split("/"))
        query = "?format=html" if html else ""
        return self._get_bytes(f"api/docs/{escaped}{query}").decode("utf-8")

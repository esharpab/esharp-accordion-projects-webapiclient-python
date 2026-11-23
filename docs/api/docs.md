# Documentation

The station's own documentation, for scripts and AI agents (firmware 7.1.0): the pages the station serves under `/docs/` on its Web UI port, listed and read as Markdown or HTML. The calls need no API key in any security mode; a key the client has is sent as on every call. In security mode `On` requests without a key are rate limited per client, as for every call that needs no key.

`client.capabilities.get()` lists the feature `docs` (`CapabilitiesDto.DOCS`) when the station has the pages.

## Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `list()` | `DocsList` | The pages, in the documentation's order, and `/docs/` on the station's Web UI. Empty with a `note` when the station has no pages, or its firmware has no `api/docs` (before 7.1.0). |
| `get(path, html=False)` | `str` | A page by its `path` from the list (or its `.md` or `.html` file): its Markdown, or with `html=True` its HTML page. A path that isn't one of the pages raises `AccordionQ2ApiError` with `status_code` 404. |

## Example

```python
docs = client.docs.list()
for page in docs.pages:
    if page.section == "Connectivity and security":
        print(f"{page.title}: {page.summary}")

markdown = client.docs.get("03-connectivity/security")
```

## Models

`DocsList`

| Field | Type | Description |
|-------|------|-------------|
| `base_url` | `str \| None` | `/docs/` on the station's Web UI port, where each page's `html` and `md` are; None when the Web UI is off |
| `llms_txt` | `str \| None` | The pages in the llms.txt convention (`/docs/llms.txt`); None when the Web UI is off or there are no pages |
| `pages` | `tuple[DocsPage, ...]` | The pages |
| `note` | `str \| None` | Why the list is empty; None otherwise |

`DocsPage`

| Field | Type | Description |
|-------|------|-------------|
| `path` | `str` | What `get` takes, e.g. `03-connectivity/security` |
| `title` | `str` | The page's title |
| `section` | `str` | The section it is listed in, e.g. `Connectivity and security` |
| `summary` | `str` | Its first paragraph, shortened |
| `html` | `str` | The HTML page, relative to `base_url` |
| `md` | `str` | Its Markdown copy, relative to `base_url` |

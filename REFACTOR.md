# Refactor Notes

> **Status: v2.0.0 — all items implemented and documentation updated.**
> Source code, unit tests (82 passing), CI pipeline, CHANGELOG, and all documentation files
> updated to reflect v2.0.0 changes. This file is preserved for historical reference.
 – `accordionq2` Python Client

This document tracks identified issues and proposed improvements.
Items are grouped by area. Add user feedback under each section before acting on any change.

---

## 1. `models.py` – Dataclass misuse *(confirmed bug)*

**Issue:** Six classes use `@dataclass` but also define class-level attribute
assignments *and* a hand-written `__init__`, making `@dataclass` completely redundant.
The class-level assignments create **class variables** shared across all instances.
The custom `__init__` overwrites them per-instance at construction time, but the damage
is wider than that:

- `@dataclass` generates `__repr__` and `__eq__` from the *annotated fields* — but
  none of these classes have annotations, only bare assignments. The generated
  `__repr__` and `__eq__` therefore see **no fields at all** and produce useless output.
- `@dataclass` also generates `__init__` — which is immediately overridden by the
  hand-written one. The generated `__init__` is dead code.
- Any mutable class-level default (e.g. `modules = []`) is a **single list shared
  between every instance**. Code that appends to it without going through `__init__`
  corrupts all instances.
- `dataclasses.fields()` returns an empty tuple for these classes, breaking any
  generic tooling that introspects fields.

Confirmed `ruff` violation: `RUF012` (mutable class variable not annotated `ClassVar`).

Classes affected: `ConnectionStatusDto`, `AppLicenseDto`, `ModuleSettingsDto`,
`PhysicalModuleDto`, `PhysicalSystemDto`, `ChannelDto`.

**Implementation recipe** (confirmed by owner, using `ChannelDto` as the canonical example):

```python
# ❌ Current — broken
@dataclass
class ChannelDto:
    name = ""          # class variable, shared across ALL instances
    modules = []       # mutable default, shared across ALL instances

    def __init__(self, **kwargs):       # overrides the generated __init__
        self.name = kwargs.get("name", "")
        self.modules = kwargs.get("modules", [])
    # __repr__ and __eq__ see zero fields → useless

# ✅ Correct — confirmed target form
@dataclass(frozen=True, slots=True)
class ChannelDto:
    """Represents a multi-purpose hardware channel."""
    channel_index: int = 0
    index: int = 0
    enabled: bool = False
    usage: MpioUsageTypes = MpioUsageTypes.UNDEFINED
    device_name: str = ""
    channel_type: ChannelTypes = ChannelTypes.UNDEFINED
    channel_type_capability: ChannelTypes = ChannelTypes.UNDEFINED
    alias: str = ""
    net_name: str = ""
    group_name: str = ""
    capability: DirectionTypes = DirectionTypes.UNDEFINED
    description: str = ""
    direction: DirectionTypes = DirectionTypes.UNDEFINED
    direction_changed: bool = False
    default_direction: DirectionTypes = DirectionTypes.UNDEFINED
    unit: str = ""
    is_virtual: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "ChannelDto":
        # from_dict stays as-is — only __init__ is removed
        ...
```

**Rules for each class (apply uniformly):**

1. Remove all bare class-level assignments (`name = ""`).
2. Replace with typed field declarations (`name: str = ""`).
3. Delete the custom `__init__` entirely — `@dataclass` generates it from the field
   declarations.
4. Apply `@dataclass(frozen=True, slots=True)`:
   - `frozen=True` → immutable; appropriate for read-only API response DTOs.
   - `slots=True` → less memory, faster attribute access, no accidental extra attributes.
5. For mutable defaults (lists, dicts) use `field(default_factory=list)` /
   `field(default_factory=dict)` — **never** a bare `= []` or `= {}`.
6. The `from_dict` classmethod stays exactly as-is.
7. Add type annotations to `from_dict` signature: `(cls, data: dict) -> "ClassName"`.

**Note on request classes (`ChannelLookupRequest`, `ChannelConfigRequest`):**
These are not read-only; callers construct and mutate them. Use
`@dataclass` without `frozen=True`. `to_dict` stays as-is. See item 2.

**Alternative (deferred decision):** Replace `@dataclass` entirely with
`pydantic.BaseModel`, which gives the same correctness plus automatic JSON serde
(eliminating `from_dict` entirely), field validation, and safe mutable defaults — at
the cost of adding a runtime dependency. Decision deferred to owner.

---

## 2. `models.py` – Non-dataclass request objects lack `@dataclass`

**Issue:** `ChannelLookupRequest` and `ChannelConfigRequest` are plain classes with a
manual `__init__` and `to_dict`. They would benefit from `@dataclass` to get `__repr__`
and `__eq__` for free, just like the DTO classes.

**Proposed fix:** Convert both to `@dataclass` (all fields optional/defaulting to
`None`) and keep the `to_dict` method.

---

## 3. `enums.py` – Duplicate mapping tables for `IntFlag` enums

**Issue:** `_DIRECTION_NAMES` and `_CHANNEL_TYPE_NAMES` are hand-maintained dicts that
duplicate the integer values already present in the `IntFlag` enum members. If a new
flag is added to `ChannelTypes` or `DirectionTypes`, the parse dict must also be
updated manually or parsing silently breaks.

**Proposed fix:** Derive the lookup dicts from the enum classes themselves (e.g.
`{m.name.title(): m.value for m in ChannelTypes}` or a small explicit name-map driven
off the enum). Also consider whether the JSON name casing ("VirtualDigital", "UART")
can be preserved with `_name_` overrides or a `_missing_` hook.

---

## 4. `_base.py` – `_post_multipart` uses raw string formatting for MIME boundary

**Issue:** The multipart body is assembled with manual string concatenation. This works
today but is fragile: if `filename` contains special characters (spaces, quotes,
non-ASCII) the `Content-Disposition` header will be malformed.

**Proposed fix:** Encode the filename with `email.utils.encode_rfc2231` or quote it
per RFC 5987, or use `urllib3`/`httpx` if the no-dependency constraint is relaxed.

---

## 5. `_base.py` – `full_path` construction produces double slashes

**Issue:** `full_path = "{}/{}".format(self._path_prefix, path)` will produce
`//api/…` when `base_url` has no path suffix (i.e. `_path_prefix` is `""`), because
the format string always inserts `/`. If `base_url` ends with `/` and `path` also
starts with `/` a double slash results.

**Proposed fix:** Use `posixpath.join` or strip leading slashes from `path` and handle
the empty-prefix case explicitly.

---

## 6. `numeric_results.py` – Python 2 fallback import

**Issue:**
```python
try:
    from urllib.parse import quote as _quote
except ImportError:
    from urllib import quote as _quote  # Python 2 fallback (unused but safe)
```
`pyproject.toml` requires `python>=3.8`. The Python 2 branch is dead code and adds
noise.

**Proposed fix:** Remove the `try/except` and use the unconditional
`from urllib.parse import quote as _quote`.

---

## 7. `resources.py` – `get_value` / `transact` assume fixed response key

**Issue:** Both methods access `result["value"]` (lowercase) after a `_post_json` call.
If the server ever returns `"Value"` (uppercase, consistent with other API responses)
these will raise a `KeyError` with no helpful message.

**Proposed fix:** Use `result.get("value") or result.get("Value")` with a clear error
if neither is present, or normalise the key in `_base.py`.

---

## 8. `channels.py` – `get_channel` duplicates `ChannelLookupRequest.to_dict` logic

**Issue:** `ChannelsGroup.get_channel` manually builds the lookup body inline:
```python
body = {}
if alias is not None:
    body["Alias"] = alias
if net_name is not None:
    body["NetName"] = net_name
```
This is the same logic as `ChannelLookupRequest.to_dict()`.

**Proposed fix:** Instantiate a `ChannelLookupRequest` and call `.to_dict()`.

---

## 9. `__init__.py` – Public surface is too narrow

**Issue:** Only `AccordionQ2Client` and `AccordionQ2ApiError` are exported. Users who
want to type-hint return values (e.g. `ChannelDto`, `BusTransactionResponse`,
`BusActions`) must import from internal submodules, which is fragile.

**Proposed fix:** Re-export all public model classes, enums, and exceptions from
`__init__.py` (and update `__all__`).

---

## 10. `_base.py` – Error message extraction is case-sensitive

**Issue:** The error-body parser checks for `err.get("error") or err.get("Error")`.
The API may return other keys (e.g. `"message"`, `"detail"`, `"title"` from ASP.NET
`ProblemDetails`). Unknown keys fall through to the raw body string.

**Proposed fix:** Also check `"message"`, `"detail"`, and `"title"` which are standard
`ProblemDetails` fields, or expose the full dict so callers can inspect it.

---

## 11. General – No type annotations

**Issue:** The entire library has no type hints. This makes IDE auto-complete and
static analysis (`mypy`, `pyright`) unavailable to users.

**Proposed fix:** Add `from __future__ import annotations` and PEP 484 / PEP 526 type
annotations to all public methods and dataclass fields. This is a larger effort and can
be done incrementally.

---

## User Feedback

### UF-1 – macOS not listed as a supported platform

The `pyproject.toml` does not declare any `classifiers` for supported platforms or
operating systems. Users on macOS have no indication the package works there, and CI
does not test it.

**Proposed fix:** Add `Operating System` trove classifiers covering Linux, macOS, and
Windows. Consider adding a macOS runner to the publish/test pipeline.

---

### UF-2 – No authentication mechanism; incorrect thread-safety claim; no opt-in TLS certificate validation

`HttpSession` in `_base.py` has three distinct issues:

**a) Thread safety is broken.** The docstring implies the session can be shared, but
`_conn` is mutated (reconnect on failure, `_close_conn`) without any lock. Concurrent
calls from multiple threads will race on `self._conn`, potentially causing one thread
to close the connection while another is mid-request.

**Proposed fix:** Add a `threading.Lock` acquired around the full `_connect` +
`request` + `getresponse` sequence in `HttpSession.request`, or clearly document that
the client is **not** thread-safe and one client per thread must be used.

**b) No authentication support.** `HttpSession` creates bare connections with no
support for HTTP Basic Auth, Bearer tokens, API keys, or client certificates.

**Proposed fix:** Add an optional `auth` parameter to `AccordionQ2Client` /
`HttpSession` (e.g. `(username, password)` tuple for Basic Auth, or a generic
`default_headers` dict for tokens/API keys) that is merged into every request's headers.

**c) No opt-in TLS certificate validation control.** `HTTPSConnection` uses the
default SSL context with no way for a caller to pass a custom CA bundle or disable
certificate verification (needed for self-signed certs on embedded devices).

**Proposed fix:** Add an optional `verify` parameter (`True` / `False` /
path-to-CA-bundle) forwarded to `ssl.create_default_context()` when constructing
`HTTPSConnection`.

---

### UF-3 – No async support

The library is entirely synchronous (`http.client`). Users integrating with `asyncio`-
based frameworks (e.g. FastAPI, Home Assistant, Jupyter) must run calls in a thread
executor, which is cumbersome.

**Proposed fix:** Introduce an optional async variant, either:
- A separate `AsyncAccordionQ2Client` using `aiohttp` or `httpx[async]` as an optional
  dependency (`pip install accordionq2[async]`), or
- Provide both sync and async method pairs in the same client class.

This is a significant effort; keep in sync/async parity in mind when making any other
structural changes so the async layer can be added without a second full rewrite.

---

### UF-4 – No changelog

There is no `CHANGELOG.md` (or equivalent). Users upgrading between versions have no
record of breaking changes, new features, or bug fixes.

**Proposed fix:** Create `CHANGELOG.md` following [Keep a Changelog](https://keepachangelog.com)
conventions. Populate it retroactively with at least the current `1.2.0` entry, and
add a changelog update step to the publish workflow.

---

### UF-5 – Invalid `license` key in `pyproject.toml`; license file and grants missing

`pyproject.toml` currently has:
```toml
license = {text = "Proprietary"}
```
This is not a valid SPDX expression. PEP 639 (accepted, effective setuptools ≥ 69)
requires either a valid SPDX identifier or `LicenseRef-` prefix for non-standard
licenses. Additionally there is no `LICENSE.md` file in the repo, so distributors and
PyPI cannot display the license terms.

**Proposed fix:**
1. Change the key to:
   ```toml
   license = {text = "LicenseRef-Proprietary", file = "LICENSE.md"}
   ```
2. Create a `LICENSE.md` file with the actual proprietary licence text / grant.
3. Add the `License :: Other/Proprietary License` trove classifier so PyPI displays
   it correctly.

---

### UF-6 – No type annotations — poor developer experience

No type hints exist anywhere in the library. IDEs cannot offer auto-complete on return
values, `mypy`/`pyright` cannot validate caller code, and the public API is harder to
learn without tooling support.

**Proposed fix:**
- Add `from __future__ import annotations` to each file for forward-reference support.
- Annotate all public method signatures and `@dataclass` fields with PEP 484 types.
- Annotate `_base.py` internals too so the type checker can verify the transport layer.
- Can be done incrementally — start with `models.py` and `client.py`, then the group
  files, then `_base.py`.

---

### UF-7 – No linter, formatter, or type checker; no pre-commit hooks

There is no `ruff`, `black`, `mypy`, or `pyright` configuration, and no
`.pre-commit-config.yaml`. Code style consistency relies entirely on author discipline.

**Proposed fix:**
- Add `ruff` as the single linter + formatter (replaces `flake8`, `isort`, `black`).
- Add `mypy` (or `pyright` via `pyrightconfig.json`) for static type checking.
- Add `.pre-commit-config.yaml` running `ruff format`, `ruff check --fix`, and `mypy`.
- Pin tool versions in `[project.optional-dependencies]` dev extra in `pyproject.toml`.
- Add `[tool.ruff]` and `[tool.mypy]` sections to `pyproject.toml`.

---

### UF-8 – No unit tests; only integration tests that require live hardware

The `tests/` directory contains only integration tests (`@pytest.mark.integration`)
that require a live device reachable at `ACCORDIONQ2_API_URL`. There are zero unit
tests, so CI cannot run any test at all without hardware.

**Proposed fix:**
- Add unit tests that mock the HTTP layer (`unittest.mock.patch` on `HttpSession.request`
  or a lightweight `pytest-httpserver` fixture).
- Cover at minimum: JSON serialisation/deserialisation of every model (`from_dict` /
  `to_dict`), enum parsing helpers, error-path raising in `_base.py`, and multipart
  body construction.
- Keep integration tests as-is under the `integration` marker.
- Configure `pytest` to exclude the `integration` marker by default so `pytest` alone
  runs unit tests only.

---

### UF-9 – Python 3.8 minimum — two years past EOL

Python 3.8 reached end-of-life in October 2024. Requiring it prevents use of several
quality-of-life language features (`|` union types, `match`, improved `@dataclass`
`kw_only`, etc.) and blocks dependency upgrades that have dropped 3.8 support.

**Proposed fix:**
- Raise `requires-python` to `>=3.11` (LTS, well supported, available everywhere).
- Update `pyproject.toml` Python version classifiers accordingly.
- Remove any 3.8 compatibility shims (e.g. the dead Python 2 `urllib` fallback in
  `numeric_results.py`; see item 6 above).
- `from __future__ import annotations` can stay as good practice, but explicit
  `Optional[X]` can be replaced with `X | None`.

---

### UF-10 – No CI pipeline; publish is an empty local PowerShell script

There is no GitHub Actions (or other CI) workflow file in the repository.
`publish-python.ps1` exists but is empty. There is no automated gate on PRs, no test
run, and no publish-on-tag automation.

**Proposed fix:**
- Add `.github/workflows/ci.yml` that runs `ruff`, `mypy`, and `pytest` (unit tests
  only, no hardware required) on every push and pull request.
- Add `.github/workflows/publish.yml` that builds and uploads to PyPI on a `v*` tag
  push, using a stored `PYPI_TOKEN` secret (replacing the `.pypi-token` plaintext file).
- Remove or gitignore `.pypi-token` — a plaintext token must not be committed.

---

### UF-11 – No `uv` integration (no `uv.lock`, no `.python-version`)

The project uses a plain `.venv` with no lockfile and no pinned interpreter version.
Reproducible installs are not guaranteed across machines or CI runners.

**Proposed fix:**
- Add `.python-version` pinning the exact CPython version (aligns with UF-9 target).
- Add `uv.lock` (committed) for reproducible dev installs (`uv sync`).
- Update `pyproject.toml` dev tooling instructions and `README.md` getting-started
  section to use `uv` commands.
- The `.venv` folder should remain gitignored (already is via `.gitignore`).

---

### UF-12 – `@dataclass` class-variable bug causes unintended state sharing between instances *(duplicate of item 1, confirmed)*

See item **1** above. Promoted here to user-feedback priority because this is a
correctness bug, not just a style issue: any code path that reads a `ChannelDto`,
`AppLicenseDto`, etc. attribute without first going through `from_dict` / `__init__`
will observe the shared class-level default, not an instance default. This includes
`dataclasses.fields()`, `dataclasses.asdict()`, and direct attribute access on an
uninitialized subclass.

**Action:** Fix tracked under item 1. This entry exists to record the feedback
severity — this is a **❌ correctness bug**, not a ⚠ warning.

---

### UF-13 – `HttpSession` thread-safety claim is incorrect — `threading.Lock` missing *(confirmed bug)*

See UF-2(a) above. `HttpSession._conn` is read and written across `_connect`,
`request`, and `_close_conn` with no synchronisation. A second thread entering
`request` while the first is inside `getresponse()` can:
- See `_conn is not None` and call `_conn.request()` on an in-flight connection.
- Race on `_close_conn` after an `OSError`, setting `_conn = None` while the other
  thread is about to call `getresponse()`.

**Proposed fix (minimal):** Add `self._lock = threading.Lock()` in `__init__` and
wrap the body of `request` (from `_connect` through `resp.read()`) with
`with self._lock:`. Document that the lock serialises requests, so callers needing
true parallelism should use separate client instances.

---

### UF-14 – Optional TLS certificate validation (`verify` parameter)

See UF-2(c) above. Promoted as a standalone item because it is independently useful
even without authentication. Embedded Linux devices commonly use self-signed
certificates; users must be able to pass `verify=False` or `verify="/path/to/ca.pem"`
without monkey-patching the SSL context themselves.

**Proposed fix:** Accept `verify: bool | str = True` in `AccordionQ2Client.__init__`
and forward it to `HttpSession._connect`:
- `verify=True` → `ssl.create_default_context()` (current behaviour, unchanged).
- `verify=False` → context with `check_hostname=False`, `verify_mode=CERT_NONE`.
- `verify="path"` → `ssl.create_default_context(cafile="path")`.

---

# Changelog

All notable changes to this project are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/).

---

## [2.0.0] – unreleased

### Breaking changes

- **Python ≥ 3.11 required.** Support for Python 3.8, 3.9, and 3.10 is dropped.
- **DTO classes are now immutable (`frozen=True`).** Mutating a field on a returned DTO
  (e.g. `channel.alias = "x"`) now raises `dataclasses.FrozenInstanceError`. DTOs
  should be treated as read-only API snapshots; construct a new instance if you need
  different values.
- **`PhysicalSystemDto.modules` is now a `tuple` instead of a `list`** (consistent with
  immutability).
- **`NumericResultChannelDto.possible_target_names` is now a `tuple` instead of a `list`.**

### Added

- `AccordionQ2Client` now accepts optional parameters:
  - `auth: tuple[str, str]` — HTTP Basic Auth credentials.
  - `verify: bool | str` — TLS certificate verification (`True` = system CA bundle,
    `False` = disable, `str` = path to CA bundle file). Useful for self-signed certs
    on embedded devices.
  - `default_headers: dict[str, str]` — merged into every request (e.g. API keys).
- `threading.Lock` added to `HttpSession` — concurrent calls from multiple threads no
  longer race on the shared connection.
- All public models, enums, and exceptions are now re-exported from the top-level
  `accordionq2` package. No need to import from internal submodules.
- Full PEP 484 type annotations on every public method and dataclass field.
- 82 unit tests covering models, transport, error handling, and group methods — no
  hardware required. Running `pytest` (without flags) executes unit tests only.
- `pyproject.toml`: `ruff` + `mypy` configuration added.
- `.pre-commit-config.yaml` with `ruff` (lint + format) and `mypy` hooks.
- `.python-version` pinned to `3.11`.
- `.github/workflows/ci.yml` — automated lint, type-check, and unit-test on every push
  and pull request.
- `CHANGELOG.md` (this file).

### Fixed

- **`@dataclass` misuse in six model classes** (`ConnectionStatusDto`, `AppLicenseDto`,
  `ModuleSettingsDto`, `PhysicalModuleDto`, `PhysicalSystemDto`, `ChannelDto`): bare
  class-level assignments replaced with annotated field declarations; hand-written
  `__init__` methods removed. Previously, `__repr__`, `__eq__`, and
  `dataclasses.fields()` returned empty/useless results for these classes.
- **`ChannelLookupRequest` and `ChannelConfigRequest`** converted to proper
  `@dataclass` — `__repr__` and `__eq__` now work correctly.
- **`channels.get_channel`** no longer duplicates `ChannelLookupRequest.to_dict()`
  logic inline.
- **`resources.get_value` and `resources.transact`** now accept both `"value"` and
  `"Value"` response keys, and raise a clear `AccordionQ2ApiError` if neither is
  present.
- **Double-slash in request paths** when `base_url` has no path suffix is now
  prevented.
- **Multipart filename encoding** now uses RFC 5987 (`filename*=UTF-8''…`) so filenames
  containing spaces or non-ASCII characters are transmitted correctly.
- **Error response parsing** now checks `"message"`, `"detail"`, and `"title"` in
  addition to `"error"` / `"Error"`, covering ASP.NET `ProblemDetails` responses.
- **Dead Python 2 `urllib` fallback import** removed from `numeric_results.py`.
- **`enums.py`**: duplicate hand-maintained name→value tables replaced with
  enum-member-referenced dicts — new `ChannelTypes` or `DirectionTypes` members no
  longer require a parallel manual edit.

### Changed

- `pyproject.toml`: `license` corrected to `{text = "LicenseRef-Proprietary", file = "LICENSE.md"}`.
- `pyproject.toml`: OS and Python version trove classifiers added (Linux, macOS, Windows).
- `pyproject.toml`: `pytest` default run now excludes `integration` and `performance`
  markers — `pytest` alone is safe without hardware.
- `setuptools` minimum bumped to `>=69` (required for PEP 639 license support).

---

## [1.2.0] – previous release

Initial public release. Synchronous stdlib-only client covering resources, channels,
modules, application, media, connection, comm (I2C/UART/SPI/Socket), and
numeric-results API groups.

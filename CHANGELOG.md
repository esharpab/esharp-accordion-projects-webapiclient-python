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

- The control lease (accordionq2 contract section 5.5): `client.lease.get/acquire/renew/release`,
  and `with client.lease.hold(owner):`, which renews in the background and releases after the
  block. The holder's requests carry `X-Lease-Id`; other clients' changes raise 423.
- The event stream and value subscriptions (accordionq2 contract sections 4 and 5.3):
  `client.events.open()` (an `EventStream` with `stream_id`, on a connection of its own, with
  the 30 s silence limit) and `client.subscriptions.create/update/delete`.
- Reads with a maximum age (contract section 5.2): `resources.get_values(names, max_age_ms=…)`
  and `resources.read_values(...)`, which also returns each value's age.
- `client.instruments.get_all()` returns the station's instruments (`InstrumentDto`: type,
  group, and the function map naming the channel behind each capability).
- `ChannelDto.details`: the fields of the channel's own type (gain, input configuration,
  push/pull, a multiplexer's destination nets, ...), read-only, keyed as the WebApi sends them.
- `ChannelConfigRequest.details` changes those fields, e.g. `details={"gain": 2.0}`.
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

- **A failed request is no longer sent again when that could run it twice on the station.**
  `HttpSession` used to resend any request once after any error, including a timeout after
  the WebApi had already received it, so a value write, bus transaction or EEPROM command
  could run twice. Now GET, HEAD and OPTIONS are retried on any error; every other request
  only when sending failed on a reused connection (it never reached the server). The reads
  sent as POST count as "every other", because reading a byte stream consumes it. A
  timeout or a dropped connection after sending raises, and the caller decides.
  Connections idle for over `IDLE_REOPEN_SECONDS` (60 s; the WebApi closes them after
  120 s) are reopened before use, so the stale-connection case stays rare.
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

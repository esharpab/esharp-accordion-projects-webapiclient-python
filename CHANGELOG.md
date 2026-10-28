# Changelog

All notable changes to this project are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/).

---

## [7.0.0] – 2026-10-28

Secured stations (FW7 CLI-01): an API key, HTTPS with a pinned certificate, and IPv6 addresses.
`accordionq2` 7.0.0 matches AccordionQ2.WebApiClient 7.0.0 and Accordion firmware 7.

### Compatibility with 5.x

The major version follows the firmware; for most code 7.0.0 is a drop-in upgrade.

- **Code that ran against 5.28 runs unchanged.** Every call, argument and return type is the same;
  `api_key` and `cert_sha256` are new optional keyword arguments, and without them the client
  sends exactly what 5.28 sent. Python 3.11 or later, as before.
- **Existing error handling keeps working.** `AccordionQ2SecurityError` (a 401/403) is an
  `AccordionQ2ApiError`, and `AccordionQ2CertificateError` is an `ssl.SSLCertVerificationError`,
  so `except AccordionQ2ApiError` and `except ssl.SSLError` still catch them.
- **Every firmware works.** Against firmware 6.x, or a firmware 7 station whose security mode
  is `Off` (the default), the client behaves as 5.28. Firmware 6.x ignores a key sent to it.
- **What can break** (see Breaking changes below): a base URL that isn't absolute `http(s)://`
  with a host, or carries a user name/password; two `X-Api-Key` entries in `default_headers`; code
  that matched a 401's message text or expected a 3xx body. None of these happen against a
  station, which never redirects.

### Breaking changes

- **A base URL must be an absolute `http://` or `https://` URL with a host**, or the constructor
  raises `ValueError`. One with a user name or password in it is refused too (they used to be
  ignored): send the key with `api_key`.
- **A 3xx answer raises `AccordionQ2ApiError`.** The station's API never redirects, and the client
  doesn't follow one; it used to return the redirect's body.
- **An `X-Api-Key` in `default_headers` is handled as the API key.** Without `api_key` it becomes the
  key, with the same checks (a key a header can't carry raises `ValueError`) and protections (it is
  withheld from server text, and a 401 is `INVALID_API_KEY`); with `api_key` it is dropped. Two of
  them in different cases raise `ValueError`. `HttpSession.default_headers` no longer lists it, in
  either case. With `api_key`, an `X-Api-Key` set later with `set_default_header`, in any case, is
  replaced on each request rather than sent as a second header.
- **A 401 raises `AccordionQ2SecurityError`** (see Added) whose message is the client's own (no key,
  or a key the station doesn't accept), followed by the server's error text as `(station: ...)`. It
  used to be a plain `AccordionQ2ApiError` with only the server's text.

### Added

- `AccordionQ2Client(..., api_key=...)`: the station API key, sent as `X-Api-Key` on every request,
  the event stream included. It replaces an `X-Api-Key` in `default_headers`. A key with characters
  a header can't carry raises `ValueError`. The key is never put in an exception message or a
  `repr()` (`repr(client)` shows `api_key=set`), and server text that would repeat it is withheld.
  The client holds it as a `str` whose `repr()` is `'<api key>'`, so a traceback that shows local
  variables doesn't show it in the client's frames (`http.client`'s frames still hold the request
  bytes; docs/security.md says so). `repr()` of a client whose constructor raised no longer raises.
- `AccordionQ2Client(..., cert_sha256=...)`: pin the station's HTTPS certificate by its SHA-256
  fingerprint, with or without colons, spaces or dashes, in either case. Exactly that certificate
  is accepted, self-signed or reached by IP address; any other raises `AccordionQ2CertificateError`
  (an `ssl.SSLCertVerificationError`, with `expected` and `actual`) right after the handshake,
  before the request (and so the key) is sent, on the event stream too. A pin with an `http://`
  URL or together with a CA bundle in `verify` raises `ValueError` rather than being ignored. A
  pinned certificate's validity dates aren't checked, as in the .NET client.
- `AccordionQ2SecurityError`, a subclass of `AccordionQ2ApiError`, for a 401 and for a 403 that
  names a role, from requests and the event stream: `reason` (`AccordionQ2SecurityReason`:
  `MISSING_API_KEY`, `INVALID_API_KEY`, `ROLE_TOO_LOW`) and `required_role`. A 403 without a role
  (a read-only folder) stays a plain `AccordionQ2ApiError`.
- `client.capabilities.get()`: `CapabilitiesDto` with `api_version`, `webapi_version`,
  `codec_version`, `features`, `has(feature)` and `security_mode` (`"Off"`, `"Report"`, `"On"`).
  It needs no API key; a WebApi without it (404) gives `CapabilitiesDto()`.
- IPv6 addresses in base URLs, in brackets, with a zone id as `%eth0` or RFC 6874's `%25eth0`:
  `http://[::1]:5000`, `http://[fe80::1%eth0]:5000`. As in the .NET client, `%25` followed by more
  is the RFC 6874 form (`%2512` is zone 12) and `%25` alone is zone 25; an empty zone is refused.
  Over HTTPS the zone is left out of TLS, so no IP address goes out as the server name (SNI).
- `accordionq2.normalize_sha256(fingerprint)` and `sha256_of(certificate)` (DER bytes or PEM text
  with one certificate: a PEM chain raises `ValueError`).
- docs/security.md: modes, keys, roles, pins, a site CA, IPv6. The plain-`http://` key crosses the
  network in clear text, which the docs say wherever they show it. `verify=<CA bundle>` (a site
  CA) is documented as what it does: the certificate must chain to that CA, match the host name
  and be meant for TLS servers (serverAuth).
- Unit tests against HTTP and HTTPS servers on the loopback interface (tests/unit/test_tls.py),
  with test certificates in tests/unit/data/tls.

### Fixed

- A certificate the client refuses is no longer tried a second time for a GET.

---

## [5.28.1] – 2026-10-03

From this release the Python and the C# client (AccordionQ2.WebApiClient on NuGet) share a version
number: `accordionq2` 5.28.1 covers the same API as AccordionQ2.WebApiClient 5.28.1. The entries
below gather everything since 1.2.0, released over the 2.0 and 5.x versions on PyPI.

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

- The hardware app's start-up configuration, boot.config (accordionq2 contract section 11):
  `client.system.boot.get()`, `set_startup(enabled, alias_files)` and `update(...)`, with
  `if_modified` (409 instead of overwriting another edit) and the Wi-Fi password kept unless
  `wifi_password` is given.
- Firmware updates (accordionq2 contract section 12): `client.firmware.get_state()`,
  `get_releases(include_beta=False)`, `set_source`, `start_update`, `get_update`, `get_update_log`,
  `wait_for_update` and `install` (which poll through the station's restart), and
  `upload_package`, `install_package` and `delete_package` for a station without internet. The
  station installs only releases signed by E-Sharp, from 6.0.0 on.
- The station's services, reboot and clock (accordionq2 contract section 9): `client.system.get_services()`,
  `service_action(id, action)`, `reboot()`, `get_clock()` and `set_clock(utc=None, force=False)`.
- Files in the station's own folders (accordionq2 contract section 10): `client.files.get_roots()`, `list`,
  `download`, `upload`, `create_folder`, `move` and `delete`.
- `numeric_results.acquire(channel, target, samples, lsl=, usl=)`: the samples and their
  statistics in one call (accordionq2 contract section 8), as a `NumericAcquisition`.
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

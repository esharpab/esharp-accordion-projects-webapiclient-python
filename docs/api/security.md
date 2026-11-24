# Security: Logins, Users, Keys, Certificate, Event Log, Firewall, Extensions, Factory Reset

> `client.security` (library 7.5.0, firmware 7.1.0): everything under `/api/security`. Logins give a token the client then sends as `Authorization: Bearer`; the rest is Admin.

A station before firmware 7.1.0 answers these calls 404 (401 or 403 in security mode `On`). Check `client.capabilities.get().has(...)` with `CapabilitiesDto.SECURITY_LOGIN`, `SECURITY_EVENTS`, `SECURITY_HOST`, `SECURITY_EXTENSIONS` or `SECURITY_FACTORY_RESET` first if a script must work against older stations.

Everything here is **Admin** (in mode `Off` that is anyone), except the logins: `login`, `me` and `claim` need nothing, `renew`, `logout` and `change_password` need a login. Nothing here needs the [lease](lease.md).

Calls that carry a password or a private key (`login`, `claim`, `change_password`, `create_user`, `set_user_password`, `install_certificate`) raise `ValueError` **before sending** when the base URL is `http://` to another host: the station refuses them over plain HTTP anyway (400), but only after the secret has crossed the network in clear text. Use `https://` with a [pinned certificate](../security.md#https-with-a-pinned-certificate), or run on the station itself.

Fields are kept as the station sends them: times as ISO 8601 strings, roles and modes as `str` (compare with `StationRole.ADMIN`, `SecurityMode.ON`, which are `StrEnum`s).

## Logins

```python
import getpass
from accordionq2 import AccordionQ2Client

with AccordionQ2Client("https://station-12:5001", cert_sha256="3F:A2:7C:...:9C") as client:
    login = client.security.login("anna", getpass.getpass())
    print(f"Signed in as {login.user.name} ({login.user.role}) for {login.expires_in} s")
    client.resources.get_value("Engine.Uptime")    # sent with Authorization: Bearer
    client.security.renew()                        # before expires_in runs out
    client.security.logout()
```

| Method | Returns | Description |
|--------|---------|-------------|
| `login(name, password, *, use=True)` | `LoginResponse` | `POST /api/security/login`. With `use`, the client sends the token from then on. A wrong name or password: `AccordionQ2SecurityError` 401 with reason `LOGIN_REFUSED`; too many: `AccordionQ2ThrottledError` 429 |
| `renew()` | `LoginResponse` | `POST /api/security/token/renew`: a new token for the same login, until 12 hours after it; the client sends the new one. 401 `LOGIN_REFUSED` after that: log in again. `RuntimeError` when the client has no token |
| `logout()` | &mdash; | `POST /api/security/logout`: this token and every token renewed from the same login stop working. The client stops sending it even when the station can't be reached. A token the station no longer accepts (401: expired, already logged out) is no error, so `logout()` in a `finally` after a long idle doesn't hide the script's own exception |
| `me()` | `MeInfo` | `GET /api/security/me`: the mode, whether the station is claimed, who this client is (`caller`: a key or a login, or `None`), whether logins work |
| `claim(password, name=None, *, use=True)` | `LoginResponse` | `POST /api/security/claim`: the first admin of an unclaimed station in mode `Off` or `Report` (`name` defaults to `admin` on the station). In `On` 409: an unclaimed station is claimed there with the recovery drive (`recovery_reset_admin`) |
| `sign_out_all()` | &mdash; | `POST /api/security/sessions/sign-out-all` (Admin): every login token on the station ends, this client's own too; API keys stay |
| `change_password(current_password, new_password)` | `LoginResponse` | `PUT /api/security/password`: this login's own password (12 to 128 characters). The user's other logins end; the client sends the new token. A wrong current password: 401 `LOGIN_REFUSED`, and the login stays valid |

`LoginResponse` has `token` (never shown by `repr()`), `expires_at` (the station's clock), `expires_in` (seconds from the answer; time the token by this, on your own clock) and `user` (`UserInfo`). A token lasts 15 minutes.

The token can also be given to the constructor (`AccordionQ2Client(..., bearer_token=token)`) or set later with `client.security.use_token(token)` (`None` stops sending one; `has_token` tells whether one is sent); the client holds it like the API key: `repr()` shows `bearer_token=set`, a traceback with local variables shows `'<login token>'`, server text that repeats it is withheld. If the client has an API key as well, the station goes by the key; `renew()`, `logout()` and `change_password()` are sent without it (token only), so they act on the login.

In `On` the station ends an [event stream](events.md) when the credential it was opened with stops working: for a login, at that token's expiry even after a renewal. Reopen the stream with the renewed token.

## Users

| Method | Returns | Description |
|--------|---------|-------------|
| `get_users()` | `list[UserInfo]` | `GET /api/security/users`, never passwords |
| `create_user(name, role, password)` | `UserInfo` | `POST /api/security/users`. 409 for an admin on an unclaimed station: the claim (mode `Off` and `Report`), the recovery drive or an admin key in `On` make the first admin |
| `set_user_password(user_id, password)` | &mdash; | `PUT /api/security/users/{id}/password`: that user's logins end everywhere |
| `set_user_role(user_id, role)` | `UserInfo` | `PUT /api/security/users/{id}/role`; 409 for the last admin user while the station has no admin API key (every mode) |
| `remove_user(user_id)` | &mdash; | `DELETE /api/security/users/{id}`: their logins end at once; 409 for the last admin user while the station has no admin API key |

## The mode, API keys and the certificate

| Method | Returns | Description |
|--------|---------|-------------|
| `get_state()` | `SecurityState` | `GET /api/security`: `mode`, `keys`, `users`, `claimed`, `throttled` (clients blocked now, `None` for none), `extension_uploads_until`, `module_image_role`, `extension_check` |
| `set_mode(mode)` | `SecurityState` | `PUT /api/security/mode`: `Off`, `Report` or `On`; `warnings` lists what to check. `On` needs an admin key or login, HTTPS on the station, and this request over HTTPS or on the station |
| `create_key(name, role)` | `CreatedApiKey` | `POST /api/security/keys`: `key` is shown this once only (never by `repr()`); `warnings` when it was issued over plain HTTP |
| `revoke_key(key_id)` | &mdash; | `DELETE /api/security/keys/{id}` |
| `get_certificate()` | `CertificateInfo` | `GET /api/security/certificate`: `sha256` is what `cert_sha256` pins; `warnings` when it has expired or expires within 30 days (firmware 7.1.0); `default_request_names` |
| `install_certificate(certificate_pem=None, private_key_pem=None, *, pfx=None, password=None)` | `CertificateInfo` | `PUT /api/security/certificate`: PEM (leaf and intermediates, and the key) or PKCS#12 bytes. Open TLS connections are closed: give pinned clients the new fingerprint |
| `remove_certificate()` | `CertificateInfo` | `DELETE /api/security/certificate`: the self-signed one serves again |
| `regenerate_certificate(extra_names=None)` | `CertificateInfo` | `POST /api/security/certificate/regenerate`: a new self-signed certificate, a new fingerprint |
| `request_certificate(names=None)` | `CertificateRequest` | `POST /api/security/certificate/request` (firmware 7.1.0): a new key made on the station, which never leaves it, and the CSR for your CA (`csr_pem`); no names: the station's `default_request_names`. It replaces a pending request |
| `get_certificate_request()` | `CertificateRequest` or `None` | `GET /api/security/certificate/request`: the pending request (names, `created`, `csr_pem`; never the key); `None` when none is pending |
| `delete_certificate_request()` | &mdash; | `DELETE /api/security/certificate/request`: the pending request and its key are deleted |
| `install_signed_certificate(certificate_pem)` | `CertificateInfo` | `PUT /api/security/certificate` with the certificate the CA signed for the pending request (leaf and intermediates, PEM) and no key: it serves as the site certificate and the request is used up; 400 when it isn't the pending request's |

Your own CA without a private key leaving the station:

```python
request = client.security.request_certificate()          # the station's default names
open("station-12.csr", "w").write(request.csr_pem)        # give it to the CA
# ... the CA issues station-12.cer (PEM, with its chain)
installed = client.security.install_signed_certificate(open("station-12.cer").read())
print(installed.sha256)
```

The certificate calls need HTTPS or the station itself: over plain HTTP from another host the station answers 400.

## The security event log

| Method | Returns | Description |
|--------|---------|-------------|
| `get_events(tail=200, since=None, kinds=None)` | `SecurityEvents` | `GET /api/security/events`: newest first, at most `tail` (1 to 5000), optionally since a time (ISO 8601 string or aware `datetime`) and of some kinds (`["LoginFailed", "Throttled"]`); with `max_age_days`, `max_bytes` and `oldest` |

```python
for event in client.security.get_events(tail=20, kinds=["LoginFailed"]).events:
    print(event.time, event.client, event.data)
```

## The firewall

| Method | Returns | Description |
|--------|---------|-------------|
| `get_host()` | `HostSecurity` | `GET /api/security/host`: the settings, the firewall's state (`NotApplied`, `Applied`, `Failed`, `Unsupported`), the ports opened in `On`, `warnings` |
| `set_host(settings)` | `HostSecurity` | `PUT /api/security/host` with a `HostSettings(xvc_ports, xvc_from)`: stored in every mode, applied at once in `On` |

In `On` the firewall drops connections that other hosts make to ports containers publish on the station.

## Extensions and module images

| Method | Returns | Description |
|--------|---------|-------------|
| `get_extensions()` | `ExtensionsReport` | `GET /api/security/extensions`: the release checked against, each folder of hw/additional with its state (`Signed`, `Accepted`, `Unsigned`, `Changed`, `Unverified`) and digest, and modules loading from outside it |
| `accept_extension(folder, digest)` | `(ExtensionFolder, list[str])` | `POST /api/security/extensions/accept` with the digest read from `get_extensions()`; 409 when the folder changed since |
| `withdraw_extension(folder)` | &mdash; | `DELETE /api/security/extensions/accept?folder=...`; 404 when it isn't accepted |
| `set_extension_uploads(minutes)` | `(str \| None, list[str])` | `PUT /api/security/extension-uploads`: open the file API's changes to the extensions folder in `On` for 1 to 1440 minutes, or close (0); until when, and warnings |
| `set_module_image_role(role)` | `(str, list[str])` | `PUT /api/security/module-images`: `Admin` (default) or `Operator` for module images in `On` |

## The recovery drive

For a station whose admin password is lost, by someone at the station (firmware 7.1.0). No credential is needed: the drive proves physical access, and the secret this client keeps proves that it made the drive. The client makes the drive, not the station.

| Call | Returns | What it does |
|---|---|---|
| `get_recovery()` | `RecoveryWindow \| None` | `GET /api/security/recovery`: `is_open` while a recovery drive for this station is in it (until 24 hours after the drive was made, until it is taken out, one reset per insertion), `until`, `usb_ports_off` (the drive then needs a restart of the station), `hint`, `steps`, `station` (the name a drive must carry), `created` (when the drive in the station was made) and `why` it is closed (such as `Outdated` for a drive made by an earlier firmware build, `Expired` after 24 hours); `None` before 7.1.0 |
| `make_recovery_drive(station, now=None)` | `bytes` | Made here, without a call: `accordion-recovery.json` for the top folder of a FAT32 or exFAT USB drive (`kind`, `station`, `created`, `hash`; never the secret). The drive's random 32-byte secret stays in `recovery_key` |
| `save_recovery_key(path)`, `load_recovery_key(path)` | &mdash;, `RecoveryDriveKey` | Write or read `recovery_key` in a file you choose (JSON with the secret: keep it where only you can read it), to reset from another process |
| `recovery_reset_admin(password, user=None)` | `RecoveryReset` | `POST /api/security/recovery/reset-admin` without the key or the token, over HTTPS or on the station, with the secret of `recovery_key`: *user* (default `admin`) gets the password, is made Admin (made if missing) and its logins end; the mode, the keys and the other users stay. `ValueError` without a `recovery_key` (nothing is sent). 409 when no recovery drive is in the station, 403 when the drive was made by another client or browser (counted like a wrong password; 429 after several), 400 for a password the station refuses. This client doesn't log in |

The hash is `recovery_drive_hash(secret, station, created)`: the lower-case hex SHA-256 of the secret's bytes, a 0x00 byte, the station's name in upper case, a 0x00 byte and `created` as the file carries it (`2026-11-24T08:00:00Z`). The station, the Web UI and the .NET client compute the same. A drive opens the recovery window until 24 hours after `created`, on the station's clock (`created` may be up to an hour ahead of it).

```python
window = client.security.get_recovery()
with open("E:/accordion-recovery.json", "wb") as f:   # the top folder of a FAT32 or exFAT USB drive
    f.write(client.security.make_recovery_drive(window.station))
client.security.save_recovery_key("recovery-key.json")  # optional: to reset from another process
# plug the drive into the station (restart the station with it in when its USB ports are off), then:
window = client.security.get_recovery()
if window is not None and window.is_open:
    client.security.recovery_reset_admin(new_password)
client.security.login("admin", new_password)
```

## The factory reset

| Method | Returns | Description |
|--------|---------|-------------|
| `factory_reset_preview()` | `FactoryResetPreview` | `GET /api/security/factory-reset/preview`: what would be erased and kept (counts only), and `host_name` |
| `factory_reset(confirm, erase_calibration=False)` | `FactoryResetStarted` | `POST /api/security/factory-reset` with the host name typed to confirm. 202: the station erases its data, reboots, and comes back in mode `Off`, unclaimed, on DHCP, with a new certificate. 400 for a wrong name, 409 while an update runs or the lease is held, 501 off a station |
| `last_factory_reset()` | `FactoryResetRecord \| None` | `GET /api/security/factory-reset`; `None` when the station has none |

```python
preview = client.security.factory_reset_preview()
print("Erases:", ", ".join(preview.erased))
client.security.factory_reset(preview.host_name)
```

## Errors

See [Error handling](../error-handling.md): `AccordionQ2SecurityError` (401 and 403; `LOGIN_REFUSED` for a login call's own 401, `INVALID_TOKEN` for an expired or logged-out token), `AccordionQ2ThrottledError` (429 with `retry_after`), and `AccordionQ2ApiError` with the station's `error` for the rest (400, 404, 409, 501, 503 with `retry_after` while the station is busy checking passwords).

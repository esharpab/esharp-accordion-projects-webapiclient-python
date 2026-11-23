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
| `claim(setup_code, password, name=None, *, use=True)` | `LoginResponse` | `POST /api/security/claim`: the first admin of an unclaimed station (`name` defaults to `admin` on the station), with the setup code read over SSH (`cat ~/webapi/config/setup-code`), from the station's own network segment |
| `change_password(current_password, new_password)` | `LoginResponse` | `PUT /api/security/password`: this login's own password (12 to 128 characters). The user's other logins end; the client sends the new token. A wrong current password: 401 `LOGIN_REFUSED`, and the login stays valid |

`LoginResponse` has `token` (never shown by `repr()`), `expires_at` (the station's clock), `expires_in` (seconds from the answer; time the token by this, on your own clock) and `user` (`UserInfo`). A token lasts 15 minutes.

The token can also be given to the constructor (`AccordionQ2Client(..., bearer_token=token)`) or set later with `client.security.use_token(token)` (`None` stops sending one; `has_token` tells whether one is sent); the client holds it like the API key: `repr()` shows `bearer_token=set`, a traceback with local variables shows `'<login token>'`, server text that repeats it is withheld. If the client has an API key as well, the station goes by the key; `renew()`, `logout()` and `change_password()` are sent without it (token only), so they act on the login.

In `On` the station ends an [event stream](events.md) when the credential it was opened with stops working: for a login, at that token's expiry even after a renewal. Reopen the stream with the renewed token.

## Users

| Method | Returns | Description |
|--------|---------|-------------|
| `get_users()` | `list[UserInfo]` | `GET /api/security/users`, never passwords |
| `create_user(name, role, password)` | `UserInfo` | `POST /api/security/users`. 409 for an admin on an unclaimed station: only the claim, an admin key in `On` or the SSH tool make the first admin |
| `set_user_password(user_id, password)` | &mdash; | `PUT /api/security/users/{id}/password`: that user's logins end everywhere |
| `set_user_role(user_id, role)` | `UserInfo` | `PUT /api/security/users/{id}/role`; 400 when it would leave `On` without an admin |
| `remove_user(user_id)` | &mdash; | `DELETE /api/security/users/{id}`: their logins end at once |

## The mode, API keys and the certificate

| Method | Returns | Description |
|--------|---------|-------------|
| `get_state()` | `SecurityState` | `GET /api/security`: `mode`, `keys`, `users`, `claimed`, `throttled` (clients blocked now, `None` for none), `extension_uploads_until`, `module_image_role`, `extension_check` |
| `set_mode(mode)` | `SecurityState` | `PUT /api/security/mode`: `Off`, `Report` or `On`; `warnings` lists what to check. `On` needs an admin key or login, HTTPS on the station, and this request over HTTPS or on the station |
| `create_key(name, role)` | `CreatedApiKey` | `POST /api/security/keys`: `key` is shown this once only (never by `repr()`); `warnings` when it was issued over plain HTTP |
| `revoke_key(key_id)` | &mdash; | `DELETE /api/security/keys/{id}` |
| `get_certificate()` | `CertificateInfo` | `GET /api/security/certificate`: `sha256` is what `cert_sha256` pins |
| `install_certificate(certificate_pem=None, private_key_pem=None, *, pfx=None, password=None)` | `CertificateInfo` | `PUT /api/security/certificate`: PEM (leaf and intermediates, and the key) or PKCS#12 bytes. Open TLS connections are closed: give pinned clients the new fingerprint |
| `remove_certificate()` | `CertificateInfo` | `DELETE /api/security/certificate`: the self-signed one serves again |
| `regenerate_certificate(extra_names=None)` | `CertificateInfo` | `POST /api/security/certificate/regenerate`: a new self-signed certificate, a new fingerprint |

## The security event log

| Method | Returns | Description |
|--------|---------|-------------|
| `get_events(tail=200, since=None, kinds=None)` | `SecurityEvents` | `GET /api/security/events`: newest first, at most `tail` (1 to 5000), optionally since a time (ISO 8601 string or aware `datetime`) and of some kinds (`["LoginFailed", "Throttled"]`); with `max_age_days`, `max_bytes` and `oldest` |

```python
for event in client.security.get_events(tail=20, kinds=["LoginFailed"]).events:
    print(event.time, event.client, event.data)
```

## The firewall, SSH and SSH keys

| Method | Returns | Description |
|--------|---------|-------------|
| `get_host()` | `HostSecurity` | `GET /api/security/host`: the settings, the firewall's and SSH's state (`NotApplied`, `Applied`, `Failed`, `Unsupported`), the ports opened in `On`, the number of SSH keys, `warnings` |
| `set_host(settings)` | `HostSecurity` | `PUT /api/security/host` with a `HostSettings(ssh_allowed, ssh_from, xvc_ports, xvc_from)`: stored in every mode, applied at once in `On` |
| `get_ssh_keys()` | `list[SshKey]` | `GET /api/security/ssh-keys`: the `accordion` user's authorized_keys |
| `add_ssh_key(line)` | `SshKeyChange` | `POST /api/security/ssh-keys`: one authorized_keys line without options; `keys` holds the new key |
| `remove_ssh_key(key_id)` | `SshKeyChange` | `DELETE /api/security/ssh-keys/{id}`: the keys left, and a warning when that was the last one in `On` |

Whoever holds an installed SSH key gets a shell on the station: treat adding one as handing out Admin.

## Extensions and module images

| Method | Returns | Description |
|--------|---------|-------------|
| `get_extensions()` | `ExtensionsReport` | `GET /api/security/extensions`: the release checked against, each folder of hw/additional with its state (`Signed`, `Accepted`, `Unsigned`, `Changed`, `Unverified`) and digest, and modules loading from outside it |
| `accept_extension(folder, digest)` | `(ExtensionFolder, list[str])` | `POST /api/security/extensions/accept` with the digest read from `get_extensions()`; 409 when the folder changed since |
| `withdraw_extension(folder)` | &mdash; | `DELETE /api/security/extensions/accept?folder=...`; 404 when it isn't accepted |
| `set_extension_uploads(minutes)` | `(str \| None, list[str])` | `PUT /api/security/extension-uploads`: open the file API's changes to the extensions folder in `On` for 1 to 1440 minutes, or close (0); until when, and warnings |
| `set_module_image_role(role)` | `(str, list[str])` | `PUT /api/security/module-images`: `Admin` (default) or `Operator` for module images in `On` |

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

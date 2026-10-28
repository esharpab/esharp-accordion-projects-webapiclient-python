# Security: API keys and HTTPS

A station is meant for an intranet: the lab or factory network, not the internet. On that network it can ask every client for an **API key**, and serve **HTTPS** with its own self-signed certificate. This page covers both from the client's side. Both need version 7.0 or later of this library.

## Security modes

The station's security mode decides what a request without a valid key gets. `GET /api/capabilities` answers without a key and reports the mode:

| `security_mode` | What the station does |
|-----------------|-----------------------|
| `"Off"` | Checks nothing. A WebApi that predates the modes reports `"Off"` too |
| `"Report"` | Lets every request through and logs what `On` would refuse. Use it to find clients that don't send a key yet |
| `"On"` | Refuses a request without a valid key (401) or with too low a role (403) |

```python
from accordionq2 import CapabilitiesDto

caps = client.capabilities.get()
if caps.has(CapabilitiesDto.SECURITY_API_KEY) and caps.security_mode != "Off":
    print(f"This station checks API keys ({caps.security_mode})")
```

## API keys

The station's administrator makes a key for each machine (a test station, a script) with a name and a role. The key starts with `acc_` and is shown once. Pass it to the client:

```python
import os
from accordionq2 import AccordionQ2Client

with AccordionQ2Client("http://station-12:5000", api_key=os.environ["ACCORDION_API_KEY"]) as client:
    print(client.connection.get_status())
```

The client sends it as the `X-Api-Key` header on every request, the [event stream](api/events.md) included. An `X-Api-Key` in `default_headers`, in any case (the way before 7.0), is handled as the key: it is used as `api_key` when that isn't given, with the same checks and protections, and dropped when it is. With `api_key` given, an `X-Api-Key` added later with `HttpSession.set_default_header` is replaced too, so only one key is ever sent.

> **Over `http://` the key crosses the network in clear text.** Anyone who can watch the traffic between the client and the station can read it and use it. That is acceptable only on a trusted intranet segment. Once the station offers HTTPS, use `https://` with a [pinned certificate](#https-with-a-pinned-certificate).

### Redirects

The client doesn't follow HTTP redirects (`http.client` never does), so the key and the lease id go only to the host in the base URL. The station's API never redirects, so a 3xx answer raises an `AccordionQ2ApiError` with that status, usually because the base URL is wrong.

Keep the key out of source code: read it from an environment variable or a secret store. The client never logs it or puts it in an exception message or a `repr()`: `repr(client)` shows only `api_key=set`, and server text that would repeat the key is withheld. The client holds the key as a `str` whose `repr()` is `'<api key>'`, so a traceback that shows local variables (`pytest -l`, `traceback.TracebackException(capture_locals=True)`, error reporters that collect frame variables) shows `'<api key>'` in the client's own frames. Two places still show the key itself:

- In such a traceback, the frames of `http.client` beneath the client hold the request as bytes, the `X-Api-Key` line included. Don't keep those tracebacks where others can read them.
- `http.client.HTTPConnection.debuglevel = 1` prints each request, the key included, to standard output.

A key with characters a header can't carry (spaces, line breaks, non-ASCII) raises a `ValueError` in the constructor, and the message doesn't contain the key. So does a base URL with a user name or password in it: send the key with `api_key` instead.

### Roles

Each role may do what the roles below it may:

| Role | May |
|------|-----|
| `Viewer` | Read: values, channels, state, the event stream and subscriptions |
| `Operator` | Run tests: write values, configure channels, alias files, the lease, media, acquisitions |
| `Admin` | The station itself: firmware, system, boot.config, files, extensions, bus transactions, logs, keys |

The station decides which role each call needs; `GET /api/capabilities` needs none. The client reports a refusal as an [`AccordionQ2SecurityError`](error-handling.md#security-errors-401-and-403).

## HTTPS with a pinned certificate

A station's HTTPS certificate is self-signed, and you often reach the station by IP address, so normal validation would refuse it. Pin it instead, by its SHA-256 fingerprint:

```python
client = AccordionQ2Client(
    "https://station-12:5001",
    api_key=api_key,
    cert_sha256="3F:A2:7C:...:9C",
)
```

With a pin, the client accepts exactly that certificate, whatever its chain or name, and refuses every other one, publicly valid ones included. Its validity dates aren't checked either: a station's own certificate stays pinned until it is replaced, even past its expiry date (a pin checks identity, and a station's clock may be wrong). The .NET client does the same. The request then raises an `AccordionQ2CertificateError`, a subclass of `ssl.SSLCertVerificationError`, with the pinned fingerprint in `expected` and the server's in `actual`. The key isn't sent: the certificate is checked right after the TLS handshake, before any request goes out, and the request isn't tried again.

The fingerprint may be written in any of the usual forms: with or without colons, spaces or dashes, in upper or lower case. For example, `AB:CD:...` as `openssl x509 -noout -fingerprint -sha256 -in station.crt` prints it (the part after `=`), or `abcd...`. Anything other than 64 hex digits raises a `ValueError`. Get the fingerprint from the station's administrator over a channel you trust, not from the station over the network you are trying to secure. If you have the station's certificate file, `accordionq2.sha256_of(open("station.crt").read())` gives it. The file must hold that one certificate: PEM text with several (a chain, or the station's certificate with a CA after it) raises a `ValueError`, since its fingerprint would match no certificate.

When a station gets a new certificate, its fingerprint changes and the old pin stops working. That is the point of pinning: update the pin.

A pin is never ignored: `cert_sha256` with an `http://` base URL, or together with a CA bundle in `verify`, raises a `ValueError`. Don't use `verify=False` for a station's certificate: it accepts any certificate, an impostor's too.

### A site CA instead

If your site signs station certificates with its own CA, trust that CA instead of pinning each station, by passing its certificate file (PEM) as `verify`:

```python
client = AccordionQ2Client("https://station-12.lab.example:5001", verify="site-ca.pem")
```

The certificate must chain to that CA, match the host name in the URL, and be meant for TLS servers: a certificate with an extended key usage that doesn't include server authentication (for example one for client authentication or code signing) is refused. Unlike the .NET client, the file replaces the operating system's CAs rather than adding to them; to trust both, put both in the file.

## IPv6 addresses

Write an IPv6 address in brackets. A link-local address needs its zone: the interface name on Linux, or its index on Windows. Write it as `%eth0`, or as `%25eth0`, the form RFC 6874 gives for URLs:

```python
AccordionQ2Client("http://[::1]:5000")
AccordionQ2Client("https://[2001:db8::12]:5001", api_key=api_key, cert_sha256=pin)
AccordionQ2Client("http://[fe80::1%eth0]:5000")     # Linux
AccordionQ2Client("http://[fe80::1%25eth12]:5000")  # RFC 6874 form
AccordionQ2Client("http://[fe80::1%12]:5000")       # Windows: interface index
```

A zone that starts with `25` followed by more is read as the RFC 6874 form, as in the .NET client: `%2512` is zone `12`. So write Windows interface index 251 as `%25251`; `%25` on its own is index 25. Over HTTPS the zone stays out of TLS: the address goes without it, so no server name (SNI) is sent, as for any IP address.

A base URL that isn't an absolute `http://` or `https://` URL raises a `ValueError`.

## Bearer tokens

Not yet: the station doesn't issue them. An API key is the way to authenticate.

"""SHA-256 certificate fingerprints, for pinning a station's HTTPS certificate (``cert_sha256``)."""

from __future__ import annotations

import hashlib
import ssl

_SEPARATORS = frozenset(":-")
_HEX = frozenset("0123456789ABCDEF")


def normalize_sha256(fingerprint: str) -> str:
    """*fingerprint* as 64 upper-case hex digits.

    Colons, dashes and white space are ignored and either case is accepted, so
    ``AB:CD:...`` as ``openssl x509 -noout -fingerprint -sha256`` prints it
    (after the ``=``) and ``abcd...`` both work. Raises ``ValueError`` for
    anything else.
    """
    if not isinstance(fingerprint, str):
        raise TypeError("A SHA-256 fingerprint is a str of hex digits")
    digits: list[str] = []
    for c in fingerprint:
        if c in _SEPARATORS or c.isspace():
            continue
        u = c.upper()
        if u not in _HEX:
            raise ValueError("A SHA-256 fingerprint is hex digits, optionally separated by colons")
        digits.append(u)
    if len(digits) != 64:
        raise ValueError(f"A SHA-256 fingerprint has 64 hex digits; this has {len(digits)}")
    return "".join(digits)


def sha256_of(certificate: bytes | str) -> str:
    """The SHA-256 fingerprint of *certificate* (DER bytes or PEM text), as 64 upper-case hex.

    For example, the pin for a station whose certificate file you have::

        pin = sha256_of(open("station.crt").read())

    PEM text must hold exactly one certificate: a file with a chain in it (the
    station's certificate with a CA after it) raises ``ValueError``, since its
    fingerprint would match no certificate.
    """
    if isinstance(certificate, str):
        count = certificate.count("-----BEGIN CERTIFICATE-----")
        if count > 1:
            raise ValueError(
                f"The PEM text holds {count} certificates; pass only the station's own "
                "(usually the first)"
            )
    der = ssl.PEM_cert_to_DER_cert(certificate) if isinstance(certificate, str) else certificate
    return hashlib.sha256(der).hexdigest().upper()

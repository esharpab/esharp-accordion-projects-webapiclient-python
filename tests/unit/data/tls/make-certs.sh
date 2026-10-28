#!/bin/sh
# Makes the test certificates in this folder (run it here; needs openssl 3; in Git Bash
# on Windows run it as MSYS_NO_PATHCONV=1 sh make-certs.sh).
# They are for the unit tests' local HTTPS server only: the keys are public, so
# never trust any of these certificates anywhere else. Valid for 100 years (but expired.pem).
#
#   self-signed.pem  a self-signed server certificate, as a station's own (pinning tests)
#   ca.pem           a test CA, as a site CA
#   server.pem       signed by ca.pem, for TLS servers (extendedKeyUsage serverAuth)
#   client-eku.pem   signed by ca.pem, but only for TLS clients (extendedKeyUsage clientAuth)
#   expired.pem      self-signed, valid only 2020-01-01..2021-01-01 (a pin ignores the dates)
# Each *.pem has its key in *-key.pem. All name localhost, 127.0.0.1 and ::1.
set -e
DAYS=36500
SAN="subjectAltName=DNS:localhost,IP:127.0.0.1,IP:::1"
key() { openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$1"; }

key self-signed-key.pem
openssl req -x509 -new -key self-signed-key.pem -out self-signed.pem -days $DAYS \
  -subj "/CN=localhost" -addext "$SAN" -addext "basicConstraints=critical,CA:FALSE" \
  -addext "keyUsage=critical,digitalSignature" -addext "extendedKeyUsage=serverAuth"

key ca-key.pem
openssl req -x509 -new -key ca-key.pem -out ca.pem -days $DAYS -subj "/CN=accordionq2 test CA" \
  -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign"

leaf() {
  key "$1-key.pem"
  openssl req -new -key "$1-key.pem" -subj "/CN=localhost" -out "$1.csr"
  printf '%s\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=%s\nauthorityKeyIdentifier=keyid\nsubjectKeyIdentifier=hash\n' \
    "$SAN" "$2" > "$1.ext"
  openssl x509 -req -in "$1.csr" -CA ca.pem -CAkey ca-key.pem -set_serial "$3" -days $DAYS \
    -extfile "$1.ext" -out "$1.pem"
  rm "$1.csr" "$1.ext"
}
leaf server serverAuth 1001
leaf client-eku clientAuth 1002
rm ca-key.pem  # nothing else is signed with it

# expired.pem: self-signed like self-signed.pem, but valid only 2020-01-01..2021-01-01. A pin
# accepts it all the same (it checks identity, not dates), as the .NET client does.
key expired-key.pem
openssl req -new -key expired-key.pem -subj "/CN=localhost" -out expired.csr
mkdir -p ca.tmp/newcerts && : > ca.tmp/index.txt && echo 1003 > ca.tmp/serial
printf '%s\n' '[ca]' 'default_ca=x' '[x]' 'dir=ca.tmp' 'database=ca.tmp/index.txt' \
  'new_certs_dir=ca.tmp/newcerts' 'serial=ca.tmp/serial' 'default_md=sha256' 'policy=p' \
  'unique_subject=no' '[p]' 'commonName=supplied' '[ext]' "$SAN" \
  'basicConstraints=critical,CA:FALSE' 'keyUsage=critical,digitalSignature' \
  'extendedKeyUsage=serverAuth' > ca.tmp/ca.cnf
openssl ca -batch -config ca.tmp/ca.cnf -selfsign -keyfile expired-key.pem -in expired.csr \
  -startdate 20200101000000Z -enddate 20210101000000Z -extensions ext -notext -out expired.pem
rm -r expired.csr ca.tmp

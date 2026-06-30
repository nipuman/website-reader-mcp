#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CERT_DIR="${CERT_DIR:-$ROOT/certs}"
CERT_FILE="${SSL_CERTFILE:-$CERT_DIR/localhost.pem}"
KEY_FILE="${SSL_KEYFILE:-$CERT_DIR/localhost-key.pem}"

mkdir -p "$CERT_DIR"

if [[ -f "$CERT_FILE" && -f "$KEY_FILE" ]]; then
  echo "Cert files already exist:"
  echo "  $CERT_FILE"
  echo "  $KEY_FILE"
  exit 0
fi

openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "$KEY_FILE" \
  -out "$CERT_FILE" \
  -days 365 \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

chmod 600 "$KEY_FILE"

echo "Created local dev TLS files:"
echo "  $CERT_FILE"
echo "  $KEY_FILE"
echo
echo "Self-signed certs for local development only."

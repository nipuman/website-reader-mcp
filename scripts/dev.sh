#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f "$ROOT/.venv/bin/activate" ]]; then
  echo "Missing .venv. Run setup steps from README first." >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"

CERT_FILE="${SSL_CERTFILE:-$ROOT/certs/localhost.pem}"
KEY_FILE="${SSL_KEYFILE:-$ROOT/certs/localhost-key.pem}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8001}"
DEV_HTTPS="${DEV_HTTPS:-true}"

if [[ "$DEV_HTTPS" == "true" ]]; then
  if [[ ! -f "$CERT_FILE" || ! -f "$KEY_FILE" ]]; then
    "$ROOT/scripts/generate_dev_certs.sh"
  fi

  echo "Starting HTTPS dev server at https://localhost:${PORT}"
  exec uvicorn app.main:app \
    --reload \
    --host "$HOST" \
    --port "$PORT" \
    --ssl-certfile "$CERT_FILE" \
    --ssl-keyfile "$KEY_FILE"
fi

echo "Starting HTTP dev server at http://localhost:${PORT}"
exec uvicorn app.main:app --reload --host "$HOST" --port "$PORT"

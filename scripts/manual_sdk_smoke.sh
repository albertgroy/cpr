#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python3"
fi
PORT="${CPR_MOCK_PORT:-8765}"
BASE="http://127.0.0.1:${PORT}"
TMP_HOME="$(mktemp -d)"
SERVER_PID=""

cleanup() {
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  rm -rf "$TMP_HOME"
}
trap cleanup EXIT

"$PYTHON_BIN" scripts/mock_server.py "$PORT" &
SERVER_PID="$!"
sleep 0.5

export CPR_HOME="$TMP_HOME"
cat >"$CPR_HOME/config" <<EOF
server:
  endpoint: $BASE
  timeout_seconds: 5
client:
  id: 00000000-0000-4000-8000-000000000001
  locale: en-US
cache:
  dir: $TMP_HOME/cache
EOF

echo "[1/5] cpr sdk"
cpr sdk || test "$?" -eq 2

echo "[2/5] cpr git status"
cpr git status

echo "[3/5] cpr __quota"
cpr __quota || test "$?" -eq 4

echo "[4/5] cpr __timeout"
cpr __timeout || test "$?" -eq 3

echo "[5/5] danger y/N path"
printf 'n\n' | cpr sdk install java

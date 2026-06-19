#!/usr/bin/env bash
set -euo pipefail

SDKMAN_DIR="${SDKMAN_DIR:-$HOME/.sdkman}"
INIT="$SDKMAN_DIR/bin/sdkman-init.sh"

if [[ ! -f "$INIT" ]]; then
  echo "SDKMAN init not found: $INIT" >&2
  exit 2
fi

source "$INIT"

echo "[1/7] sdk"
sdk version

echo "[2/7] sdk list"
sdk list | sed -n '1,20p'

echo "[3/7] sdk list java"
sdk list java | sed -n '1,40p'

INSTALLED="$(sdk current java 2>/dev/null | awk -F' ' '/Using java version/ {print $4; exit}')"
if [[ -n "$INSTALLED" ]]; then
  echo "[4/7] sdk use java $INSTALLED"
  sdk use java "$INSTALLED"

  echo "[5/7] sdk default java $INSTALLED"
  sdk default java "$INSTALLED"
else
  echo "[4/7] sdk use java <installed-version> skipped: no installed java detected"
  echo "[5/7] sdk default java <installed-version> skipped: no installed java detected"
fi

echo "[6/7] sdk current java"
sdk current java || true

echo "[7/7] sdk install java <identifier> skipped: destructive/network manual step"

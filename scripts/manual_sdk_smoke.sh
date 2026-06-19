#!/usr/bin/env bash
# Manual SDKMAN smoke for T-001.
#
# Two parts:
#   1) Non-interactive CPR self-checks (--check-tree, --slash-parse) that the
#      script can run on behalf of a human.
#   2) Bare `sdk` exercises that prove the host has a working SDKMAN install.
#
# The interactive 7-command CPR walk-through must be done by a human in a real
# TTY (CCB sessions are not TTYs) — instructions are echoed at the end and the
# operator pastes the captured session into docs/05-验收反馈/2026-06-19-T-001-验收报告.md.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python}"

echo "=== Part A · CPR non-interactive self-checks ==="

echo "[A1/3] python -m cpr --check-tree"
"$PYTHON_BIN" -m cpr --check-tree

echo "[A2/3] python -m cpr --slash-parse '/help'"
"$PYTHON_BIN" -m cpr --slash-parse "/help"

echo "[A3/3] python -m cpr --slash-parse '/ai 帮我安装 Java 17 LTS'"
"$PYTHON_BIN" -m cpr --slash-parse "/ai 帮我安装 Java 17 LTS"

echo
echo "=== Part B · SDKMAN host exercises (bare sdk) ==="

SDKMAN_DIR="${SDKMAN_DIR:-$HOME/.sdkman}"
INIT="$SDKMAN_DIR/bin/sdkman-init.sh"

if [[ ! -f "$INIT" ]]; then
  echo "SDKMAN init not found: $INIT" >&2
  exit 2
fi

set +u
source "$INIT"
set -u

echo "[B1/7] sdk"
sdk version

echo "[B2/7] sdk list"
sdk list | sed -n '1,20p'

echo "[B3/7] sdk list java"
sdk list java | sed -n '1,40p'

INSTALLED="$(sdk current java 2>/dev/null | awk -F' ' '/Using java version/ {print $4; exit}')"
if [[ -n "$INSTALLED" ]]; then
  echo "[B4/7] sdk use java $INSTALLED"
  sdk use java "$INSTALLED"

  echo "[B5/7] sdk default java $INSTALLED"
  sdk default java "$INSTALLED"
else
  echo "[B4/7] sdk use java <installed-version> skipped: no installed java detected"
  echo "[B5/7] sdk default java <installed-version> skipped: no installed java detected"
fi

echo "[B6/7] sdk current java"
sdk current java || true

echo "[B7/7] sdk install java <identifier> skipped: destructive/network manual step"

cat <<'NEXT'

=== Part C · Interactive CPR walk-through (operator must run in real TTY) ===

CCB sessions are not TTYs, so the prompt_toolkit TUI cannot run here. Open a
real terminal and execute the 7 commands below by typing tokens / Enter inside
`python -m cpr`. Capture the session (e.g. `script` or terminal recording) and
paste the transcript into:

  docs/05-验收反馈/2026-06-19-T-001-验收报告.md  →  ## 手工冒烟记录

Steps:
  1. python -m cpr
  2. type `sdk` ↵ ; observe candidates list/install/use/default/current
  3. type `list` ↵ ; observe `java`
  4. type `java` ↵ ; observe sdk list java executes (real output)
  5. /back twice ; type `install java` ↵ ; observe dynamic identifier candidates
  6. pick an identifier with arrows + Enter ; observe `sdk install java <id>`
     stays editable; abort with /back rather than installing
  7. /clear ; /help ; /ai test ; verify slash output appears in content area

Acceptance pass condition:
  - candidate area shows real identifiers (source=dynamic) within ~1s
  - exit codes printed after each `[exit=N ok=...]` line
  - /back pops one token per press; /clear wipes display only
  - log file path printed at startup matches ~/.cpr/logs/cpr.log
NEXT

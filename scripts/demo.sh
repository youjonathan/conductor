#!/usr/bin/env bash
# scripts/demo.sh — runs one full Conductor proposal lifecycle through the CLI
# and prints the resulting Inbox + Proposals files.
#
# Mirrors test_full_cycle_code_refactor in test_e2e_smoke.py, but invoked
# through the CLI the way a real Planner/Builder session would.
#
# Usage: ./scripts/demo.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors (skip if not a TTY)
if [[ -t 1 ]]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; CYAN=$'\033[36m'; GREEN=$'\033[32m'
  YELLOW=$'\033[33m'; RESET=$'\033[0m'
else
  BOLD=""; DIM=""; CYAN=""; GREEN=""; YELLOW=""; RESET=""
fi

step() { echo; echo "${BOLD}${CYAN}» $*${RESET}"; }
cmd()  { echo "${DIM}\$ $*${RESET}"; }
note() { echo "${YELLOW}  $*${RESET}"; }

# Fresh CONDUCTOR_DIR in a temp dir; clean up unless KEEP=1
CONDUCTOR_DIR="$(mktemp -d -t conductor-demo.XXXXXX)"
export CONDUCTOR_DIR
if [[ "${KEEP:-0}" != "1" ]]; then
  trap 'rm -rf "$CONDUCTOR_DIR"' EXIT
fi

mkdir -p "$CONDUCTOR_DIR/.conductor"
: > "$CONDUCTOR_DIR/.conductor/inbox.lock"
: > "$CONDUCTOR_DIR/.conductor/proposals.lock"
echo "# Conductor Inbox"     > "$CONDUCTOR_DIR/Conductor Inbox.md"
echo "# Conductor Proposals" > "$CONDUCTOR_DIR/Conductor Proposals.md"

cd "$REPO_ROOT"
PY="python3 conductor.py"

echo "${BOLD}Conductor v1 adapter — one-cycle demo${RESET}"
echo "${DIM}CONDUCTOR_DIR=$CONDUCTOR_DIR${RESET}"

# ── T+0 — empty bus
step "1. Initial bus state (nothing yet)"
cmd "$PY state"
$PY state

# ── T+2 — Planner drafts a proposal
step "2. Planner drafts a proposal (P-001)"
cmd "$PY proposal-create --title '...' --kind refactor --executor builder --effort S --risk S --risk-note '...' < body.md"
PID=$($PY proposal-create \
  --title "Remove dead RetrieverV1 shim" \
  --kind refactor --executor builder \
  --effort S --risk S \
  --risk-note "trivial deletion" <<'EOF'
### Summary
Remove dead RetrieverV1 import shim.

### Motivation
Dead code; misleads contributors.

### Scope
- vhile/retrieval/__init__.py

### Acceptance
- pytest passes

### Evidence
- vhile/retrieval/__init__.py:23
EOF
)
note "→ $PID"

$PY inbox-append --from planner --to builder --kind scan-result --proposal "$PID" \
  <<<"Found 1 occurrence." > /dev/null

# ── T+8 — Builder reviews
step "3. Builder reviews → approved-for-human"
cmd "$PY inbox-append --from builder --to planner --kind review --verdict approved-for-human ..."
$PY inbox-append --from builder --to planner --kind review \
  --verdict approved-for-human --for-version 1 --proposal "$PID" \
  <<<"Confirmed; scope ok." > /dev/null

# ── T+11 — Planner concurs, promotes to 🟡
step "4. Planner concurs and promotes → 🟡 awaiting-jonathan"
$PY inbox-append --from planner --to builder --kind review \
  --verdict approved-for-human --for-version 1 --proposal "$PID" \
  <<<"Agree; promoting." > /dev/null
cmd "$PY proposal-set-status --id $PID --new-status awaiting-jonathan --by planner"
$PY proposal-set-status --id "$PID" --new-status awaiting-jonathan --by planner

# ── T+14 — Human approves
step "5. Human approves → 🟢 approved"
cmd "$PY proposal-set-status --id $PID --new-status approved --by human"
$PY proposal-set-status --id "$PID" --new-status approved --by human

# ── T+17 — Builder starts; hands off to Codex
step "6. Builder takes ⚙️ in-progress and hands off to Codex"
cmd "$PY proposal-set-status --id $PID --new-status in-progress --by builder"
$PY proposal-set-status --id "$PID" --new-status in-progress --by builder
HANDOFF_ID=$($PY inbox-append --from builder --to codex --kind note --proposal "$PID" \
  <<<"[Codex handoff doc per §7.2]")
note "→ handoff $HANDOFF_ID"

# ── T+34 — Codex returns
step "7. Codex returns success; Builder verifies"
$PY inbox-append --from codex --to builder --kind note --proposal "$PID" --in-reply-to "$HANDOFF_ID" \
  <<<"status: success; pr_url: https://github.com/.../1234" > /dev/null
$PY inbox-append --from builder --to human --kind review \
  --verdict approved-for-human --for-version 1 --proposal "$PID" \
  <<<"Verified; ready-to-merge." > /dev/null

# ── T+45 — Builder closes
step "8. Builder closes the loop → ✅ done"
cmd "$PY proposal-set-status --id $PID --new-status done --by builder"
$PY proposal-set-status --id "$PID" --new-status done --by builder

# ── Final state
step "9. Final bus state"
cmd "$PY state"
$PY state

step "10. Proposals file"
cat "$CONDUCTOR_DIR/Conductor Proposals.md"

step "11. Inbox file (tail)"
tail -n 40 "$CONDUCTOR_DIR/Conductor Inbox.md"

echo
echo "${GREEN}${BOLD}✓ One full cycle: 🔵 → 🟡 → 🟢 → ⚙️ → ✅${RESET}"
if [[ "${KEEP:-0}" == "1" ]]; then
  echo "${DIM}Artifacts kept at: $CONDUCTOR_DIR${RESET}"
fi

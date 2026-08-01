#!/usr/bin/env bash
# PreToolUse hook: security gate before `git commit`.
#
# Fires on every Bash command but acts only on `git commit`. Runs the
# security scanner on the STAGED files:
#   * CRITICAL findings (secrets, .env files) -> BLOCK the commit (exit 2)
#     with the findings so they can be fixed (and any exposed secret rotated).
#   * WARN-level findings are printed but never block.
#   * Non-commit commands and clean commits pass through silently.

set -euo pipefail

payload="$(cat)"

command_str="$(printf '%s' "$payload" | python3 -c '
import json,sys
try:
    d=json.load(sys.stdin)
    print((d.get("tool_input") or {}).get("command",""))
except Exception:
    print("")
' 2>/dev/null || true)"

# Only gate real `git commit` invocations.
if ! printf '%s' "$command_str" | grep -qE '(^|[;&|[:space:]])git[[:space:]]+([^;&|]*[[:space:]])?commit([[:space:]]|$)'; then
  exit 0
fi

scanner=""
for cand in \
  "$HOME/.claude/hooks/security-precommit.py" \
  "${CLAUDE_PROJECT_DIR:-$PWD}/.claude/hooks/security-precommit.py"; do
  if [ -f "$cand" ]; then scanner="$cand"; break; fi
done
[ -z "$scanner" ] && exit 0

cd "${CLAUDE_PROJECT_DIR:-$PWD}" || exit 0

report="$(python3 "$scanner" --staged --gate 2>/dev/null)" && status=0 || status=$?

if [ "$status" -ne 0 ]; then
  {
    echo "Security gate BLOCKED this commit — CRITICAL finding(s) in staged files:"
    echo
    echo "$report"
    echo
    echo "Fix via the security-tester agent: move secrets to environment"
    echo "variables, ROTATE anything exposed, unstage .env files, then retry."
  } >&2
  exit 2
fi

# Surface WARNs (non-blocking) so they're visible during the commit.
if printf '%s' "$report" | grep -q "WARN"; then
  printf '%s\n' "$report"
fi
exit 0

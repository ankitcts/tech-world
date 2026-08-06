#!/usr/bin/env bash
# PreToolUse hook: AdSense compliance gate before `git push`.
#
# Registered against the Bash tool. It fires before every Bash command but only
# acts when the command is a `git push`. For a push it runs the AdSense auditor
# in --gate mode against the project:
#   * If the project does NOT integrate AdSense  -> silent pass (exit 0).
#   * If it integrates AdSense and all blockers pass -> pass (exit 0).
#   * If it integrates AdSense and a hard blocker FAILs (no valid ads.txt or no
#     privacy policy) -> BLOCK the push (exit 2) and tell Claude what to fix.
#
# It never blocks non-push commands and never blocks non-ad projects.

set -euo pipefail

payload="$(cat)"

# Extract the command being run (tool_input.command) without requiring jq.
command_str="$(printf '%s' "$payload" | python3 -c '
import json,sys
try:
    d=json.load(sys.stdin)
    print((d.get("tool_input") or {}).get("command",""))
except Exception:
    print("")
' 2>/dev/null || true)"

# Only gate real `git push` invocations.
if ! printf '%s' "$command_str" | grep -qE '(^|[;&|[:space:]])git[[:space:]]+([^;&|]*[[:space:]])?push([[:space:]]|$)'; then
  exit 0
fi

# Locate the project and the auditor.
project_dir="${CLAUDE_PROJECT_DIR:-$PWD}"
audit=""
for cand in \
  "$project_dir/.claude/skills/adsense-compliance/scripts/audit.py" \
  "$HOME/.claude/skills/adsense-compliance/scripts/audit.py"; do
  if [ -f "$cand" ]; then audit="$cand"; break; fi
done
if [ -z "$audit" ]; then
  exit 0  # auditor not installed; don't block.
fi

report="$(python3 "$audit" "$project_dir" --gate 2>/dev/null || true)"
status="$(python3 "$audit" "$project_dir" --gate >/dev/null 2>&1; echo $?)"

if [ "$status" -ne 0 ]; then
  {
    echo "AdSense compliance gate BLOCKED this push."
    echo "The project integrates Google AdSense but is missing a hard requirement"
    echo "(a valid ads.txt and/or a privacy-policy page). Fix these before pushing:"
    echo
    echo "$report"
    echo
    echo "Use the adsense-compliance skill to resolve, then retry the push."
  } >&2
  exit 2
fi

exit 0

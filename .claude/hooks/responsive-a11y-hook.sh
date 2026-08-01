#!/usr/bin/env bash
# PostToolUse hook: responsive + WCAG-AA check on every file change.
#
# Registered against Edit|Write. After any file modification it runs the static
# responsive/a11y checker on the changed file — but only when the file is a web
# source file (html/css/scss/jsx/tsx/vue/svelte). Findings are printed so the
# agent sees and fixes them immediately as part of the same change.
#
# It never blocks (always exits 0) and stays silent for non-web files, so
# backend/docs work is not slowed down.

set -euo pipefail

payload="$(cat)"

file_path="$(printf '%s' "$payload" | python3 -c '
import json,sys
try:
    d=json.load(sys.stdin)
    ti=d.get("tool_input") or {}
    print(ti.get("file_path","") or ti.get("notebook_path",""))
except Exception:
    print("")
' 2>/dev/null || true)"

[ -z "$file_path" ] && exit 0

case "${file_path,,}" in
  *.html|*.htm|*.css|*.scss|*.jsx|*.tsx|*.vue|*.svelte) ;;
  *) exit 0 ;;
esac

checker=""
for cand in \
  "$HOME/.claude/hooks/responsive-a11y-check.py" \
  "${CLAUDE_PROJECT_DIR:-$PWD}/.claude/hooks/responsive-a11y-check.py"; do
  if [ -f "$cand" ]; then checker="$cand"; break; fi
done
[ -z "$checker" ] && exit 0

python3 "$checker" "$file_path" 2>/dev/null || true
exit 0

#!/usr/bin/env bash
# PreToolUse hook: architecture-BEFORE-build gate.
#
# Fires before Write/Edit. If the file being created/edited is APPLICATION
# SOURCE CODE and the project has no architecture docs yet, it BLOCKS the write
# (exit 2) and instructs the agent to prompt the user to create the
# architecture first (architecture-diagrams agent) before building.
#
# It deliberately does NOT block:
#   * writes to docs/architecture/** (so the architecture itself can be created)
#   * writes under .claude/** or docs/** (tooling & documentation)
#   * non-source files (config, markdown, json, yaml, css, assets, tests)
#   * projects that already have docs/architecture/architecture.md
#
# Result: the FIRST attempt to write app code in a project without architecture
# is turned into a prompt to do the architecture first — a one-time gate.

set -euo pipefail

payload="$(cat)"

file_path="$(printf '%s' "$payload" | python3 -c '
import json,sys
try:
    d=json.load(sys.stdin)
    ti=d.get("tool_input") or {}
    print(ti.get("file_path","") or "")
except Exception:
    print("")
' 2>/dev/null || true)"

[ -z "$file_path" ] && exit 0

# Project root.
root="$(git -C "$(dirname "$file_path")" rev-parse --show-toplevel 2>/dev/null \
        || echo "${CLAUDE_PROJECT_DIR:-$PWD}")"

# Already have architecture docs? Never gate.
[ -f "$root/docs/architecture/architecture.md" ] && exit 0

# Normalize the path relative to root for exemption checks.
rel="${file_path#"$root"/}"

case "$rel" in
  docs/architecture/*|docs/*|.claude/*|*/node_modules/*|node_modules/*) exit 0 ;;
esac

# Only gate real application source files.
case "${file_path,,}" in
  *.py|*.js|*.ts|*.jsx|*.tsx|*.go|*.rs|*.java|*.rb|*.php|*.c|*.cpp|*.cc|*.cs|*.vue|*.svelte|*.html|*.htm) ;;
  *) exit 0 ;;
esac

# Exempt obvious test files so scaffolding tests isn't blocked.
case "${rel,,}" in
  test/*|tests/*|*_test.*|*.test.*|*.spec.*|spec/*) exit 0 ;;
esac

# Block and instruct the agent to PROMPT THE USER.
{
  echo "ARCHITECTURE-FIRST GATE: blocked writing application code"
  echo "  ($rel) because this project has no docs/architecture/ yet."
  echo
  echo "Policy: the architecture must be designed and documented BEFORE building."
  echo "STOP and prompt the user with AskUserQuestion — offer to create the"
  echo "architecture now via the architecture-diagrams agent (C4 context +"
  echo "container diagrams, architecture.md, interactive viewer), or let them"
  echo "explicitly choose to skip the gate for this project. Do not write"
  echo "application code until docs/architecture/architecture.md exists or the"
  echo "user explicitly opts out."
} >&2
exit 2

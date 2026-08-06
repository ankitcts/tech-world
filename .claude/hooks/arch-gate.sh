#!/usr/bin/env bash
# UserPromptSubmit hook: architecture-first gate.
#
# Policy (architecture-diagrams agent):
#   * New project  -> docs/architecture/ must be created BEFORE implementation.
#   * Existing project without architecture docs -> create them as soon as the
#     first change is being made.
#
# This hook checks the current project on each prompt:
#   - Not a git repo, or docs/architecture/architecture.md exists -> silent.
#   - Repo contains source files but no architecture docs -> nudge to invoke
#     the architecture-diagrams agent before/alongside the change.
#
# It only nudges (always exits 0); the agent does the actual work.

set -euo pipefail

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

root="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"

# Architecture docs already in place? Silent.
if [ -f "$root/docs/architecture/architecture.md" ]; then
  exit 0
fi

# Does the repo contain real source files (beyond docs/config/tooling)?
has_source="$(find "$root" \
  -path "$root/.git" -prune -o \
  -path "$root/.claude" -prune -o \
  -path "$root/node_modules" -prune -o \
  -path "$root/docs" -prune -o \
  -type f \( -name '*.py' -o -name '*.js' -o -name '*.ts' -o -name '*.jsx' \
    -o -name '*.tsx' -o -name '*.go' -o -name '*.rs' -o -name '*.java' \
    -o -name '*.rb' -o -name '*.php' -o -name '*.c' -o -name '*.cpp' \
    -o -name '*.cs' -o -name '*.html' -o -name '*.vue' -o -name '*.svelte' \) \
  -print -quit 2>/dev/null)"

if [ -n "$has_source" ]; then
  cat <<'EOF'
[architecture-first] This project has source code but no docs/architecture/.
Policy: create the interactive architecture diagram + documents (C4 context &
container levels minimum) via the architecture-diagrams agent BEFORE or
alongside the change you are about to make. For a brand-new project, do it
before implementation starts.
EOF
else
  cat <<'EOF'
[architecture-first] New/empty project: per policy, create the architecture
diagram + documents first (architecture-diagrams agent) before starting
implementation.
EOF
fi
exit 0

#!/usr/bin/env bash
# UserPromptSubmit hook for the `living-docs` skill.
#
# Fires on every user prompt. When the current git working tree has uncommitted
# changes, it injects a short reminder (via stdout, which Claude Code adds to
# context) to keep CHANGELOG.md's [Unreleased] section and docs current. On a
# clean tree or outside a git repo it stays silent, so read-only Q&A is not
# nagged.
#
# It only ever nudges — it never blocks the prompt (always exits 0).

set -euo pipefail

# Not a git repo? Say nothing.
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

# Any uncommitted changes (staged or unstaged, incl. untracked)?
if [ -z "$(git status --porcelain 2>/dev/null)" ]; then
  exit 0
fi

# Has CHANGELOG.md itself been touched in this working set? If so, assume the
# author is already on it and stay quiet.
if git status --porcelain 2>/dev/null | grep -qiE 'CHANGELOG\.md$'; then
  exit 0
fi

cat <<'EOF'
[living-docs] There are uncommitted changes. Per the living-docs skill, record
any user-visible change in CHANGELOG.md under [Unreleased] (Added/Changed/Fixed/
Removed/Deprecated/Security) and update affected docs/ in the same change,
before or alongside committing. Cut a versioned release doc when releasing.
EOF
exit 0

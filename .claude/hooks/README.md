# Global hooks

These hook scripts are wired **globally** in `~/.claude/settings.json` so they
apply to every project without per-project configuration. The scripts are kept
here under version control for review and portability.

| Script | Event | Purpose |
|--------|-------|---------|
| `doc-reminder.sh` | `UserPromptSubmit` | Nudges to keep `CHANGELOG.md` `[Unreleased]` and docs current when the working tree has uncommitted changes (living-docs skill). Silent on clean trees / non-git dirs. |
| `adsense-pre-push.sh` | `PreToolUse` (Bash) | Runs the AdSense auditor before a `git push`. Blocks the push (exit 2) only when the project integrates AdSense **and** a hard blocker fails (no valid `ads.txt` or privacy policy). Non-ad projects and non-push commands pass through. |
| `arch-gate.sh` | `UserPromptSubmit` | Architecture-first gate: nudges to create `docs/architecture/` (C4 diagrams + docs via the architecture-diagrams agent) before a new project starts, or on first change to an existing project lacking them. Silent once docs exist. |
| `responsive-a11y-hook.sh` | `PostToolUse` (Edit\|Write) | After every file change to a web source file (html/css/scss/jsx/tsx/vue/svelte), runs `responsive-a11y-check.py` on the changed file and surfaces responsive + WCAG 2.1 AA findings so they are fixed in the same change. Silent for non-web files; never blocks. |
| `responsive-a11y-check.py` | (called by hook / agent) | Dependency-free static checker: viewport meta, zoom disabling, `lang`, img alt, labels, clickable divs, positive tabindex, empty controls, fixed widths, px fonts, focus outline removal, reduced-motion. |

## One-time global install

Copy the scripts and register the hooks in your user-level Claude config:

```bash
mkdir -p ~/.claude/hooks
cp .claude/hooks/doc-reminder.sh          ~/.claude/hooks/
cp .claude/hooks/arch-gate.sh             ~/.claude/hooks/
cp .claude/hooks/adsense-pre-push.sh      ~/.claude/hooks/
cp .claude/hooks/responsive-a11y-hook.sh  ~/.claude/hooks/
cp .claude/hooks/responsive-a11y-check.py ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.sh ~/.claude/hooks/*.py
```

Then merge this into `~/.claude/settings.json` (create the file if absent):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "bash \"$HOME/.claude/hooks/doc-reminder.sh\"" }, { "type": "command", "command": "bash \"$HOME/.claude/hooks/arch-gate.sh\"" } ] }
    ],
    "PreToolUse": [
      { "matcher": "Bash", "hooks": [ { "type": "command", "command": "bash \"$HOME/.claude/hooks/adsense-pre-push.sh\"" } ] }
    ],
    "PostToolUse": [
      { "matcher": "Edit|Write", "hooks": [ { "type": "command", "command": "bash \"$HOME/.claude/hooks/responsive-a11y-hook.sh\"" } ] }
    ]
  }
}
```

> Register the hooks in **one** place only. If you also add them to a project
> `.claude/settings.json`, they will fire twice in that project.

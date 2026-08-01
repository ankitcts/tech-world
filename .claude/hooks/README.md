# Global hooks

These hook scripts are wired **globally** in `~/.claude/settings.json` so they
apply to every project without per-project configuration. The scripts are kept
here under version control for review and portability.

| Script | Event | Purpose |
|--------|-------|---------|
| `doc-reminder.sh` | `UserPromptSubmit` | Nudges to keep `CHANGELOG.md` `[Unreleased]` and docs current when the working tree has uncommitted changes (living-docs skill). Silent on clean trees / non-git dirs. |
| `adsense-pre-push.sh` | `PreToolUse` (Bash) | Runs the AdSense auditor before a `git push`. Blocks the push (exit 2) only when the project integrates AdSense **and** a hard blocker fails (no valid `ads.txt` or privacy policy). Non-ad projects and non-push commands pass through. |

## One-time global install

Copy the scripts and register the hooks in your user-level Claude config:

```bash
mkdir -p ~/.claude/hooks
cp .claude/hooks/doc-reminder.sh    ~/.claude/hooks/
cp .claude/hooks/adsense-pre-push.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.sh
```

Then merge this into `~/.claude/settings.json` (create the file if absent):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "bash \"$HOME/.claude/hooks/doc-reminder.sh\"" } ] }
    ],
    "PreToolUse": [
      { "matcher": "Bash", "hooks": [ { "type": "command", "command": "bash \"$HOME/.claude/hooks/adsense-pre-push.sh\"" } ] }
    ]
  }
}
```

> Register the hooks in **one** place only. If you also add them to a project
> `.claude/settings.json`, they will fire twice in that project.

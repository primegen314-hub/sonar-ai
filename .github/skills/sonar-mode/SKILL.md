---
name: sonar-mode
description: Show or switch the sonar workflow mode (Local | GitHub) in one quick step - no need to remember set_mode.py commands. Use when the user says "switch mode", "change to github/local mode", "which mode am I in", or "sonar mode".
---

# sonar-mode `[local | github]`

The quick mode switcher. Scripts home: `.github/skills/sonar-issues/`. Never read
`.env`; the script owns all mode state.

**On any script error**: read `.github/skills/sonar-issues/RECOVERY.md` (only then) and
apply the one mapped action; unlisted errors → show verbatim, ask the user.

## Phases (mirror these as your progress/todo display)

1. Show current mode
2. Switch (only if asked)
3. Remind: re-run /sonar-init

## Steps

1. **Show**: run `python .github/skills/sonar-issues/set_mode.py --show` and present
   its output (mode, branch/repo, token state, configured/incomplete). If the user only
   asked "which mode?", stop here.

2. **Switch** — when the user named a target mode (argument or in their message), go
   straight to it; otherwise ask per the Choice Presentation Contract:
   - `[Local] (Recommended when you have a git checkout) — fixes edit your checkout
     directly; verify with /sonar-verify`
   - `[GitHub] — no checkout needed; fixes go to a scratch workspace and are pushed
     with /publish-to-github; needs a WRITE-scope token`
   - `[Stay as is] — change nothing`

   Then:
   - **→ Local**: run `python .github/skills/sonar-issues/set_mode.py local` (asks
     nothing; if there is no git repo here it says so — relay that one sentence).
   - **→ GitHub**: tell the user to run
     `python .github/skills/sonar-issues/set_mode.py github` **in their own terminal**
     (hidden token prompt; a pasted repo URL — even a `/tree/<branch>` deep link —
     works when there is no checkout; SSO orgs must authorize the token). The agent
     never handles the token. Re-check with `--show` after they confirm.

3. **Remind (always, after any switch)**: extracted trees belong to the mode they were
   extracted in — after switching, run `/sonar-init <sonar-url>` again before solving
   (re-runs are safe: `resolution.json` progress survives). Unpublished GitHub-mode
   workspace edits block a re-fetch — `/publish-to-github` first or
   `--discard-workspace`.

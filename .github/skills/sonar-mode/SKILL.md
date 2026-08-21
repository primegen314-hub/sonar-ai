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
   - **→ GitHub**: first collect the repo reference if needed (git remote, or ask for a
     pasted repo URL — a `/tree/<branch>` deep link works). Then ask about the token
     (the ONLY extra thing GitHub mode needs; Local never asks any of this):
     - `[Enter the token now] (Recommended) — run set_mode.py github in a terminal the
       user can type into (use your run-in-terminal tool so the terminal takes focus;
       the token prompt is hidden input). No interactive terminal available? Print the
       command as a copy-paste block and wait.`
     - `[Skip — set it later] — the agent runs set_mode.py github --repo-url <url>
       --no-token itself: mode/org/repo/branch are saved now, status stays INCOMPLETE,
       and extraction/publish will remind about the token when it's actually needed.`
     The agent NEVER handles or sees the token either way. Re-check with `--show`.

3. **Remind (always, after any switch)**: extracted trees belong to the mode they were
   extracted in — after switching, run `/sonar-init <sonar-url>` again before solving
   (re-runs are safe: `resolution.json` progress survives). Unpublished GitHub-mode
   workspace edits block a re-fetch — `/publish-to-github` first or
   `--discard-workspace`.

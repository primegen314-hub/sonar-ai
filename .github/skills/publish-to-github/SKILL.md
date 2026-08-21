---
name: publish-to-github
description: Publish GitHub-mode Sonar fixes to GitHub - commit the scratch-workspace changes (changes.patch) to a target branch via the GitHub REST API, after a preview and explicit confirmation. Use when the user says "publish", "push my sonar fixes", or after sonar-issues-solve finished in GitHub mode.
---

# publish-to-github `[branchRef]`

Scripts home: `.github/skills/sonar-issues/`. Never read `.env`; never read the contents
of `_workspace/` files — `publish.py` prints everything this skill needs.

GitHub-mode only. In local mode the user commits and pushes with git themselves — refuse
politely and say exactly that. Tests for GitHub-mode fixes run in CI after this publish.

How the push works (so you can explain it): `publish.py` pushes the **edited file
contents** as ONE atomic multi-file commit via the GitHub Git Data API (blob → tree →
commit → ref) — all-or-nothing, no half-published state. `changes.patch` is a review
artifact, not the push mechanism. No local git is involved at any point.

**On any script error**: read `.github/skills/sonar-issues/RECOVERY.md` (only then —
never upfront) and apply the one mapped action. Errors not listed there: show them
verbatim and ask the user — never improvise a recovery.

## Phases (mirror these as your progress/todo display)

1. Gate (mode: github)
2. Preview (dry-run)
3. Target branch
4. Confirm + push
5. Report + optional cleanup

Use the host's todo/plan tool when one exists: in VS Code Copilot agentic chat, create
these phases as todo-list items at session start and mark each completed as you finish
it (they render as green check indicators above the chat); in Claude Code use the task
list the same way. No such tool: print a one-line status at each transition.

## Choice Presentation Contract (mandatory)

Native question/choice tool available (e.g. AskUserQuestion in Claude Code) → using it
is MANDATORY for every choice. No such tool (e.g. VS Code Copilot chat — no dropdown
UI) → render exactly a numbered menu (`❓ question` / numbered options, recommended
first / `Reply with a number`), nothing after it in the same message, and wait.
FORBIDDEN: asking the user to describe their choice in prose when the options are
enumerable — that is a defect. Every menu marks exactly ONE option `(Recommended)`
listed first with a one-line why, and every option carries a one-line description of
what happens when chosen (native tools: the description field; text menus: after a
dash) — a menu missing either is a defect.

## Steps

1. **Gate**: run `python .github/skills/sonar-issues/pick_issue.py --list --branch <branchRef>`
   (no branch known → `--branches` first and let the user choose; the listing shows each
   tree's mode). Require `mode: github`:
   - `mode: local` → refuse: "publish is for GitHub mode - in local mode commit and push
     with git yourself".
   - Nothing extracted → run `/sonar-init` first.

2. **Preview**: `python .github/skills/sonar-issues/publish.py --dry-run --branch <branchRef>`
   and show its summary verbatim (repo, files + diffstat, issues covered).
   "Nothing to publish" (exit 2) → stop and point at `/sonar-issue-pick` or
   `/sonar-issues-solve`.

3. **Target branch** — ask:
   `[<analyzed branch>] (Recommended — the branch Sonar analyzed)` ·
   `[A new branch — type the name]` (created from the analyzed branch head) ·
   `[Another existing branch — type the name]`.

4. **Explicit confirmation** — ask:
   `[Push N file(s) to <org>/<repo>@<target>]` · `[Cancel]`.
   NEVER push without this confirmation. After the user confirms, ALWAYS run the script
   with `--yes` — agent terminals have no interactive stdin, so without `--yes` the
   script exits 2 by design (its message says exactly this; it is not an error in the
   changes).

5. **Run**:
   `python .github/skills/sonar-issues/publish.py --branch <branchRef> --target-branch <target> --yes`.
   Failure playbook — surface the script's message verbatim, then:
   - **Write-scope error** (403/404): the fix is a token with write access (classic:
     `repo` scope; fine-grained: Contents read/write), re-entered via
     `set_mode.py github` in the user's terminal (hidden prompt — never handle the
     token in chat).
   - **Conflict** (files changed on GitHub since extraction): offer
     `[Re-run /sonar-init and re-apply the fixes] (Recommended)` or
     `[--force overwrite]` (only if the user insists — last-write-wins).
   - **Branch moved during publish** (422): simply re-run publish.
   - **Exit 2 mentioning the confirmation prompt**: you forgot `--yes` — re-run the same
     command with `--yes` (after the user's confirmation in step 4, that is authorized).

6. **Report**: the commit URL from the script output. Remind the user Sonar clears the
   issues only after CI re-analyzes the target branch. Then offer `[cleanup]` — delete
   `SONAR_ISSUES/<branchRef>/` (safe now: `publish.json` records the push); never delete
   without the user choosing it.

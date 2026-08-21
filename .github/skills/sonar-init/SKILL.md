---
name: sonar-init
description: Initialize the Sonar issues workspace - fetch SonarQube issues for a branch into SONAR_ISSUES/{branchRef}/ folders (issue.md, issue.json, context.json, summary.json) ready for solving. Use when the user pastes a SonarQube URL, says "init sonar", "pull/list sonar issues", or wants to prepare sonar issues for fixing.
---

# sonar-init

Run the whole extraction pipeline from a pasted Sonar URL. All scripts live in
`.github/skills/sonar-issues/` (the canonical scripts home shared by every sonar skill).
The scripts decide; you execute them and act on their short output.

**On any script error**: read `.github/skills/sonar-issues/RECOVERY.md` (only then —
never upfront) and apply the one mapped action. Errors not listed there: show them
verbatim and ask the user — never improvise a recovery.

## Phases (mirror these as your progress/todo display)

1. Config (`.env` exists)
2. Mode (read or ask once: Local | GitHub)
3. Extract (`run_all.py`)
4. Report (`summary.json`)

Use the host's todo/plan tool when one exists: in VS Code Copilot agentic chat, create
these phases as todo-list items at session start and mark each completed as you finish
it (they render as green check indicators above the chat); in Claude Code use the task
list the same way. No such tool: print a one-line status at each transition
(`Phase 3/4 — extracting`).

## Phase 1 — Config

Ensure `.github/skills/sonar-issues/.env` exists. If missing, copy `.env.example` from
that same folder to `.env` (same folder — NOT the repo root; a host repo's root `.env` is
a different file and must not be touched) and ask the user to fill `SONAR_USER` (password
optional — s01 prompts interactively). Never read or print `.env` contents; credentials
flow only through the Python scripts.

## Phase 2 — Workflow mode

Run `python .github/skills/sonar-issues/set_mode.py --show`.

- Exit 0 (a mode is configured): just note it and continue — never re-ask. Offer
  switching only when the user asks for it.
- Exit 2 (no mode yet): ask ONCE — `[Local — I work in this git checkout] (Recommended)`
  or `[GitHub — no checkout, work through the GitHub API]`. Present this (like every
  choice) per the Choice Presentation Contract: native choice tool when the host has
  one (MANDATORY); otherwise an exact numbered menu ending with "Reply with a number" —
  never a prose "tell me what you'd like" ask. The menu MUST mark `Local` as
  `(Recommended)` (listed first, one-line why) and every option MUST carry a one-line
  description of what happens when chosen.
  - **Local**: run `python .github/skills/sonar-issues/set_mode.py local`. It asks
    nothing — the branch is resolved per run from the Sonar URL's `branch=` param, then
    `SONAR_BRANCH`, then the current checkout. Fixes edit this checkout directly. If the
    script reports there is no git repository here, tell the user in one sentence to open
    the project repository folder and retry — do not offer a mode switch.
  - **GitHub**: collect the repo reference (git remote when one exists, otherwise ask
    for a pasted repo URL — a `/tree/<branch>` deep link works; no checkout is ever
    required), then ask about the token (the ONLY extra info GitHub mode needs;
    WRITE access — publishing commits through the API):
    - `[Enter the token now] (Recommended) — run set_mode.py github in a terminal the
      user can type into (use your run-in-terminal tool so the terminal takes focus;
      hidden input). No interactive terminal? Print the command as a copy-paste block
      and wait for the user to confirm.`
    - `[Skip — set it later] — the agent runs set_mode.py github --repo-url <url>
      --no-token itself: mode/org/repo/branch saved now, status INCOMPLETE; the token
      is asked for only when extraction/publish actually needs it.`
    The agent never handles or sees the token either way, same rule as `.env`.
    Re-check with `--show`. Any local checkout is IRRELEVANT from here on; fixes go to
    a scratch workspace + `changes.patch`, pushed later with `/publish-to-github`.

## Phase 3 — Extract

Run from the repository root (GitHub mode: from any folder), passing the user's pasted
Sonar URL:

```
python .github/skills/sonar-issues/run_all.py "<pasted-sonar-url>"
```

Optional flags: `--branch <name>` to override the branch (default: the URL's `branch=`
param, then — local mode only — the current git branch; GitHub mode requires an explicit
branch from URL/flag/`GITHUB_BRANCH`), `--fixtures` for the offline demo,
`--discard-workspace` to drop unpublished github-mode edits when the pipeline refuses to
re-fetch over them.

**Branch gate**: the pipeline hard-errors (red message) when the branch is wrong for the
mode. Surface the error verbatim — each failure names exactly ONE remedy:

- **Sonar has no such branch** (git and Sonar name the branch differently): ask the user
  for the Sonar-side branch name (free text), run
  `python .github/skills/sonar-issues/set_mode.py --sonar-branch <sonar-name>`, re-run
  the pipeline.
- **Wrong branch checked out / out-of-sync** (local mode): the error prints the exact
  git command (`git checkout <branch> && git pull` or `git pull`). Offer to run that
  command in the terminal so the user only has to approve it (if you cannot run terminal
  commands, print it as a copy-paste block). After it runs, re-run the pipeline. Never
  suggest switching modes here.
- **Branch missing on GitHub** (GitHub mode): the error explains `GITHUB_BRANCH`;
  relay it.

**Re-runs are safe**: solve progress (`resolution.json`) is stashed and restored for
issues that still exist in Sonar. Exception: unpublished github-mode workspace edits
block a re-fetch — publish them first or pass `--discard-workspace`.

## Phase 4 — Report

Read `SONAR_ISSUES/<branchRef>/summary.json` — counts by severity/type and one line per
issue, plus the mode line: local → "fixes edit this checkout; verify anytime with
/sonar-verify"; github → "fixes go to the scratch workspace (your checkout stays
untouched), publish with /publish-to-github". Do not dump raw API responses.

Close with the next step: `/sonar-issues-solve` (batch) or `/sonar-issue-pick <n>` (one).

## Output contract (consumed by sonar-issues-solve / sonar-issue-pick)

Each `SONAR_ISSUES/{branchRef}/{NNN}_{ruleId}_{file}_L{line}/` contains:
- `issue.json` — machine contract: rule, file, `textRange`, message, severity, `sonarUrl`.
- `context.json` — solving context: `testFiles`, `usedBy`, `coChangedFiles`, `snippetRange`.
- `issue.md` — human-readable (Sonar's "why" + the rule's compliant-solution example under
  **Suggested fix**). For review, not for parsing.

---
name: sonar-verify
description: Run the project's tests to verify solved Sonar issues (full suite or scoped to one issue's tests) - always user-invoked, never automatic. Use when the user says "verify", "run the tests", "check my sonar fixes", or after finishing a /sonar-issues-solve or /sonar-issue-pick session in local mode.
---

# sonar-verify `[issue-selector]`

Scripts home: `.github/skills/sonar-issues/`. Never read `.env` — `verify.py` handles
the test command (persisted `TEST_COMMAND` or auto-detected maven/gradle/npm/pytest
runner) and prints the command before running it.

**Why this is a separate skill**: solving sessions stay fast because they never run
tests; verification happens once, here, when the user chooses. On failure the USER
decides what happens next — never start a root-cause investigation unless the user
explicitly asks for one.

**On any script error** (not test failures — those follow the menu below): read
`.github/skills/sonar-issues/RECOVERY.md` (only then — never upfront) and apply the one
mapped action. Errors not listed there: show them verbatim and ask the user.

## Phases (mirror these as your progress/todo display)

1. Resolve branch tree
2. Run tests (full, or scoped per selector)
3. On failure: user decides
4. Report + optional cleanup

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

1. **Branch**: take it from the user's message if given; otherwise
   `python .github/skills/sonar-issues/pick_issue.py --branches` — one tree: use it;
   several: let the user choose; none: nothing to verify, point at `/sonar-init`.

   **GitHub mode** (the listing shows `mode: github`): stop here and explain — the fixes
   live in the scratch workspace, not in any checkout, so there is no fixed code here to
   test (`verify.py` exits 4 by design). Verification happens after `/publish-to-github`:
   CI tests the pushed branch, or the user pulls the published branch and runs
   `/sonar-verify` there.

2. **Run**:
   - No selector (the normal case): `python .github/skills/sonar-issues/verify.py --full --branch <branchRef>`.
   - Selector given (bisecting one issue): `python .github/skills/sonar-issues/verify.py --issue <selector> --branch <branchRef>`
     (scoped to that issue's `testFiles`; exit 3 = no tests known for it — offer `--full`).
   - User asked for a quick check (or wants confidence right after a solving session
     without the full suite's cost):
     `python .github/skills/sonar-issues/verify.py --compile --branch <branchRef>` —
     compile-only, seconds: `BUILD_COMMAND`, else derived from the detected runner
     (maven `compile` / gradle `classes` / python `compileall`). Exit 3 = nothing
     derivable — the one-time setup below can set `BUILD_COMMAND`, or fall back to
     `--full`. Catches "the fix doesn't even build" without running a single test.

   **One-time test-command setup** — when verify exits 2 (no `TEST_COMMAND` configured
   and auto-detection found nothing), offer:
   - `[Let AI determine the test command] (Recommended)` — inspect the project's build
     files (package.json scripts, settings.gradle / multi-module gradle, parent pom +
     modules, Makefile, tox/nox, whatever the stack is), propose the exact command, and
     confirm it with the user.
   - `[Type the test command yourself]` — free text.
   - `[Skip verification]` — fine; it can run any time later.

   Persist the chosen command with
   `python .github/skills/sonar-issues/verify.py --set-command "<cmd>"` — NEVER edit
   `.env` directly. Every later verify reuses it; the question is never asked again.

3. **On failure** (non-zero exit): show the test output (last relevant lines, not a wall
   of text) and ask — do NOT start debugging on your own. Present the options WITH these
   short descriptions so the user knows what each will do:
   - `[Bisect per issue] (Recommended) — test each fix alone; the one that fails alone
     is the culprit. Fast: runs only that fix's own tests, not the whole suite.`
     How: run `verify.py --issue <n>` for each recently fixed issue (get them from
     `pick_issue.py --list`: status `fixed`); report the culprit and let the user decide
     (revert that fix / fix forward / keep).
   - `[Try a different test command] — the failure may be the command, not the fixes;
     set a new one (saved for next time).` How: the setup above (`--set-command`).
   - `[Investigate the failure] — let the AI read the test output and debug it now.`
     Only at this explicit request do you debug the failing test yourself.
   - `[Skip / deal with it later] — stop here; nothing gets marked as passing.`

4. **Report + optional cleanup**: pass/fail per what ran. On a pass, update each
   verified issue's `resolution.json` by filling `"testsRun"` with what was executed
   (e.g. `["full-suite"]` or the scoped test files). After a PASSING `--full` run
   (local mode), offer:
   - `[keep the SONAR_ISSUES tree] (Recommended when unresolved issues remain) — audit
     trail and progress stay on disk`
   - `[cleanup — delete SONAR_ISSUES/<branchRef>/] — everything is verified; removes
     the whole extracted tree (resolutions included)`
   Never delete without the user explicitly choosing it. Scoped runs and failures never
   offer cleanup.

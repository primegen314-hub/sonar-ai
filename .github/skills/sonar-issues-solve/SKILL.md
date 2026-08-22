---
name: sonar-issues-solve
description: Solve the extracted Sonar issues for a branch, interactively (one by one with user choices) or automated (all at once). Fast by design - no test runs during solving; verification is a separate user-invoked step (/sonar-verify). Use when the user says "solve sonar issues", "fix the sonar findings", or after sonar-init has produced SONAR_ISSUES/{branchRef}/.
---

# sonar-issues-solve `[branchRef | sonar-url]`

Scripts home: `.github/skills/sonar-issues/`. Never read `.env`; never modify anything
under `SONAR_ISSUES/` except writing `resolution.json` files (and the final cleanup
below) — and, in GitHub mode only, files under `SONAR_ISSUES/<branchRef>/_workspace/edited/`.

**Speed contract**: this skill NEVER runs tests and never debugs test failures — that is
`/sonar-verify`, invoked by the user when they choose. A solving session is: read the
pre-computed brief, apply the fix, prove the edit landed, record it, next issue.

**On any script error**: read `.github/skills/sonar-issues/RECOVERY.md` (only then —
never upfront) and apply the one mapped action. Errors not listed there: show them
verbatim and ask the user — never improvise a recovery.

## Phases (mirror these as your progress/todo display)

1. Locate tree
2. List issues
3. Session choices (interactive/automated + effort tier)
4. Fix loop (announce "issue i/N" as you go)
5. Report
6. Hand-off (/sonar-verify or /publish-to-github) + optional cleanup

Use the host's todo/plan tool when one exists: in VS Code Copilot agentic chat, create
these phases as todo-list items at session start and mark each completed as you finish
it (they render as green check indicators above the chat) — keep the fix-loop item's
text updated with the count ("fix loop — issue 3/12"); in Claude Code use the task list
the same way. No such tool: print a one-line status at each transition.

## Workflow mode (read it, never ask it)

The `--list` header and every issue printout carry a `mode:` line (local | github) — the
mode was chosen once in `/sonar-init` and is only *read* here. If `summary.json` is
missing, run `/sonar-init` first. If the user wants to switch modes, point them at
`set_mode.py` and re-run `/sonar-init` — never switch modes yourself mid-session.

- **local**: fixes edit the checkout directly.
- **github**: the checkout is irrelevant. Every fix goes through the workspace:
  `workspace.py fetch <file>` → edit the printed workspace copy → `workspace.py diff`.

## Choice Presentation Contract (mandatory)

Every choice this skill offers takes exactly one of two shapes:

1. **The host has a native question/choice tool** (e.g. AskUserQuestion in Claude Code):
   using it is MANDATORY for every choice — never present options as plain text.
2. **No such tool** (e.g. VS Code Copilot chat — it has no dropdown UI): render EXACTLY
   this menu, put nothing after it in the same message, and wait for the reply:

   ```
   ❓ <question>
     1. <option> (Recommended) — <one-line why>
     2. <option>
     3. <option>
   Reply with a number (or type your own answer).
   ```

**FORBIDDEN in both shapes**: asking the user to describe what they want in prose
("let me know how you'd like to proceed") when the options are enumerable — that is a
defect, not a style choice.

Two more MUSTs, both shapes:
- **Every menu marks exactly ONE option `(Recommended)`, listed FIRST, with a one-line
  why.** Use the pre-computed recommendation when the scripts provide one (`recommend:`
  line, `ai effort:` line, `--list` footer); when none exists, mark the sensible
  default. A menu with no `(Recommended)` marker is a defect.
- **Every option carries a one-line description of what happens when chosen** — native
  tools: put it in the option's description field; text menus: inline after a dash.

Every issue carries a pre-computed `recommend:` line (from `pick_issue.py` /
`summary.json`): **list the recommended option first, marked "(Recommended)", with its
reason** — `sonar` = apply the rule's compliant example, `ai` = the rule may not fit
this app (e.g. frontend) or has no example, so an AI fix tailored to the code is safer.
Do not spend tokens re-deriving this recommendation.

## Token economy — read exactly this, nothing more

The scripts pre-computed everything; each phase names its only allowed reads:

- **Menu/brief phase**: `pick_issue.py` output ONLY (it has file:line, severity, message,
  status, recommendation). Do NOT open issue.md, issue.json, or the source file yet.
- **Fix phase**: `issue.json` + `context.json` of the current issue, plus ONLY the
  `snippetRange` lines of the source file (not the whole file) — in GitHub mode that
  means the workspace copy (the `workspace:` line names it), never the checkout. Read
  issue.md's "Suggested fix" section only when applying the Sonar suggestion.
- **Never read**: `_raw/`, other issues' folders, `.env`, `_workspace/orig/`, or
  summary.json (pick_issue already presents it).

## Project standards (the `rules:` line)

Each `pick_issue.py` issue printout includes a `rules:` line listing the project's
instruction files it found (CLAUDE.md, .github/copilot-instructions.md, AGENTS.md,
.cursorrules, ...). Handle them ONCE at session start, not per issue:
- Skip files your host already auto-loaded (e.g. Claude Code loads CLAUDE.md itself).
- From the rest, skim only what is relevant to fixing code (style, bug-fix conventions,
  structure) and apply those standards to every fix in the session.
- `(none found)` → ask ONCE per session (never again after any answer):
  `[Paste a reference class OR name reference files (comma-separated)] · [skip] (both fine)`.
  The user may paste code directly, or answer with comma-separated file names/paths
  (e.g. `ReportService.java, BillingService.java`) — resolve each name in the repo
  (local mode: read from the checkout; GitHub mode: `workspace.py fetch <path>` first)
  and read at most 3 files, skimming for conventions only. A name that matches nothing
  or several files: say so and let the user correct it — never guess.
  Either way: extract the conventions (naming, logging, error handling,
  formatting, idioms) and follow them in every fix this session; then offer
  `[Save as instructions.md] (Recommended — future sessions pick it up automatically)`
  or `[this session only]`. Saving writes a short distilled style guide (conventions,
  not the pasted code verbatim) to `instructions.md` at the repo root — from then on
  the `rules:` line finds it and this question is never asked again. If they skip:
  proceed, no searching of your own.

## Steps

1. **Locate the tree**: resolve the branch (argument, URL `branch=` param, or — local
   mode only — the current git branch; when in doubt run `pick_issue.py --branches`,
   which also shows each tree's mode). If a pasted URL contains `open=<issueKey>` it is
   a single-issue deep link — offer `/sonar-issue-pick <key>` for that exact issue
   instead of a batch session (the user may still choose to solve all). If `SONAR_ISSUES/<branchRef>/summary.json` is
   missing, run the sonar-init pipeline first
   (`python .github/skills/sonar-issues/run_all.py ...`). Re-running is safe —
   `resolution.json` progress survives.

2. **Show the plan**: `python .github/skills/sonar-issues/pick_issue.py --list --branch <branchRef>`.

3. **Ask the mode**: `[interactive]` (confirm each issue) or `[automated]` (fix everything,
   report at the end).

3b. **Ask the AI effort ONCE for the whole session**: `[normal | high | max | xMax]`,
   recommended tier first — it is pre-computed on the `--list` footer
   (`recommended batch ai effort: ...`, from a composite complexity score per issue:
   blast radius (`usedBy`), co-change history, rule type/severity, whether a mechanical
   compliant example exists, test coverage — Sonar's time estimate is only a minor
   factor, since Sonar easily misjudges real fix complexity). The chosen tier applies
   to every AI-done fix in the session; the user can override it for a single issue by
   saying so. **Bounded adjustment**: while fixing, if the brief/context reveals the
   score clearly missed something (e.g. the fix must change a public API signature),
   you MAY raise that one issue's tier by ONE level, stating the reason in one line —
   never lower it, never re-derive the score. Tiers control ANALYSIS depth only — no
   tier runs tests:

   | Tier | The AI must... |
   |---|---|
   | **normal** | Minimal fix at the flagged lines only. Standard read path. |
   | **high** | + check every `usedBy` file when the fix touches an API/signature; skim the `relatedFiles` relevant to THIS fix (its tests, direct users) for context; handle edge cases. |
   | **max** | + read the whole issue file and ALL `relatedFiles` in depth; weigh alternative fixes; extend the affected tests when coverage is thin. |
   | **xMax** | + adversarial self-review of each diff before recording the resolution. |

   Higher tiers explicitly widen the token-economy read allowance for the fix phase.

4. **Interactive mode** — loop `pick_issue.py --next` until exit code 2. Announce
   progress each iteration ("issue 3/12"). Per issue:
   - Show the brief straight from the `pick_issue.py` output (rule, file:line, message,
     severity, `recommend:` + reason) — no file reads in this phase.
   - Offer (recommended one FIRST, marked "(Recommended)"):
     `[Apply the Sonar suggestion]` (the rule's compliant-solution example from `issue.md`,
     applied as literally as possible) · `[Let AI solve it]` (minimal fix at the flagged
     location) · `[Your own fix / extra instructions]` (free text) · `[skip]`.
   - Apply the fix. Keep it minimal — no refactoring beyond the issue; if it changes an
     API/signature, check every `usedBy` file. **GitHub mode**: first
     `python .github/skills/sonar-issues/workspace.py fetch <file> --branch <branchRef>`
     (also for each `usedBy` file the fix touches), edit ONLY the printed workspace
     copies, then `python .github/skills/sonar-issues/workspace.py diff --branch <branchRef>`
     to regenerate `changes.patch`.
   - **Fallout sweep (mandatory, ALL fix paths — including mechanical Sonar
     suggestions)**: re-read the edited region and clean up damage the edit itself just
     caused, in the same fix: imports made unused by the change, locals/params/fields
     now unused, dead references to removed members, dangling javadoc
     (`@throws`/`@param` for removed things), empty `try`/`catch`/`finally` shells left
     after a removal. Litmus test: *would a Sonar re-scan flag something NEW as a
     direct result of my edit?* If yes, it is part of THIS fix. Hard bound: never
     extend beyond direct fallout — pre-existing problems nearby are their own issues.
     Mention swept items in the fix report line.
   - **Prove the edit landed (phantom-fix guard)** before recording anything:
     - Local mode: run `git diff --stat -- <file>` (one fast command) and show the
       one-line result. An empty diff means the fix did NOT land — retry the edit;
       never record `fixed` on an empty diff.
     - GitHub mode: confirm `workspace.py diff` listed the file, and tell the user:
       "your checkout is untouched — this change lives in the workspace until
       `/publish-to-github`" (so an empty `git diff` in their repo is expected).
   - Write `resolution.json` into the issue folder:
     `{"status": "fixed"|"skipped", "reason": "...", "filesChanged": [...], "testsRun": [],
     "mode": "local"|"github"}` — in GitHub mode add
     `"workspaceFiles": [...], "patchFile": "changes.patch"`. (`testsRun` stays empty
     here; `/sonar-verify` fills it later.) **For `fixed`, `reason` MUST be a one-line
     summary of what was actually done** (e.g. "wrapped FileInputStream in
     try-with-resources", "extracted 2 guard clauses to cut nesting") — it becomes the
     fix's brief in the final report.
   - Then offer: `[keep the issue folder] (Recommended)` or `[delete this issue's folder]`
     (progress stays tracked — a missing folder counts as `removed`/resolved; deleting
     loses only the audit trail).

5. **Automated mode** — same loop, no prompts, same fallout sweep and phantom-fix
   guard per issue:
   - Follow each issue's `recommend:` value (sonar → apply the compliant example;
     ai → minimal AI fix); deviate only when the recommended approach clearly fails.
   - No test runs. If a fix cannot be applied cleanly (or the guard shows an empty
     diff after retrying), revert that issue's change (GitHub mode: restore the
     workspace copy from what `workspace.py fetch` gave you, then `workspace.py diff`),
     record `resolution.json` as `skipped` with the reason, continue.

6. **Report**: re-run `--list`; present THREE groups so nothing is invisible —
   **fixed** (one brief line per issue: `<ruleId> · <folder> — <what was done>`, from
   each `resolution.json` reason, e.g.
   `S3776 · 007_S3776_ReportService.java_L88 — extracted 2 guard clauses to cut nesting`),
   **skipped** (each with its recorded reason), and **still unresolved** (count + their
   `--list` lines), so the user always knows exactly which issues were NOT solved.
   Remind the user Sonar clears the issues only after the branch is re-analyzed (CI).

7. **Hand-off** (never skip this message):
   - **Local mode**: "All fixes are applied to your checkout but UNTESTED — run
     `/sonar-verify` when you're ready (it runs the project's tests and helps you bisect
     any failure per issue)."
   - **GitHub mode**: "The fixes live only in the scratch workspace — your checkout is
     untouched. Next step: `/publish-to-github` (it previews the patch and pushes after
     your explicit confirmation). Tests run in CI on the pushed branch."

8. **Offer `[cleanup]`**: delete the entire `SONAR_ISSUES/<branchRef>/` folder. Local
   mode: only after the user says `/sonar-verify` passed (note: `/sonar-verify` itself
   offers cleanup after a passing full run — don't re-offer if it already happened).
   GitHub mode: only after publishing (`SONAR_ISSUES/<branchRef>/publish.json` exists)
   — cleanup before publishing would delete the unpushed fixes. Ask explicitly; never
   delete without the user choosing it.

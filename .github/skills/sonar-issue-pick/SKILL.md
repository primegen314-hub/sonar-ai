---
name: sonar-issue-pick
description: Pick and solve exactly ONE extracted Sonar issue - by selector (sequence number, folder prefix, or Sonar key) or from a filterable menu of all issues. Fast by design - no test runs; verification is a separate user-invoked step (/sonar-verify). Use when the user names a specific sonar issue ("fix issue 3", "solve the S1481 one") or wants to browse the extracted issues and choose.
---

# sonar-issue-pick `[selector]`

Scripts home: `.github/skills/sonar-issues/`. Never read `.env`; never modify anything
under `SONAR_ISSUES/` except this issue's `resolution.json` — and, in GitHub mode only,
files under `SONAR_ISSUES/<branchRef>/_workspace/edited/`.

**Speed contract**: this skill NEVER runs tests and never debugs test failures — that is
`/sonar-verify`, invoked by the user when they choose.

**On any script error**: read `.github/skills/sonar-issues/RECOVERY.md` (only then —
never upfront) and apply the one mapped action. Errors not listed there: show them
verbatim and ask the user — never improvise a recovery.

## Phases (mirror these as your progress/todo display)

1. Resolve branch
2. Locate issue
3. Brief + fix choice
4. Apply fix + prove it landed
5. Record + report

Use the host's todo/plan tool when one exists: in VS Code Copilot agentic chat, create
these phases as todo-list items at session start and mark each completed as you finish
it (they render as green check indicators above the chat); in Claude Code use the task
list the same way. No such tool: print a one-line status at each transition.

## Workflow mode (read it, never ask it)

`pick_issue.py` prints a `mode:` line (local | github) — the mode was chosen once in
`/sonar-init` and is only *read* here. If the output is missing entirely (no extracted
issues), run `/sonar-init` first. If the user wants to switch modes, point them at
`set_mode.py` and re-run `/sonar-init`; do not improvise a switch here.

- **local**: fixes edit the checkout directly.
- **github**: the checkout is irrelevant. Fixes edit ONLY the workspace copy
  (`workspace.py fetch` prints its path); the user's `git diff` will show nothing —
  that is expected, not a failed fix.

## Choice Presentation Contract (mandatory)

Every choice takes exactly one of two shapes:

1. **The host has a native question/choice tool** (e.g. AskUserQuestion in Claude Code):
   using it is MANDATORY for every choice — never present options as plain text.
2. **No such tool** (e.g. VS Code Copilot chat — it has no dropdown UI): render EXACTLY
   this menu, put nothing after it in the same message, and wait for the reply:

   ```
   ❓ <question>
     1. <option> (Recommended) — <one-line why>
     2. <option>
   Reply with a number (or type your own answer).
   ```

**FORBIDDEN in both shapes**: asking the user to describe what they want in prose
("let me know how you'd like to proceed") when the options are enumerable — that is a
defect, not a style choice.

Two more MUSTs, both shapes:
- **Every menu marks exactly ONE option `(Recommended)`, listed FIRST, with a one-line
  why.** Use the pre-computed recommendation when the scripts provide one (`recommend:`
  line, `ai effort:` line); when none exists, mark the sensible default. A menu with no
  `(Recommended)` marker is a defect.
- **Every option carries a one-line description of what happens when chosen** — native
  tools: put it in the option's description field; text menus: inline after a dash.

The issue carries a pre-computed `recommend:` line (sonar | ai) with a reason — **list
the recommended option first, marked "(Recommended)"**; don't spend tokens re-deriving it.

## Token economy — read exactly this, nothing more

- **Brief/menu phase**: `pick_issue.py` output ONLY. Do not open issue.md, issue.json,
  or the source file yet.
- **Fix phase**: this issue's `issue.json` + `context.json`, plus ONLY the `snippetRange`
  lines of the source file — in GitHub mode that means the workspace copy
  (the `workspace:` line of the issue printout names it), never the checkout. Read
  issue.md's "Suggested fix" section only when applying the Sonar suggestion. (Higher
  AI-effort tiers below explicitly widen this allowance.)
- **Never read**: `_raw/`, other issues' folders, `.env`, `_workspace/orig/`.

## Project standards (the `rules:` line)

`pick_issue.py` prints a `rules:` line listing the project's instruction files it found
(CLAUDE.md, .github/copilot-instructions.md, AGENTS.md, .cursorrules, ...). Before
applying any fix:
- Skip files your host already auto-loaded (e.g. Claude Code loads CLAUDE.md itself).
- From the rest, skim ONLY the ones plausibly relevant to this fix (coding style,
  bug-fixing conventions, code structure) — and follow them; never violate project
  standards with a fix.
- `(none found)` → ask ONCE per session (never again after any answer):
  `[Paste a reference class OR name reference files (comma-separated)] · [skip] (both fine)`.
  The user may paste code directly, or answer with comma-separated file names/paths
  (e.g. `ReportService.java, BillingService.java`) — resolve each name in the repo
  (local mode: read from the checkout; GitHub mode: `workspace.py fetch <path>` first)
  and read at most 3 files, skimming for conventions only. A name that matches nothing
  or several files: say so and let the user correct it — never guess.
  Either way: extract the conventions (naming, logging, error handling,
  formatting, idioms) and follow them for this fix; then offer
  `[Save as instructions.md] (Recommended — future sessions pick it up automatically)`
  or `[this session only]`. Saving writes a short distilled style guide (conventions,
  not the pasted code verbatim) to `instructions.md` at the repo root — from then on
  the `rules:` line finds it and this question is never asked again. If they skip:
  proceed with the fix, no searching of your own.

## AI effort tiers

When the fix will be done by AI, ask the tier — recommended one first (it comes
pre-computed on the `ai effort:` line from a composite complexity score: blast radius
(`usedBy`), co-change history, rule type/severity, mechanical-example availability, test
coverage — Sonar's time estimate is only a minor factor). **Bounded adjustment**: while
fixing, if the brief/context reveals the score clearly missed something (e.g. a public
API signature must change), you MAY raise the tier by ONE level with a one-line reason —
never lower it, never re-derive the score. Tiers control ANALYSIS depth only — no tier
runs tests:

| Tier | The AI must... |
|---|---|
| **normal** | Minimal fix at the flagged lines only. Standard read path. |
| **high** | + check every `usedBy` file when the fix touches an API/signature; handle edge cases. |
| **max** | + may read the whole issue file and `relatedFiles`; weigh alternative fixes; extend the affected tests when coverage is thin. |
| **xMax** | + adversarial self-review of the diff before recording the resolution. |

## Steps

1. **Branch**: take `--branch` from the user's message if given. **Pasted Sonar URL**:
   extract the pieces yourself — `branch=` is the branch, and `open=<key>` is the issue
   key (use it as the selector in step 2); no `open=` in the URL → just use its branch
   and show the menu. Otherwise run
   `python .github/skills/sonar-issues/pick_issue.py --branches` — one tree: use it;
   several: present them as a choice (each line already shows branch + resolved count);
   none: run sonar-init first. Never guess between branches. (A URL only locates issues
   already extracted by `/sonar-init` — if the branch tree is missing, init runs first.)

2. **Locate the issue** — never guess folder names:
   - Selector given → `python .github/skills/sonar-issues/pick_issue.py <selector> --branch <branchRef>`.
   - No selector → `pick_issue.py --list --branch <branchRef>`, then present the unresolved
     issues as a choice menu grouped by severity. Let the user filter with free text
     (rule id, file name, or severity) and re-present the narrowed list if they do.

3. **Brief**: straight from the `pick_issue.py` output — rule, file:line, message,
   severity, and the `recommend:` line with its reason. No file reads in this phase.

4. **Offer** (recommended one FIRST, marked "(Recommended)"):
   `[Apply the Sonar suggestion]` (the rule's compliant-solution example, applied as
   literally as possible) · `[Let AI solve it]` (minimal fix at the flagged location) ·
   `[Your own fix / extra instructions]` (free text).

5. **Effort** (only when the fix is AI-done — `[Let AI solve it]` was picked or chosen
   for the user's own instructions): ask `[normal | high | max | xMax]`, recommended tier
   first from the `ai effort:` line. Skip this question when applying the Sonar
   suggestion mechanically.

6. **Apply** the fix per the chosen tier — never refactor beyond the issue; if it changes
   an API/signature, check every `usedBy` file in `context.json`.

   **GitHub mode**: before editing, run
   `python .github/skills/sonar-issues/workspace.py fetch <file> --branch <branchRef>`
   for the issue's file (and for each `usedBy` file the fix must touch) — it prints the
   workspace copy to edit. Edit ONLY those workspace copies. After the fix, run
   `python .github/skills/sonar-issues/workspace.py diff --branch <branchRef>` to
   regenerate `changes.patch` (the cumulative review artifact).

6b. **Fallout sweep (mandatory, ALL fix paths — including mechanical Sonar
   suggestions)**: re-read the edited region and clean up damage the edit itself just
   caused, in the same fix: imports made unused by the change, locals/params/fields now
   unused, dead references to removed members, dangling javadoc (`@throws`/`@param` for
   removed things), empty `try`/`catch`/`finally` shells left after a removal. Litmus
   test: *would a Sonar re-scan flag something NEW as a direct result of my edit?* If
   yes, it is part of THIS fix. Hard bound: never extend beyond direct fallout —
   pre-existing problems nearby are their own issues. Mention swept items in the report.

7. **Prove the edit landed (phantom-fix guard)** before recording anything:
   - Local mode: run `git diff --stat -- <file>` (one fast command) and show the
     one-line result. An empty diff means the fix did NOT land — retry the edit; never
     record `fixed` on an empty diff.
   - GitHub mode: confirm `workspace.py diff` listed the file, and tell the user:
     "your checkout is untouched — this change lives in the workspace until
     `/publish-to-github`".

8. **Record** `resolution.json` in the issue folder:
   `{"status": "fixed"|"skipped", "reason": "...", "filesChanged": [...], "testsRun": [],
   "mode": "local"|"github"}` — in GitHub mode add
   `"workspaceFiles": [...], "patchFile": "changes.patch"`. (`testsRun` stays empty
   here; `/sonar-verify` fills it later.) **For `fixed`, `reason` MUST be a one-line
   summary of what was actually done** — it becomes the fix's brief in the report.
   Then offer: `[keep the issue folder] (Recommended)` or `[delete this issue's folder]` —
   progress stays tracked either way (a missing folder counts as `removed`/resolved);
   deleting loses only the audit trail.

9. **Report** with the fix's brief line — `<ruleId> · <folder> — <what was done>` (the
   resolution reason) — plus the issue's `sonarUrl` so the user can see it in Sonar.
   Close with the hand-off:
   - Local mode: "the fix is applied but untested — run `/sonar-verify` whenever you're
     ready (recommended: after you've solved all the issues you plan to)."
   - GitHub mode: "the fix is only in the workspace until `/publish-to-github` pushes it;
     tests run in CI on the pushed branch."

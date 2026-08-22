# Sonar Issues Pipeline

Tooling that pulls SonarQube issues for a branch into per-issue folders, then guides a developer (or an AI agent) through fixing, verifying, and shipping them — in the local checkout or entirely through the GitHub API.

## Language

### Modes

**Workflow Mode**:
The one user-facing switch (`local` | `github`), chosen ONCE in `/sonar-init` via `set_mode.py` and persisted as `WORKFLOW_MODE`. `local` = fixes edit the git checkout, tests run via Verify, the user pushes with git. `github` = no checkout needed; fixes go to the Scratch Workspace and reach GitHub via Publish; tests run in CI. There is no mid-session mode switch — changing modes means re-running `/sonar-init`.
_Alias_: `remote` (accepted forever in `.env` and `set_mode.py` for GitHub Mode)
_Avoid_: context mode

**Sonar Branch**:
`SONAR_BRANCH` — the Sonar-side branch name when Sonar names the branch differently than git (local mode only). Extraction queries Sonar with it while git operations use the git branch.

### Extraction

**Pipeline**:
The s01–s06 script sequence that turns a pasted Sonar URL into a Branch Folder.
_Avoid_: scripts, steps (when meaning the whole run)

**Branch Folder**:
`SONAR_ISSUES/<branchRef>/` — everything the Pipeline produced for one Sonar branch: `_raw/`, one Issue Folder per issue, and `summary.json`.

**Issue Folder**:
One directory per Sonar issue (`NNN_ruleId_file_LNN/`) holding `issue.json`, `issue.md`, `context.json`, and (once worked) `resolution.json`.

**Context Source**:
Where the Pipeline reads source code from when building context: `local` (the git checkout) or `github` (the GitHub API). Derived from Workflow Mode — an internal knob, no longer set by hand.

**Branch Check**:
The hard-error gate before extraction. Local mode: Sonar must know the branch, the Sonar branch must equal the checked-out git branch (unless Sonar Branch declares the mismatch), and the checkout must be in sync with origin — each failure names exactly ONE remedy command for the user to run (never a mode switch). GitHub mode: the branch must exist on GitHub; the checkout is never consulted.

### Solving

**Sonar Suggestion**:
The rule's generic Compliant-solution example (from `issue.md`), applied as mechanically as possible. NOT Sonar's per-issue quick-fix patch — the Pipeline never fetches that.
_Avoid_: quick fix

**Recommended Fix**:
The per-issue, deterministically pre-computed default (`sonar` or `ai`, with a reason): `ai` when the rule's language doesn't match the file or the rule has no compliant example. Presented first in every choice menu.

**AI Effort Tier**:
The pre-computed analysis depth for an AI-done fix (`normal` | `high` | `max` | `xMax`), derived from the Complexity Score. Tiers widen what the AI reads and considers before fixing; the AI may raise a tier one level mid-fix with a stated reason (never lower); no tier ever runs tests.

**Complexity Score**:
The deterministic per-issue estimate of how big a fix really is: blast radius (`usedBy`), co-change history, rule type/severity, mechanical-example availability, test coverage — with Sonar's own time estimate as only a minor factor (Sonar easily misjudges). Always computable, even when Sonar gives no estimate.

**Batch Fix**:
Solving a chosen SUBSET of extracted issues in one session (`/sonar-batch-fix`) — named by selectors/ranges, a rule id, or a severity. The chunking strategy for large backlogs; ends with fixed / skipped / still-unresolved so progress stays visible.

**Attack Plan**:
The deterministic suggested fixing order for a backlog, computed by `pick_issue.py --stats` from the extracted data: Quick Wins first, then same-rule batches (3+ unresolved issues sharing a rule), then the hard tail one issue at a time by severity — with a verify + commit gate between steps. Surfaced only by the read-only `/sonar-attack-plan` skill (or the raw flag); other skills may mention it in one line but never impose it.
_Avoid_: roadmap, strategy

**Quick Wins**:
The low-effort slice of a backlog — unresolved issues with Recommended Fix `sonar` and AI Effort Tier `normal` — cleared in one automated pass (`/sonar-quick-wins`), leaving the harder remainder explicitly listed.

**Interactive Mode**:
Solving one issue at a time: brief shown, user picks Sonar Suggestion / AI fix / their own instruction.

**Automated Mode**:
Solving all unresolved issues without pausing; failures are skipped-and-recorded. No tests run — Verify is a separate step.

**Style Snapshot**:
Reference material the user supplies as the session's highest-priority authority — proactively offered once per session when no instruction files exist (`rules:` line says none found), and honored ANYTIME the user volunteers it (even when rules files exist; on conflict: user reference > rules files > model defaults). Given as pasted code, comma-separated repo file names (max 3), framework skills/docs/examples, or domain notes. Governs both STYLE (naming, logging, idioms) and IMPLEMENTATION (which framework APIs/patterns fixes use). With consent, distilled into a root-level `instructions.md` — guidance only, never the supplied code verbatim.

**Fallout Sweep**:
The mandatory completeness pass after every fix (all fix paths, including mechanical Sonar Suggestions): clean up damage the edit itself caused — unused imports/locals/params, dead references, dangling javadoc, empty try/catch shells. Litmus test: anything a Sonar re-scan would newly flag as a direct result of the edit belongs to the fix. Strictly bounded: never touches pre-existing neighbors.

**Phantom-Fix Guard**:
The proof, required before writing a Resolution, that the edit actually landed: local mode — a non-empty `git diff --stat` for the file; GitHub mode — the file appears in the regenerated Patch. Prevents recording `fixed` when nothing changed.

**Resolution**:
The per-issue outcome record (`resolution.json`: fixed or skipped, reason, files changed, tests run, mode — plus workspace files and patch file in GitHub mode). `testsRun` is filled by Verify, never at solve time. Survives Pipeline re-runs for issues that still exist.

**Scratch Workspace**:
`SONAR_ISSUES/<branchRef>/_workspace/` — where GitHub-mode fixes are made: `orig/` holds pristine byte-exact copies fetched from GitHub, `edited/` the copies the fixes edit. The checkout is never touched in GitHub mode (so `git diff` showing nothing is expected).
_Avoid_: sandbox, staging

**Patch**:
`SONAR_ISSUES/<branchRef>/changes.patch` — the cumulative, `git apply`-compatible unified diff of the Scratch Workspace (orig vs edited), regenerated wholesale after every fix. A review artifact: Publish pushes the edited file contents, not the patch.
_Avoid_: diff file, quick fix

**Verify**:
Running the project's tests — always user-invoked via `/sonar-verify`, never automatic during solving. Scoped Verify = only one issue's `testFiles` (used to bisect a failure); Full Verify = the whole suite (the normal end-of-session run). Local mode only — in GitHub mode verification happens in CI after Publish (`verify.py` refuses with exit 4).

**Recovery Playbook**:
The deterministic error-to-action table (`RECOVERY.md`) skills consult only when a script fails: every known failure maps to exactly one next action (one retry max for transients); unlisted errors are shown verbatim to the user. Self-recovery without improvised debugging.

**Phase Protocol**:
Every skill opens with a fixed numbered phase list that the agent mirrors as its progress/todo display ("issue 3/12"), so the user always sees where the session is.

**Publish**:
The explicit, user-confirmed commit of the Scratch Workspace changes to a target GitHub branch — one atomic multi-file commit via the GitHub API (`/publish-to-github` → `publish.py`). GitHub mode only; records `publish.json` and re-baselines the workspace.
_Avoid_: push (unqualified), deploy

**Cleanup**:
The offered (never automatic) deletion of the entire Branch Folder — local mode: after the user reports a passing Full Verify; GitHub mode: only after a Publish (`publish.json` exists).

### Skills

**Canonical Home**:
`.github/skills/sonar-issues/` — the single copy of scripts and full skill docs. `.claude/skills/` entries are thin wrappers pointing there.

**Adaptive Interactivity**:
The Choice Presentation Contract: when the host has a native question UI (Claude Code dropdowns) using it is mandatory; otherwise (Copilot chat has no dropdown UI) choices render as an exact numbered menu answered with one number. Prose "tell me what you'd like" asks for enumerable options are a defect.

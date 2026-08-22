# USAGE — every script, every flag, with real demo output

> Prefer pictures? **[FLOWS.md](FLOWS.md)** shows the same workflows as diagrams —
> every dropdown the AI presents and what each choice leads to.

Every output block below is a **real captured run** of the bundled offline demo
(`--fixtures --branch demo`), executed in Git Bash on Windows. Swap the demo flags for
your pasted Sonar URL and the commands become live runs — nothing else changes.

All commands run from the **repository root**.

## Flags — identical for every script

| Flag | Meaning | Default |
|---|---|---|
| `url` (positional, optional) | Pasted Sonar URL. Parsed for host, project (`id=`), `issueStatus`, `newCodePeriod` | falls back to `.env` (`SONAR_HOST`, `SONAR_PROJECT_KEY`, `ISSUE_STATUSES`, `SCOPE`) |
| `--branch NAME` | Branch ref override | URL `branch=`, then `SONAR_BRANCH`, then (local mode only) the current git branch — GitHub mode needs an explicit branch |
| `--fixtures` | Offline mode: bundled sample API responses, no network, no credentials | off |
| `--discard-workspace` | GitHub mode: delete unpublished workspace edits instead of refusing the re-fetch (s02 consumes it) | off |
| `--help` | Usage text | |

Live run pattern (the only two forms you need):

```bash
# everything at once
python .github/skills/sonar-issues/run_all.py "sonar.example.com/project/issues?issueStatus=OPEN%2CCONFIRMED&newCodePeriod=true&id=example_report-service"

# or any single step, same argument
python .github/skills/sonar-issues/steps/s02_fetch_issues.py "<same-url>"
```

---

# Setup — minimal vs recommended

**Minimal** (works immediately): copy `.github/skills/` into the repo, add
`SONAR_ISSUES/` + `.env` to `.gitignore`, put `SONAR_HOST` and `SONAR_USER` in
`.github/skills/sonar-issues/.env`. Done — `/sonar-init <url>` handles everything else.

**Recommended** for the best experience: leave `SONAR_PASSWORD` empty (interactive prompt,
never on disk) · set `SONAR_PROJECT_KEY` so you can run without pasting a URL · let the
first `/sonar-verify` establish `TEST_COMMAND` (auto-detect or AI-determined once, then
persisted — never asked again) · copy `.claude/skills/` too if you use Claude Code
(real dropdowns) · let `/sonar-init`'s one-time mode question set `WORKFLOW_MODE`
(Local when you have the checkout; GitHub when you don't — needs a write-scope GitHub token).

---

# The skills — what you invoke, what gets asked, what to pick

Eight skills drive the whole workflow (Claude Code shows real dropdowns via
AskUserQuestion; Copilot chat has no dropdown UI, so the same options render as a strict
numbered menu — you answer with just a number). Each skill announces its phases as it
works ("issue 3/12") so you always see where it is. Every fix ends with a mandatory
**fallout sweep**: anything the edit itself broke (an import made unused by a removal,
dangling javadoc, an emptied try/catch) is cleaned in the same fix, so solving one
issue never plants the next one.

## `/sonar-init <sonar-url>` — extract

One dropdown, asked ONCE ever: **Workflow mode** — `Local` (fixes edit this checkout;
setup asks nothing — the branch is resolved per run from the Sonar URL or the current
checkout) or `GitHub` (no checkout needed; you run `set_mode.py github` in your terminal
to enter a WRITE-scope GitHub token with hidden input — without a checkout it asks you
to paste the repo URL; fixes go to the scratch workspace and are pushed with
`/publish-to-github`). After that: no dropdowns — the pipeline runs and reports the
summary. First run only: it asks you to fill `SONAR_USER` in the skill's `.env` and (if
no password is stored) s01 prompts for your LDAP password in the terminal. Errors you may
see and what they mean:

- red **Sonar has no branch X** (git and Sonar name it differently) → the AI
  asks for the Sonar branch name → `set_mode.py --sonar-branch <name>`, re-run.
- red **branch not on GitHub** (GitHub mode) → pass `--branch` or set `GITHUB_BRANCH=`.
- red **wrong branch / out of sync** (local mode; Sonar analyzed the pushed state) → the
  error prints exactly ONE git command (`git checkout <branch> && git pull` or
  `git pull`); the AI offers to run it in the terminal — you approve, it runs, re-run
  the pipeline. No mode switching is ever offered here. `SYNC_CHECK=false` in `.env`
  disables the sync gate (offline use).
- red **unpublished workspace changes** (GitHub-mode re-run) → publish first, or
  `--discard-workspace`.

## `/sonar-issues-solve [branch | sonar-url]` — solve everything

| # | Dropdown | Options | How to choose |
|---|---|---|---|
| 1 | Mode | `interactive` / `automated` | `interactive` when you want to confirm each fix (first time on a branch, risky code); `automated` when the list is long and mostly `rec:sonar` trivia. |
| 2 | AI effort (asked ONCE) | `normal` / `high` / `max` / `xMax` | Take the pre-computed recommendation shown in the `--list` footer — a composite complexity score per issue (usedBy blast radius, co-change history, rule type/severity, tests; Sonar's time estimate is only a minor factor). Bump it up for critical code, down for a pile of unused-variable trivia. |
| 3 | Per issue (interactive only) | `Apply the Sonar suggestion` / `Let AI solve it` / `Your own fix` / `skip` | Take the option marked **(Recommended)** — `rec:sonar` means the rule's example fits this file's language; `rec:ai` means the rule may not fit this app (e.g. frontend) so a tailored AI fix is safer. `Your own fix` when you know something the tools don't. |
| 4 | Cleanup (end; local: after `/sonar-verify` passed / GitHub: after publishing) | `cleanup` / keep | `cleanup` deletes the whole `SONAR_ISSUES/<branch>/` folder. Keep it if you still want the audit trail. |

No tests run during solving — after every local fix the AI shows a one-line
`git diff --stat` proving the edit landed (the phantom-fix guard), and the session ends
by pointing you at `/sonar-verify` (local) or `/publish-to-github` (GitHub mode).

## `/sonar-issue-pick [selector]` — solve one issue

| # | Dropdown | Options | How to choose |
|---|---|---|---|
| 1 | Issue (only when no selector given) | list of unresolved issues grouped by severity, free-text filter | Severity icons/order: 🔴 BLOCKER first. Filter by rule id or file name to narrow. |
| 2 | Fix approach | `Apply the Sonar suggestion` / `Let AI solve it` / `Your own fix` | Same rule as above — take the **(Recommended)** one from the `recommend:` line. |
| 3 | AI effort (only when the fix is AI-done) | `normal` / `high` / `max` / `xMax` | Take the recommendation from the `ai effort:` line — a composite complexity score (usedBy blast radius, co-change history, rule type/severity, mechanical-example availability, tests; Sonar's minutes are only a minor factor). The AI may raise it ONE level mid-fix with a stated reason. |

Same phantom-fix guard and hand-off as `/sonar-issues-solve` — no tests run here;
verify with `/sonar-verify` when you're done picking issues.

## `/sonar-mode [local | github]` — show or switch the workflow mode

Shows `set_mode.py --show` output; switching to Local runs the script directly (asks
nothing), switching to GitHub sends you to your own terminal for the hidden token
prompt. Always reminds you to re-run `/sonar-init` after a switch (progress survives).

## `/sonar-roadmap` — the backlog report + suggested order (read-only)

Runs `pick_issue.py --stats` (sample output in the pick_issue section below) and shows
it verbatim: unresolved issues grouped by rule, then the fix roadmap — quick wins →
same-rule batches → hard tail by severity. One choice follows: `[Start step 1 now]
(Recommended)` or `[Just wanted the report]`. It fixes nothing itself; every plan line
is a copy-paste command. Full walkthrough: repo-root `USECASE.md`.

## `/sonar-batch-fix <subset>` — fix a chosen chunk (large projects)

Subset forms: `3,5,7-12` (selectors + ranges by sequence) · `S1481` (every unresolved
issue of that rule) · `BLOCKER` (every unresolved issue of that severity). Same fix
machinery as solve (fallout sweep, phantom-fix guard), automated by default; ends with
fixed / skipped / **still unresolved** so chunked progress stays visible. Recommended
rhythm on big backlogs: chunks of 30–50, `/sonar-verify` per chunk, push, repeat.

## `/sonar-quick-wins [severity]` — auto-clear the easy majority

Selects every unresolved issue with `rec:sonar` + `eff:normal` (the `--list` output
shows both flags per issue), optionally one severity only, fixes them in one automated
pass, and ends with **left for you**: the harder remainder with severity/rec/eff per
line — you always know exactly what was not solved.

## `/sonar-verify [issue-selector]` — run the tests (always you, never automatic)

| # | Dropdown | Options | How to choose |
|---|---|---|---|
| 1 | Test command (only the FIRST time ever, when nothing is auto-detected) | `let AI determine it` (Recommended) / `type it yourself` / `skip verification` | AI inspects package.json / multi-module gradle / maven / Makefile and proposes the exact command; it's saved via `--set-command` and never asked again. |
| 2 | On failure | `bisect per issue` (Recommended) / `different test command` / `investigate` / `skip` | Bisect runs each fixed issue's own `testFiles` (`verify.py --issue <n>`) to find the culprit fix. The AI only starts debugging if you explicitly pick `investigate`. |

No selector = full suite (the normal end-of-session run). With a selector it runs just
that issue's tests. GitHub mode: it explains that verification happens in CI after
`/publish-to-github` (there is no fixed code locally to test).

## `/publish-to-github [branch]` — push GitHub-mode fixes (GitHub mode only)

| # | Dropdown | Options | How to choose |
|---|---|---|---|
| 1 | Target branch | analyzed branch (Recommended) / a new branch / another existing branch | The analyzed branch is where Sonar looks after CI — pick a new branch when you want a PR-style review first. |
| 2 | Confirm push | `Push N file(s) to org/repo@target` / `Cancel` | The point of no return — the preview above it shows exactly which files and diffs go up. Nothing is ever pushed without this. |
| 3 | Cleanup | `cleanup` / keep | Safe now — `publish.json` records the pushed commit. |

In local mode this skill refuses: you commit and push with git yourself. After you
confirm in chat, the AI always runs `publish.py` with `--yes` — agent terminals have no
interactive stdin, so the script's own prompt cannot run there (exit 2 says exactly that).

**AI effort tiers** (analysis depth only — no tier runs tests): `normal` = minimal fix ·
`high` = + usedBy impact check + targeted skim of this fix's related files + edge cases ·
`max` = + whole file and ALL related files in depth, weighs alternatives, extends tests ·
`xMax` = + adversarial self-review of the diff.

---

## s01_setup_auth.py — mint the Sonar token (run once)

Live: needs `SONAR_USER` in `.env`. Leave `SONAR_PASSWORD` empty → prompts interactively
(hidden, never stored). Writes `SONAR_TOKEN` back to `.env`; clears the password if it
was in the file.

```bash
python .github/skills/sonar-issues/steps/s01_setup_auth.py "sonar.example.com"
```

Live output looks like:
```text
[s01] Sonar host : https://sonar.example.com
[s01] Sonar LDAP password for aa12345 (not stored): ********
[s01] server version 10.6.0.92116
[s01] generating user token 'sonar-issues-aa12345-1755440000' ...
[s01] SONAR_TOKEN written to C:\path\to\repo\.github\skills\sonar-issues\.env
[s01] done - later steps authenticate with the token, not your password
```

Demo (real captured output):
```text
$ python .github/skills/sonar-issues/steps/s01_setup_auth.py --fixtures --branch demo
[s01] fixtures mode - skipping authentication
```

---

## s02_fetch_issues.py — fetch issues → `_raw/issues.json` + `meta.json`

**Wipes `SONAR_ISSUES/<branch>/` first** (rerun policy: folder always mirrors Sonar) but
**stashes every `resolution.json` by issue key** into `_raw/resolutions.json`; s04 restores
them for issues still reported, so solve progress survives re-runs.
Also runs the **branch gate**: in local mode the Sonar branch must equal the checked-out
git branch (or `SONAR_BRANCH` declares the mismatch), Sonar must know the branch, and the
checkout must be in sync with origin; in GitHub mode the branch must exist on GitHub —
otherwise a red error stops the run and prints the ONE command that fixes it.
GitHub mode only: unpublished workspace edits block the re-fetch (publish first, or pass
`--discard-workspace`).
Later steps read the parameters from `meta.json`, so run s02 before s03–s06.

```text
$ python .github/skills/sonar-issues/steps/s02_fetch_issues.py --fixtures --branch demo
[s02] mode     : local
[s02] project  : example_report-service
[s02] branchRef: demo  (folder: demo)
[s02] scope    : new code | statuses: OPEN,CONFIRMED
[s02] fetched 3 issues (server total: 3)
[s02] wrote C:\...\SONAR_ISSUES\demo\_raw\issues.json and meta.json
```

---

## s03_fetch_rules.py — rule descriptions → `_raw/rules.json`

```text
$ python .github/skills/sonar-issues/steps/s03_fetch_rules.py --fixtures --branch demo
[s03] 3 distinct rules to fetch
[s03]   java:S1068: Unused "private" fields should be removed
[s03]   java:S1481: Unused local variables should be removed
[s03]   java:S2095: Resources should be closed
[s03] wrote C:\...\SONAR_ISSUES\demo\_raw\rules.json
```

---

## s04_build_folders.py — one folder per issue: `issue.json` + `issue.md`

```text
$ python .github/skills/sonar-issues/steps/s04_build_folders.py --fixtures --branch demo
[s04] building 3 issue folders under C:\...\SONAR_ISSUES\demo
[s04]   001_S1068_ReportService.java_L12
[s04]   002_S1481_ReportService.java_L21
[s04]   003_S2095_ReportService.java_L26
[s04] done
```

`issue.md` inside a folder looks like (excerpt of a real generated file):
```markdown
# S1068: Remove this unused 'translateService' private field or make it 'readonly'.

- **Rule**: java:S1068 — Unused "private" fields should be removed
- **Type**: CODE_SMELL | **Severity**: MAJOR | **Effort**: 5min

## Where is the issue

`src/main/java/com/example/report/ReportService.java` — line 12

       10 | public class ReportService {
       11 |
>>>    12 |     private TranslateService translateService;
       13 |

## Why is this an issue
...
## Suggested fix
**Sonar says:** Remove this unused 'translateService' private field or make it 'readonly'.
```

---

## s05_build_context.py — `context.json` per issue (tests, used-by, co-changed files)

`usedBy` is the impact analysis: files that reference the issue file's class name
(who uses this class → who might be affected by the fix), ranked by reference count.

```text
$ python .github/skills/sonar-issues/steps/s05_build_context.py --fixtures --branch demo
[s05] 3 project files scanned for related tests
[s05]   001_S1068_ReportService.java_L12: 1 tests, 2 used-by, 0 co-changed
[s05]   002_S1481_ReportService.java_L21: 1 tests, 2 used-by, 0 co-changed
[s05]   003_S2095_ReportService.java_L26: 1 tests, 2 used-by, 0 co-changed
[s05] done
```

`context.json` excerpt (real generated file):
```json
"usedBy": [
  { "file": "src/test/java/com/example/report/ReportServiceTest.java", "references": 4 },
  { "file": "src/main/java/com/example/report/ReportController.java", "references": 2 }
]
```

---

## s06_summarize.py — `summary.json` + validation (exit 1 if anything is incomplete)

```text
$ python .github/skills/sonar-issues/steps/s06_summarize.py --fixtures --branch demo
[s06] summary.json: 3 issues | severity {'MAJOR': 1, 'MINOR': 1, 'BLOCKER': 1} | type {'CODE_SMELL': 2, 'BUG': 1}
[s06]   001_S1068_ReportService.java_L12: Remove this unused 'translateService' private field or make it 'readonly'.
[s06]   002_S1481_ReportService.java_L21: Remove this unused 'total' local variable.
[s06]   003_S2095_ReportService.java_L26: Use try-with-resources or close this 'FileInputStream' in a "finally" clause.
[s06] validation OK - C:\...\SONAR_ISSUES\demo is complete
```

---

## run_all.py — the whole pipeline in one command

Chains s01 → s06 with the same arguments; stops at the first failing step.

```bash
python .github/skills/sonar-issues/run_all.py "<pasted-sonar-url>"        # live
python .github/skills/sonar-issues/run_all.py --fixtures --branch demo    # offline demo
```

---

## pick_issue.py — list issues / locate one (used by the solving skills)

Extra flags beyond the common ones: `--list`, `--stats`, `--next`, `--branches` (every
extracted branch tree with resolved counts — how the skills disambiguate when several
branches exist), or a positional *selector* (sequence number, folder-name prefix, or
Sonar issue key).
Exit codes: `0` found · `1` error · `2` `--next` found nothing (all resolved).

`--stats` is the big-backlog report: unresolved issues grouped by rule, plus a
deterministic **fix roadmap** (quick wins → same-rule batches → hard tail by severity).
The dedicated `/sonar-roadmap` skill presents it verbatim on request — it is never
imposed on a solving session — see [USECASE.md](../../../USECASE.md) for the full
200+-issue walkthrough:

```text
$ python .github/skills/sonar-issues/pick_issue.py --stats --branch demo
branch: demo | project: example_report-service | mode: local | unresolved: 3/3
by rule:
  S1068      x1    sev MAJOR:1 | rec sonar:1 | eff normal:1 | Remove this unused 'translateService' private field or ma...
  S1481      x1    sev MINOR:1 | rec sonar:1 | eff normal:1 | Remove this unused 'total' local variable.
  S2095      x1    sev BLOCKER:1 | rec sonar:1 | eff high:1 | Use try-with-resources or close this 'FileInputStream' in...
fix roadmap (fastest correct order - verify + commit between steps):
  1. /sonar-quick-wins                  - 2 safe-fix issue(s) (rec:sonar + eff:normal) in one automated pass
  2. hard tail - 1 issue(s) one at a time, highest severity first: /sonar-issue-pick <seq> in this order: 3
between steps: quick gate with /sonar-verify (--compile) and commit/publish the chunk.
```

```text
$ python .github/skills/sonar-issues/pick_issue.py --list --branch demo
branch: demo | project: example_report-service | mode: local | fetched: 2026-08-17T14:21:30+00:00
  [unresolved] 001_S1068_ReportService.java_L12  MAJOR    Remove this unused 'translateService' private field or make it 'rea...
  [unresolved] 002_S1481_ReportService.java_L21  MINOR    Remove this unused 'total' local variable.
  [unresolved] 003_S2095_ReportService.java_L26  BLOCKER  Use try-with-resources or close this 'FileInputStream' in a "finall...
0/3 fixed

$ python .github/skills/sonar-issues/pick_issue.py 2 --branch demo
seq     : 2
folder  : C:\...\SONAR_ISSUES\demo\002_S1481_ReportService.java_L21
issue   : C:\...\SONAR_ISSUES\demo\002_S1481_ReportService.java_L21\issue.json
context : C:\...\SONAR_ISSUES\demo\002_S1481_ReportService.java_L21\context.json
md      : C:\...\SONAR_ISSUES\demo\002_S1481_ReportService.java_L21\issue.md
mode    : local
status  : unresolved
severity: MINOR | type: CODE_SMELL | effort: 5min
file    : src/main/java/com/example/report/ReportService.java:21
message : Remove this unused 'total' local variable.
recommend: sonar - the rule's compliant example matches this file's language and can be applied directly
ai effort: normal (2 usedBy file(s))
rules    : CLAUDE.md; .github/copilot-instructions.md
```

The `rules:` line lists the project's instruction files (CLAUDE.md,
.github/copilot-instructions.md, instructions.md, AGENTS.md, .cursorrules, ...) found by
a pure filesystem check — the solving AI skims only the relevant ones so fixes never
violate project coding standards, and spends zero tokens searching for them. When NONE
exist, the solving skills offer once per session: give reference code — paste a class,
or name up to 3 repo files comma-separated (`ReportService.java, BillingService.java`) —
and the AI matches its style and can distill it into a root-level `instructions.md` so
it's permanent; or just skip.

The `recommend:` line (also `rec:` in `--list`) is computed deterministically by s04 —
`sonar` = apply the rule's compliant example; `ai` = the rule's language doesn't match the
file (e.g. a backend rule flagged in frontend code) or the rule has no example, so an AI
fix tailored to the code is the better default. The solving skills present the recommended
option first without spending any AI tokens to decide.

---

## verify.py — the engine behind /sonar-verify (never run automatically by any skill)

`TEST_COMMAND` in the skill `.env` wins; when empty the runner is auto-detected
(`pom.xml`→maven, `build.gradle`→gradle, `package.json`→`npm test`, pytest markers) and
printed before running. Exit codes: `0` passed · `3` nothing to run (no `testFiles`, no
`BUILD_COMMAND`) · `2` config error · `4` GitHub mode (by design — the fixes live in the
workspace, not any checkout; verify after publishing via CI or by pulling the published
branch; `--set-command` still works) · otherwise the runner's exit code.

```bash
python .github/skills/sonar-issues/verify.py --full   --branch demo    # whole suite (the normal /sonar-verify run)
python .github/skills/sonar-issues/verify.py --issue 2 --branch demo   # only issue #2's testFiles (bisecting a failure)
python .github/skills/sonar-issues/verify.py --compile --branch demo   # compile-only, seconds: BUILD_COMMAND or derived (mvn compile / gradlew classes / compileall)
python .github/skills/sonar-issues/verify.py --set-command "mvn -pl core -am test"   # persist TEST_COMMAND once
```

`--compile` is the cheap sanity check right after a solving session — it catches
"the fix doesn't even build" (a failure smaller models won't admit to) without paying
for a test run. Exit 3 = nothing derivable: set `BUILD_COMMAND` in the skill `.env`.

```text
$ python .github/skills/sonar-issues/verify.py --issue 2 --branch demo
[verify] auto-detected maven: mvn -B test
[verify] running: mvn -B test -Dtest=ReportServiceTest -DfailIfNoTests=false
[verify] cwd    : C:\...\repo
...
[verify] PASSED
```

---

## set_mode.py — choose (and verify) the workflow mode

The ONE place the Local | GitHub choice is made and stored (`WORKFLOW_MODE` in the skill
`.env`; `CONTEXT_SOURCE` is derived from it). `/sonar-init` drives it; you can also run it
yourself. `remote` is accepted as a permanent alias for `github`.

```bash
python .github/skills/sonar-issues/set_mode.py local                          # asks nothing; never touches your checkout
python .github/skills/sonar-issues/set_mode.py github                         # hidden token prompt, org/repo from origin
python .github/skills/sonar-issues/set_mode.py github --repo-url https://github.com/acme/report-service   # no checkout at all
python .github/skills/sonar-issues/set_mode.py github --repo-url "https://github.com/acme/report-service/tree/feat-x"   # deep link: branch auto-saved as GITHUB_BRANCH; GHE hosts auto-derive the API URL
python .github/skills/sonar-issues/set_mode.py github --repo-url acme/report-service --no-token   # "set the token later": saves mode/org/repo, status INCOMPLETE until the token is added
python .github/skills/sonar-issues/set_mode.py github --api-url https://<ghe-host>/api/v3   # GitHub Enterprise
python .github/skills/sonar-issues/set_mode.py --sonar-branch TASK-3487    # local: Sonar names the branch differently
python .github/skills/sonar-issues/set_mode.py --show                         # verify; exit 2 = no mode chosen yet
```

```text
$ python .github/skills/sonar-issues/set_mode.py --show
mode        : github
github      : acme/report-service @ https://api.github.com
token       : set
sonar host  : https://sonar.example.com
sonar token : minted
status      : configured
```

`github` needs a token with WRITE access (classic: `repo` scope; fine-grained: Contents
read/write) — publishing commits through the API. The token is prompted with hidden input
in YOUR terminal; a classic token without write scope triggers a warning immediately.
No git checkout is required: without one, pass `--repo-url` (or paste it at the prompt).
In GitHub mode the local checkout (and whatever branch it is on) is completely irrelevant.
`local` writes the mode and nothing else — the branch is resolved per run, and any
needed `git checkout`/`git pull` is printed for YOU to run, never executed for you.

---

## workspace.py — GitHub-mode fixes live here (refuses in local mode, exit 2)

Fixes never touch the checkout in GitHub mode: `fetch` pulls a byte-exact copy of a file
from GitHub into `SONAR_ISSUES/<branch>/_workspace/` (`orig/` = pristine, `edited/` = the
copy to fix); `diff` rebuilds the cumulative, `git apply`-compatible `changes.patch` from
scratch (idempotent — safe when several issues touch one file).

```bash
python .github/skills/sonar-issues/workspace.py fetch src/main/java/com/example/report/ReportService.java --branch demo
python .github/skills/sonar-issues/workspace.py diff    --branch demo
python .github/skills/sonar-issues/workspace.py status  --branch demo
python .github/skills/sonar-issues/workspace.py discard --branch demo --yes
```

```text
$ python .github/skills/sonar-issues/workspace.py diff --branch demo --fixtures
[workspace] changes.patch rebuilt - 1 file(s) changed
  src/main/java/com/example/report/ReportService.java  +2 -1
patch: C:\...\SONAR_ISSUES\demo\changes.patch
```

---

## publish.py — push the workspace changes as ONE commit (GitHub mode only)

Commits every changed `edited/` file to a target branch in ONE atomic commit via the
GitHub Git Data API (blobs → tree → commit → ref). Refuses in local mode (exit 2 — you
push with git yourself). Detects files that changed on GitHub since extraction and stops
before overwriting anyone's work (`--force` = explicit last-write-wins). Writes
`publish.json` next to `summary.json` and re-baselines the workspace (clean again).
Under `--fixtures` only `--dry-run` is allowed — offline runs never write to the network.

```bash
python .github/skills/sonar-issues/publish.py --dry-run --branch demo             # preview: files, diffstat, issues
python .github/skills/sonar-issues/publish.py --branch demo --target-branch demo --yes
```

```text
$ python .github/skills/sonar-issues/publish.py --dry-run --branch demo --fixtures
repo          : acme/report-service
target branch : demo
files to push : 1
  src/main/java/com/example/report/ReportService.java  +2 -1
patch         : C:\...\SONAR_ISSUES\demo\changes.patch
issues covered: 1
  002_S1481_ReportService.java_L21 (S1481): Remove this unused 'total' local variable.
[publish] dry-run only - nothing pushed
```

Errors mapped to plain language: `403` → the token can't write (recreate it, re-run
`set_mode.py github`) · conflict list → re-run `/sonar-init` (or `--force`) · `422` →
the branch moved mid-publish, just re-run · exit 2 mentioning the confirmation prompt →
an agent terminal has no stdin: confirm in chat, re-run with `--yes`.

---

## What a complete run leaves on disk (real tree from the demo)

```text
SONAR_ISSUES/demo/
├── summary.json
├── changes.patch                      (GitHub mode, once a fix exists)
├── publish.json                       (GitHub mode, after /publish-to-github)
├── _raw/
│   ├── issues.json
│   ├── meta.json
│   └── rules.json
├── _workspace/                        (GitHub mode)
│   ├── workspace.json
│   ├── orig/src/main/java/...
│   └── edited/src/main/java/...
├── 001_S1068_ReportService.java_L12/
│   ├── context.json
│   ├── issue.json
│   └── issue.md
├── 002_S1481_ReportService.java_L21/
│   ├── context.json
│   ├── issue.json
│   └── issue.md
└── 003_S2095_ReportService.java_L26/
    ├── context.json
    ├── issue.json
    └── issue.md
```

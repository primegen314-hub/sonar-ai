# TESTING MANIFEST — Local | GitHub workflow rework (v3: fast solve, opt-in verify)

Check off each scenario to confirm every path works. Scenarios are ordered so each one
builds on the previous. Commands run from the **repository root**.

Legend:
- ✅ **auto-verified** — already proven by automated runs on this branch (offline fixtures
  + a mock GitHub API server + a scratch git repo). Re-run them if you want, but they are
  known-good.
- 🖐 **needs your environment** — requires your real SonarQube server and/or a real
  GitHub repository. These are the ones that genuinely need manual testing.

Shortcut used below: `SK=.github/skills/sonar-issues`

**Resetting between scenarios**: delete `SONAR_ISSUES/` and (when you want the mode
question to be asked again) delete `$SK/.env`. Both are git-ignored — deleting them is
always safe.

---

## A. Offline smoke tests (no network, no credentials) — ✅ auto-verified

| # | Scenario | Steps | Expected |
|---|---|---|---|
| A1 | ☐ Local pipeline baseline | `python $SK/run_all.py --fixtures --branch demo` | Ends with `validation OK` + `Pipeline complete.`; `SONAR_ISSUES/demo/` has 3 issue folders, `summary.json` contains `"workflowMode": "local"` |
| A2 | ☐ Mode surfaced to skills | `python $SK/pick_issue.py --list --fixtures --branch demo` | Header shows `mode: local`; issue printouts show a `mode :` line |
| A3 | ☐ GitHub extraction offline | put in `$SK/.env`: `WORKFLOW_MODE=github`, `CONTEXT_SOURCE=github`, `GITHUB_ORG=x`, `GITHUB_REPO=y` → `python $SK/run_all.py --fixtures --branch demo-r` | Pipeline completes; `[s02] mode : github`; issue printouts show a `workspace:` line |
| A4 | ☐ Workspace fetch + patch | `python $SK/workspace.py fetch src/main/java/com/example/report/ReportService.java --branch demo-r --fixtures` → edit the printed `edited/` file → `python $SK/workspace.py diff --branch demo-r --fixtures` | Fetch prints the `edited/` path; diff prints a per-file `+N -N` stat; `SONAR_ISSUES/demo-r/changes.patch` exists and `git apply --check` accepts it against a pristine copy of the source |
| A5 | ☐ Publish dry-run offline | `python $SK/publish.py --dry-run --branch demo-r --fixtures` | Prints repo, target branch, files + diffstat, issues covered; exits 0; nothing pushed |
| A6 | ☐ Fixtures never write to the network | `python $SK/publish.py --branch demo-r --fixtures --yes` | Refuses: "--fixtures is offline - only --dry-run is allowed" |
| A7 | ☐ Verify refuses in GitHub mode | `python $SK/verify.py --issue 2 --branch demo-r --fixtures` | Red message "no fixed code here to test ... verify after publishing", **exit code 4** (`echo $?`) |
| A8 | ☐ Unpublished edits block re-init | with the dirty workspace from A4: `python $SK/steps/s02_fetch_issues.py --fixtures --branch demo-r` | Refuses: "Unpublished workspace changes exist"; re-running with `--discard-workspace` deletes them and proceeds |
| A9 | ☐ Publish refuses in local mode | set `WORKFLOW_MODE=local` in `$SK/.env` → `python $SK/publish.py --branch demo --fixtures` | "publish is github-mode only - commit and push with git yourself", exit 2 |
| A10 | ☐ Workspace refuses in local mode | same `.env` → `python $SK/workspace.py status --branch demo --fixtures` | "The workspace is a github-mode concept", exit 2 |
| A11 | ☐ Mode gate for skills | delete `$SK/.env` → `python $SK/set_mode.py --show` | "mode : not set", **exit 2** (this is how /sonar-init knows to ask the mode question) |
| A12 | ☐ Branch listing shows modes | after A1+A3: `python $SK/pick_issue.py --branches --fixtures` | Each line shows `mode: local` / `mode: github` |
| A13 | ☐ Publish non-tty guard | github `.env` → `python $SK/publish.py --dry-run --branch demo-r --fixtures < /dev/null` runs fine; the real (non-fixtures) no-`--yes` path in a non-tty shell | Exit 2 with the message telling the agent to confirm in chat and re-run **with `--yes`** — never a stack trace |
| A14 | ☐ `remote` alias still accepted | `.env` with `WORKFLOW_MODE=remote` (+ `GITHUB_*`) → `python $SK/pick_issue.py --branches --fixtures` and `python $SK/set_mode.py --show` | Everything behaves as `github` (shown as `mode: github`); no warning about an unknown mode |
| A15 | ☐ set_mode local asks nothing | `python $SK/set_mode.py local` (inside a git repo) | Writes `WORKFLOW_MODE=local` without asking for or checking out any branch; never runs `git checkout`/`git pull` |
| A16 | ☐ set_mode github without a checkout | in a scratch folder with **no `.git`**: `python $SK/set_mode.py github --repo-url https://github.com/acme/x --token t` | Completes: `WORKFLOW_MODE=github`, org/repo parsed from the URL; no error about a missing git repo |
| A17 | ☐ URL deep links parse correctly | `--repo-url "https://github.com/Org/dotted.repo.name/tree/my-branch-v2"` (unit-covered in the test suite) | org=`Org`, repo=`dotted.repo.name`, `GITHUB_BRANCH=my-branch-v2` auto-set; a GHE host auto-sets `GITHUB_API_URL=https://<host>/api/v3` |

## B. Back-compat / regression (nothing existing breaks) — ✅ auto-verified

| # | Scenario | Steps | Expected |
|---|---|---|---|
| B1 | ☐ No `.env` at all | delete `$SK/.env` → run A1 | Works exactly as before this change (defaults to local) |
| B2 | ☐ Legacy `.env` (pre-rework) | `.env` containing only `CONTEXT_SOURCE=github` + `GITHUB_*` (no `WORKFLOW_MODE`) | Still works — mode is derived (`github`) with a warning suggesting `set_mode.py`; nothing crashes |
| B3 | ☐ Inconsistent `.env` | `WORKFLOW_MODE=github` + `CONTEXT_SOURCE=local` | Warning "WORKFLOW_MODE wins"; behaves as github |
| B4 | ☐ Solve progress survives re-runs | run A1 → write a `resolution.json` into one issue folder → run A1 again | `[s02] ... kept 1 resolution(s)`, `[s04] restored 1/1`; `--list` still shows it `[fixed]` |
| B5 | ☐ `--next` behavior unchanged | resolve all 3 issues → `python $SK/pick_issue.py --next --fixtures --branch demo` | "All issues are resolved", exit 2 |
| B6 | ☐ Selectors unchanged | `pick_issue.py 3`, `pick_issue.py 003_S2095`, `pick_issue.py <sonar-key>` | All three locate the same issue |
| B7 | ☐ verify unchanged in local mode | `TEST_COMMAND=echo ok` in `.env` → `python $SK/verify.py --full --branch demo --fixtures` | Runs the command, prints PASSED, exit 0 |
| B8 | ☐ `--set-command` allowed in GitHub mode | github `.env` → `python $SK/verify.py --set-command "mvn -B test"` | Saved to `.env` (only running tests is blocked in GitHub mode, not configuring them) |
| B9 | ☐ New `--discard-workspace` flag is accepted by every step | `python $SK/steps/s05_build_context.py --fixtures --branch demo --discard-workspace` | No argparse error (run_all forwards all flags to all steps) |
| B10 | ☐ Old summaries (`"workflowMode": "remote"`) | keep a branch folder extracted before the rename → `pick_issue.py --list/--branches` | Shown as `mode: github`; workspace paths still resolve |
| B11 | ☐ Quick compile check | `BUILD_COMMAND=echo ok` in `.env` → `python $SK/verify.py --compile --branch demo --fixtures` | Runs the command, prints COMPILES, exit 0; github mode exits 4; no BUILD_COMMAND + no derivable runner → exit 3 with guidance |
| B12 | ☐ Backlog report + fix roadmap | `python $SK/pick_issue.py --stats --fixtures --branch demo` | `by rule:` rows (count, sev/rec/eff tallies), `fix roadmap` footer: quick-wins step (rec:sonar+eff:normal count), same-rule batch steps (clusters ≥3), hard tail by severity; resolved issues excluded from all counts; closing verify+commit line |

## C. Local mode, live — 🖐 needs your Sonar + a real checkout

| # | Scenario | Steps | Expected |
|---|---|---|---|
| C1 | ☐ First-run mode question | delete `$SK/.env`, then in Claude Code: `/sonar-init <your-sonar-url>` | Asks to fill `SONAR_USER`; then ONE dropdown: `Local (Recommended) | GitHub`. Choose **Local** — NO branch question follows |
| C2 | ☐ Branch comes from the URL / checkout | paste a Sonar URL containing `branch=` while on a different branch | The gate stops with exactly ONE command (`git checkout <branch> && git pull`), offered as a terminal command you approve; after running it, re-run succeeds |
| C3 | ☐ Mode never asked again | run `/sonar-init` a second time | No mode dropdown — it goes straight to extraction |
| C4 | ☐ Sonar-branch mismatch | point Sonar at a project where the analyzed branch name differs from the git branch name | Clean red error: "Sonar has no branch '<x>' ... set_mode.py --sonar-branch"; the skill asks for the Sonar name, saves `SONAR_BRANCH`, re-runs, extraction works; the sync gate still checks the GIT branch |
| C5 | ☐ Out-of-sync gate = ONE command | on the analyzed branch, `git reset --hard HEAD~1` → `/sonar-init` | Red OUT OF SYNC error with exactly `git pull` as the remedy — no mode-switch offer, no ".env yourself" offer |
| C6 | ☐ Solve runs ZERO tests | `/sonar-issue-pick` → fix one issue | Fix edits your checkout; a one-line `git diff --stat` is shown as proof; NO verify question, NO test run; the session ends pointing at `/sonar-verify` |
| C7 | ☐ /sonar-verify end-to-end | `/sonar-verify` after C6 | Full suite runs; first time ever you're asked the test command ONCE (then saved); on failure you get the 4-option menu (bisect recommended) and the AI does NOT debug on its own |
| C8 | ☐ Local mode ships via git | after solving | The skills do NOT push; `/publish-to-github` refuses in local mode; you `git commit` + `git push` yourself |
| C9 | ☐ No `.git` in local mode | run `/sonar-init`, choose Local, in a folder without `.git` | One sentence: open the project repository folder and retry — no GitHub-mode switch offered mid-flow |

## D. GitHub mode, live — 🖐 needs your Sonar + a real GitHub repo (use a THROWAWAY repo/branch first)

| # | Scenario | Steps | Expected |
|---|---|---|---|
| D1 | ☐ Token setup in your terminal | delete `$SK/.env` → `/sonar-init <url>` → choose **GitHub** | You are told to run `python $SK/set_mode.py github` in YOUR terminal; hidden token prompt; org/repo derived from `origin`; a classic token without `repo` scope triggers an immediate warning |
| D2 | ☐ Works with NO `.git` anywhere | in a folder that is not a git repo: `set_mode.py github` (paste the repo URL at the prompt) → `/sonar-init <url with branch=>` → solve → publish | The ENTIRE flow completes without ever needing a checkout — this is the headline promise of GitHub mode |
| D3 | ☐ Checkout is irrelevant | check out any unrelated branch → `/sonar-init <url>` with `branch=` in the URL | Extraction succeeds regardless of the checkout; `mode: github` everywhere |
| D4 | ☐ Fix goes to the workspace only | `/sonar-issue-pick` → fix an issue | `workspace.py fetch` runs first; ONLY `SONAR_ISSUES/<branch>/_workspace/edited/...` changes — `git status` in your checkout stays clean AND the AI says so explicitly ("your checkout is untouched"); `changes.patch` updates after the fix; no verify question is asked |
| D5 | ☐ Publish end-to-end | `/publish-to-github` | Dry-run preview (files + diffstat + issues) → target-branch dropdown → explicit push confirmation → the AI runs publish.py WITH `--yes` → ONE commit appears on GitHub containing all changed files; commit URL reported; `publish.json` written |
| D6 | ☐ Publish to a NEW branch | in D5 choose "a new branch" | Branch is created from the analyzed branch head, commit lands on it |
| D7 | ☐ Conflict protection | after extraction + a fix, push some other change to the same file on GitHub (web UI), then `/publish-to-github` | Refuses, listing the drifted file; offers re-init (recommended) or `--force` |
| D8 | ☐ Read-only token rejected | repeat D5 with a read-only token | Clean message: token "needs write access ... run set_mode.py github again" — no partial push |
| D9 | ☐ Workspace clean after publish | after D5: `python $SK/workspace.py status --branch <b>` | Reports clean; a second `/publish-to-github` says "nothing to publish"; re-running `/sonar-init` no longer complains about unpublished edits |
| D10 | ☐ Sonar clears after CI | wait for CI on the target branch | The published fixes disappear from Sonar for that branch |

## E. Skill-level dropdown flows (Claude Code / Copilot) — 🖐 manual

| # | Scenario | Expected |
|---|---|---|
| E1 | ☐ `/sonar-issues-solve` interactive, local | Dropdowns in order: interactive/automated → AI effort (once) → per-issue fix approach → keep/delete folder → cleanup offer at the end. NO verify dropdowns anywhere. Phase progress announced ("issue 3/12"). Matches the FLOWS.md diagrams 1-to-1 |
| E2 | ☐ `/sonar-issues-solve` interactive, github | Same; after every fix the AI states the checkout is untouched; at the end it points to `/publish-to-github`; cleanup only offered after `publish.json` exists |
| E3 | ☐ `/sonar-issues-solve` automated, both modes | No per-issue prompts, no test runs; unfixable issues recorded as skipped (github: workspace copy restored); report at the end |
| E4 | ☐ Skills never touch secrets | at no point does the AI read or print `.env`, the token, or your password; tokens/passwords are only ever typed into YOUR terminal (hidden) |
| E5 | ☐ Mode switch mid-project | tell the AI "switch to github mode" | It points you at `set_mode.py github` and requires re-running `/sonar-init` — it does not improvise, and it NEVER offers a switch on its own (e.g. at the sync gate) |
| E6 | ☐ `/sonar-verify` failure menu | make a test fail on purpose → `/sonar-verify` | The 4-option menu appears (bisect recommended); the AI investigates ONLY if you pick `investigate` |
| E7 | ☐ Phantom-fix guard | watch any local-mode fix | `git diff --stat -- <file>` shown before `resolution.json` is written; an empty diff triggers a retry, not a `fixed` record |
| E8 | ☐ Choice menus, Copilot | run any skill choice in VS Code Copilot chat | The exact numbered-menu format renders (`❓` + numbered options, recommended first, "Reply with a number") — never a prose "tell me how you'd like to proceed" |
| E9 | ☐ Fallout sweep | pick a removal-type issue (e.g. remove a never-thrown exception) | The fix also removes the now-unused import / dangling javadoc in the same edit; a Sonar re-scan reports no NEW issue caused by the fix |
| E10 | ☐ `/sonar-batch-fix` subset forms | try `3,5`, a range `1-2`, a rule id, a severity | Only matching unresolved issues are fixed; unknown selector reported, not guessed; report shows fixed/skipped/still-unresolved |
| E11 | ☐ `/sonar-quick-wins` | run on a tree with mixed rec:/eff: values | Only `rec:sonar` + `eff:normal` issues are touched; "left for you" lists every remaining unresolved issue with its flags |
| E12 | ☐ Recommended + descriptions on EVERY menu | watch any session's choices (mode, fix approach, effort tier, verify failure, cleanup) | Each menu marks exactly one option `(Recommended)` listed first with a one-line why, and every option carries a one-line what-happens description |
| E13 | ☐ `/sonar-verify` offers cleanup | run a passing `--full` verify in local mode | After PASSED it offers `[keep] (Recommended when issues remain)` / `[cleanup]`; scoped runs and failures never offer it |
| E14 | ☐ Honesty rule | watch any fix report/hand-off, especially on a smaller model | The AI never claims a fix "works"/"compiles"/"is correct" — only "edit applied" (with diff) and, after `/sonar-verify`, its actual result; hand-off suggests the quick compile check |
| E15 | ☐ Anytime reference | with rules files PRESENT, paste a reference class mid-session | The AI extracts and follows its conventions for the session (reference wins on conflict) and offers to merge into `instructions.md` — no re-asking later |
| E16 | ☐ `/sonar-roadmap` | run it after init on a mixed tree | Shows the `--stats` report verbatim (never re-derived/reordered) + ONE menu: `[Start step 1] (Recommended)` / `[Just wanted the report]`; read-only — nothing fixed unless the user starts a step; the other skills are unchanged and never invoke or push it |

## F. Docs sanity — 🖐 manual, 2 minutes

| # | Scenario | Expected |
|---|---|---|
| F1 | ☐ FLOWS.md renders | open FLOWS.md in a mermaid-capable viewer (GitHub web UI works): all 7 diagrams render; the first ("whole journey") shows every dropdown per mode and contains no verify step inside solving |
| F2 | ☐ README answers "what do I need?" | a colleague can start from `.github/skills/sonar-issues/README.md` "Before you start" alone, for either mode |
| F3 | ☐ `.env.example` sections | required-before-first-run vs GitHub-only vs set-automatically vs optional — matches what the pipeline actually does |
| F4 | ☐ CONTEXT.md matches reality | every glossary term (GitHub Mode alias, Verify, Phantom-Fix Guard, Phase Protocol) matches how the skills and scripts actually behave |

---

## What was already validated automatically (summary)

- **E2E demo**: `python .github/skills/sonar-issues/tests/e2e_demo.py` — 11 stages
  covering the whole journey in both modes offline (init → solve → guards → verify →
  publish preview). Green as of 2026-08-19.
- **Regression suite**: `python -m unittest discover .github/skills/sonar-issues/tests`
  — 21 tests covering most A/B rows above plus the composite complexity score (the
  `ai effort:` tier now comes from usedBy/co-change/type/severity/tests, with Sonar's
  minutes as a minor factor; reason strings name the factors) (pipeline both modes, all mode/tty gates,
  `remote` alias, no-`.git` github setup, single-command sync gate, effort tiers, URL
  and repo-ref parsing). Green as of 2026-08-19; run it after any script change.
- **Compile check** of every Python file; full fixtures pipeline green in both modes.
- **Regressions**: no-`.env` default, legacy `.env` derivation, inconsistent `.env`
  warning, `remote` alias normalization, resolution stash/restore across re-runs,
  `--next`/selectors, verify with `TEST_COMMAND`, `--set-command` in GitHub mode, flag
  forwarding through `run_all.py`.
- **GitHub e2e over real HTTP against a mock GitHub API** (from the previous round; the
  publish path is unchanged apart from messages): workspace fetch (contents API), full
  publish (blobs → tree → commit → ref update), publish.json + workspace re-baseline
  ("nothing to publish" on second run), conflict detection via blob SHAs, `--force`
  override, new-branch creation (`refs` POST), 403 → actionable token message, token
  scope probe warning.
- **Patch format**: generated `changes.patch` passes `git apply --check` against
  pristine sources.

The only things that cannot be validated from this environment are the 🖐 rows: your
real SonarQube server, a real GitHub repository (D-series), and the interactive
dropdown UX (C/E-series). D2 (no `.git` anywhere) and D5–D8 on a throwaway repo are the
highest-value manual tests.

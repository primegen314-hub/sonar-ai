# sonar-issues — SonarQube Issue Extraction & Solving Pipeline

A deterministic, step-by-step **Python pipeline** (stdlib only — no `pip`, no `curl`, no `gh`)
that pulls issues from SonarQube, materializes them as a reviewable folder tree, and lets
AI skills fix them — **in your checkout (Local mode)** or **entirely through the GitHub
API (GitHub mode)**, your choice.

This folder (`.github/skills/sonar-issues/`) is the **canonical scripts home** shared by all
sonar skills, for both GitHub Copilot and Claude Code (the `.claude/skills/` entries are thin
wrappers pointing here).

**Why scripts + skills instead of just prompting an AI?** Every decision that can be
computed is computed by a script — URL parsing, branch resolution, sync checking, issue
ranking, fix recommendation, effort tiering, diffing, conflict detection, publishing.
The AI only reads short script output and writes the actual code fix. That is what makes
sessions fast and consistent **on any agent model**: a weaker model executing
`pick_issue.py --next` and fixing one flagged line performs nearly as well as a stronger
one, because nothing is left to interpretation. And solving is never interrupted by test
runs — verification is its own user-invoked step (`/sonar-verify`).

## Documentation

| Doc | Read it when you want... |
|---|---|
| **[FLOWS.md](FLOWS.md)** | to SEE how it works — the whole-journey diagram (every dropdown you'll be asked, per mode), one diagram per skill, worked examples |
| **[USAGE.md](USAGE.md)** | the per-script runbook — every flag, real captured demo output |
| **[RECOVERY.md](RECOVERY.md)** | the AI error playbook — every known failure mapped to one exact action (skills read it only when a script fails) |
| this README | how to run it, what you need per mode, install, security, troubleshooting |

## How to run it (the short version)

1. **Always start with `/sonar-init <pasted-sonar-url>`.** It sets up `.env`, asks the
   ONE mode question (Local | GitHub — asked once, remembered), and extracts the issues
   into `SONAR_ISSUES/<branch>/`. Every other skill needs this to have run first.
2. **Solve**: `/sonar-issues-solve` (all issues, interactive or automated) or
   `/sonar-issue-pick 3` (one issue). Fast by design: no test runs, no checkout
   mutations — fixes only.
3. **Verify** (Local mode): `/sonar-verify` — runs the project's tests once, when YOU
   are ready (recommended: after all issues are solved). On failure it bisects per
   issue with scoped test runs.
4. **Ship the fixes**:
   - **Local mode**: commit and push with git as usual.
   - **GitHub mode**: `/publish-to-github` — it previews the changes and, after your
     explicit confirmation, commits them to the branch you choose. CI then re-analyzes
     and Sonar clears the issues.

## The two modes — what you need BEFORE you start

You are asked once, during `/sonar-init`. Choose by answering: *"can I check out the
analyzed branch on this machine?"*

### Local mode (recommended when you have the checkout)

Before you start, you need:
- **Your Sonar URL and Sonar username** (the password is prompted hidden, once).
- **A git checkout of this repository.** The branch is resolved per run — from the
  Sonar URL's `branch=` parameter, or your current checkout. If the checkout is on the
  wrong branch or behind origin, the pipeline stops and prints the exact
  `git checkout ... && git pull` command for you to run (it never mutates your checkout
  itself).

What happens: fixes edit your working tree directly; you verify with `/sonar-verify`
when ready and **push with git yourself** when done.

### GitHub mode (no checkout needed at all)

Before you start, you need:
- **Your Sonar URL and Sonar username** (same as local).
- **A GitHub token with WRITE access to the repository** (classic: `repo` scope;
  fine-grained: Contents read/write). You enter it in *your own terminal* via
  `python set_mode.py github` — hidden input; the AI never sees it. No git checkout is
  required: without one, the setup simply asks you to paste the repo URL.

What happens: source code is read via the GitHub API; fixes are applied to copies in
`SONAR_ISSUES/<branch>/_workspace/` and collected in a reviewable `changes.patch` —
**your checkout (if any) stays untouched, so `git diff` showing nothing is expected**.
`/publish-to-github` pushes the fixes as ONE atomic commit to the branch you choose.
**Tests do not run locally** — CI verifies after the publish.

(`remote` is accepted everywhere as a permanent alias for `github` — older `.env` files
keep working.)

### What gets set automatically DURING the session

You never edit these — the scripts write them into the skill `.env`:

| Key | Written by | When |
|---|---|---|
| `WORKFLOW_MODE`, `CONTEXT_SOURCE` | `set_mode.py` | the one-time mode question |
| `SONAR_TOKEN` | `s01_setup_auth.py` | first run (minted from your LDAP login) |
| `SONAR_BRANCH` | `set_mode.py --sonar-branch` | only if Sonar names the branch differently than git |
| `TEST_COMMAND` | `verify.py --set-command` | first `/sonar-verify` (asked once, reused forever) |

Full annotated key list: [.env.example](.env.example) — it is organized into
"required before first run" / "GitHub-mode only" / "set automatically" / "optional".

## Mode comparison

| | Local | GitHub |
|---|---|---|
| Needs a git checkout | yes (you run the printed git commands yourself) | no — checkout irrelevant |
| Code is read from | your working tree | the GitHub API |
| Fixes land in | your working tree | `_workspace/` copies + `changes.patch` |
| Tests | `/sonar-verify`, when you choose | in CI, after publishing |
| Reaches GitHub via | you: `git commit` + `git push` | `/publish-to-github` (confirmed API commit) |
| GitHub token | not needed | required, WRITE access |

## Install in another repository (drop-in)

1. Copy `.github/skills/` (this folder and the seven skill folders) into the target repo.
   Optionally copy `.claude/skills/` too for Claude Code (real dropdowns via AskUserQuestion).
2. Add to that repo's `.gitignore`:
   ```
   SONAR_ISSUES/
   .env
   ```
3. Copy `.env.example` to `.env` **in this same folder** and fill in `SONAR_HOST` +
   `SONAR_USER`. The `.env` deliberately lives inside the skill folder — a host repo's
   own root `.env` is never read or touched. Everything else can stay empty:
   `/sonar-init` fills in the rest (mode, token, branch, filters from the pasted URL).

### Regression tests (stdlib unittest, ~3 seconds, no network)

```
python -m unittest discover .github/skills/sonar-issues/tests
```

17 tests: URL parsing, mode normalization (`remote` alias), repo-ref parsing, effort
tiers, and the real gates run against fixtures in an isolated temp copy (pipeline both
modes, verify exit 4, publish/workspace mode gates, non-tty `--yes` guard, no-`.git`
GitHub setup, the single-command sync gate). Run this after ANY script change.

### End-to-end demo (~10 seconds, no network)

```
python .github/skills/sonar-issues/tests/e2e_demo.py
```

Walks the WHOLE journey offline and prints PASS/FAIL per stage — Local: init → brief →
fix in a real scratch git checkout → phantom-fix guard (`git diff --stat`) → resolution
→ full verify → 1/3 fixed report; GitHub (via the `remote` alias): init without a
checkout → workspace fetch → fix → `changes.patch` validated with `git apply --check` →
publish `--dry-run` preview → verify exit 4 by design.

### Offline demo (no network, no credentials)

```
python .github/skills/sonar-issues/run_all.py --fixtures --branch demo-branch
```

Runs the full pipeline against bundled sample API responses in `fixtures/` and produces a
complete `SONAR_ISSUES/demo-branch/` tree you can inspect.

## Output

```
SONAR_ISSUES/                          (repo root, git-ignored)
└── <branchRef>/                       regenerated on every run (resolutions survive)
    ├── summary.json                   brief view of every issue + totals + the mode
    ├── changes.patch                  GITHUB MODE: cumulative reviewable diff of all fixes
    ├── publish.json                   GITHUB MODE: written after /publish-to-github pushed
    ├── _raw/                          raw API responses + resolved run parameters
    │   ├── issues.json
    │   ├── rules.json
    │   ├── meta.json
    │   └── resolutions.json           stash used to restore progress across re-runs
    ├── _workspace/                    GITHUB MODE: where fixes are made
    │   ├── workspace.json             manifest (base commit, per-file blob SHAs)
    │   ├── orig/<path>                pristine copies as fetched from GitHub
    │   └── edited/<path>              the copies the fixes edit
    └── 001_S1481_ReportService.java_L42/     one folder per issue
        ├── issue.md                   human-readable, mirrors the Sonar web UI
        ├── issue.json                 machine contract (key, rule, location, message, ...)
        ├── context.json               AI solving context (tests, used-by, co-changed, ...)
        └── resolution.json            written by the solving skills (fixed/skipped)
```

Issue folders are named `{NNN}_{ruleId}_{fileName}_L{line}` so you can visually match a
folder to what the SonarQube web UI shows; the full issue key and a deep link back to the
UI are inside `issue.json`.

Each issue also carries a deterministic **`recommended` flag** (`sonar` | `ai`, with a
reason): `ai` when the rule's language doesn't match the file (a rule that doesn't really
apply to e.g. frontend code) or the rule ships no compliant example — the solving skills
present that option first, so neither the user nor the AI wastes time (or tokens) deciding.

## The scripts — what each does and why it makes you faster

Six standalone step scripts (`s01` auth → `s02` fetch+branch gate → `s03` rules →
`s04` folders → `s05` context → `s06` summary) chained by `run_all.py`, plus the helpers
the skills drive:

| Script | Does | Why it speeds you up |
|---|---|---|
| `run_all.py` | the whole extraction from one pasted Sonar URL | one command replaces a dozen API calls the AI would otherwise improvise (and get subtly wrong) |
| `set_mode.py` | the one-time mode choice: `local` (asks nothing), `github` (hidden token prompt, works without a checkout), `--show`, `--sonar-branch` | mode is decided once and read forever — no per-session re-negotiation |
| `pick_issue.py` | list/locate issues (`--list`, `--next`, `--branches`, selector) — prints the `mode:` line, the `recommend:` fix and the `ai effort:` tier the skills obey | the AI's whole "menu phase" is one short script output — zero file reads, zero guessing at folder names |
| `verify.py` | scoped/full test runs, `--set-command`; refuses in GitHub mode (exit 4 — CI verifies) | tests run exactly once per session, when the user invokes `/sonar-verify` — and a failure is bisected per issue with the pre-computed `testFiles`, not debugged blind |
| `workspace.py` | GitHub mode: `fetch` a file to fix, `diff` (rebuild `changes.patch`), `status`, `discard` | byte-exact copies + wholesale diff regeneration mean the patch is always consistent with the edits, no manual diff bookkeeping |
| `publish.py` | GitHub mode: preview (`--dry-run`) and push the workspace changes as ONE atomic commit via the Git Data API | all-or-nothing publishing with blob-SHA conflict detection — no half-pushed states, no silent overwrites of colleagues' work |

**Every flag and real captured output for each script: [USAGE.md](USAGE.md).**

## Security

- **Best practice: don't put the password in `.env` at all.** Leave `SONAR_PASSWORD`
  empty — `s01` prompts for it interactively (hidden input, memory only, never written
  anywhere) and uses it once to mint the token.
- If you do put it in `.env`, `s01` **automatically clears it** from the file right after
  the token is minted. The token is what stays on disk — it acts as your user but can be
  revoked anytime in Sonar → My Account → Security (tokens are named `sonar-issues-...`).
- **The GitHub token (GitHub mode) can WRITE to your repository.** Prefer a fine-grained
  PAT scoped to the ONE repository with only Contents read/write. It is entered via a
  hidden prompt in your terminal (`set_mode.py github`), stored only in the skill `.env`
  (git-ignored), and **nothing is ever pushed without an explicit confirmation step** in
  `/publish-to-github`. Revoke it in GitHub → Settings → Developer settings when done.
- `.env` is git-ignored (with `*.token`, `*.pat`) so it cannot be committed; `SONAR_ISSUES/`
  is git-ignored too because issue snippets (and GitHub-mode workspace copies) contain
  private source.
- No script ever prints a password or token, and the AI skills are instructed to never
  read `.env` — credentials flow only through the Python scripts.
- Never paste a password or token into an AI chat; if you ever suspect exposure, revoke
  the token (Sonar UI / GitHub settings) and change your LDAP password.

## Notes & troubleshooting

- **Old vs new SonarQube**: the pipeline probes `api/server/version` and automatically
  uses `issueStatuses`/`inNewCodePeriod` (≥ 10.4) or `statuses`/`sinceLeakPeriod` (older).
- **Proxy**: direct connection first; on DNS/connect failure the Windows proxy is
  auto-detected (registry static proxy, then PAC) and the request retried. Sonar is on the
  internal network and normally needs no proxy; `api.github.com` typically does.
- **SSL errors** against the internal Sonar certificate: set `SONAR_VERIFY_SSL=false` in `.env`.
- **"Sonar has no branch X"** (local mode): git and Sonar name the branch differently —
  `python set_mode.py --sonar-branch <sonar-name>` and re-run.
- **"OUT OF SYNC with origin"** (local mode): Sonar analyzed the pushed state — run the
  printed `git pull` and re-run the pipeline (`SYNC_CHECK=false` in `.env` disables the
  gate when offline).
- **"Unpublished workspace changes exist"** (GitHub mode re-run): publish them first
  (`/publish-to-github`) or re-run with `--discard-workspace` to drop them.
- **HTTP 403 despite a valid token** (github mode, often at the branch gate): in
  SSO-protected orgs a token must additionally be AUTHORIZED for the org — GitHub →
  Settings → Developer settings → your token → "Configure SSO" → Authorize. Also check
  `repo` scope and, on GitHub Enterprise, `GITHUB_API_URL=https://<host>/api/v3`.
- **Publish says the token can't write (403)**: the token is read-only — recreate it with
  write access (and SSO-authorize it) and re-run `set_mode.py github`.
- **Pasting repo URLs**: `set_mode.py github --repo-url` accepts deep links too —
  `https://github.com/org/repo/tree/<branch>` sets `GITHUB_BRANCH` automatically, and a
  GitHub Enterprise host auto-derives `GITHUB_API_URL`.
- **Publish exits 2 mentioning the confirmation prompt**: an agent terminal has no
  interactive stdin — confirm in chat, then re-run the same command with `--yes`.
- **`git diff` shows nothing after GitHub-mode fixes**: expected — the fixes live in
  `SONAR_ISSUES/<branch>/_workspace/edited/` (git-ignored) until `/publish-to-github`.
- **Unicode** (`&#39;`-style escapes in Sonar messages) is decoded by standard JSON
  parsing; all output files are UTF-8.
- **10k cap**: the Sonar API returns at most 10 000 issues; the fetch warns when truncated.
- Security Hotspots are out of scope for now (separate API); the schemas leave room for them.

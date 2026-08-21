# RECOVERY — the error playbook for AI agents

Read this file ONLY when a script just failed. Find the error below, apply the ONE
mapped action, and continue the skill where you left off. Iron rules:

- **One retry maximum** for anything that looks transient (network hiccup, 422). If the
  retry fails too, stop and show the user the error verbatim.
- **Never** edit `.env` directly, never switch workflow modes to escape an error, never
  start a root-cause investigation on your own.
- **Error not listed here** → show it verbatim, tell the user which step you were on,
  and ask how to proceed. Stopping cleanly IS correct behavior.

## Extraction (run_all.py / s01–s06)

| Error you see | Exact action |
|---|---|
| `Workflow mode is not configured` (exit 2) | Run the `/sonar-init` mode phase (`set_mode.py --show` → ask the mode question), then re-run the same command. |
| `No Sonar host` / `No project key` | Ask the user to paste their full Sonar URL (it contains both), re-run with it. |
| `No branch ref` | Local: re-run from inside the checkout or pass `--branch`. GitHub: ask the user for the branch (or a URL containing `branch=`), pass `--branch`. |
| `Sonar has no branch '<x>'` | Ask the user for the Sonar-side branch name → `python set_mode.py --sonar-branch <name>` → re-run the pipeline. |
| `!= checked-out git branch` or `OUT OF SYNC with origin` | Offer the ONE git command printed in the error as a terminal command the user approves (copy-paste block if you can't run terminal commands). After it runs, re-run the pipeline. Do NOT offer a mode switch. |
| `Branch '<x>' does not exist on GitHub` | Sonar and GitHub branch names often differ slightly (e.g. a `-v2` suffix on GitHub only). The user finds the exact name in the GitHub UI → `GITHUB_BRANCH` via `set_mode.py github --branch <name>` (user's terminal) → re-run. |
| `HTTP 403` from `api.github.com/.../branches/...` (github-mode branch gate) | The token cannot access the repo. Relay the error's checklist: (1) `repo` scope / Contents read-write, (2) **SSO orgs: the token must be AUTHORIZED** — token page → "Configure SSO" → Authorize the org (a valid token still 403s without this), (3) GHE: `GITHUB_API_URL=https://<host>/api/v3`. The user fixes the token in their own terminal (`set_mode.py github`), then re-run. Do not retry blindly — 403 never fixes itself. |
| `Unpublished workspace changes exist` | Ask the user: `[/publish-to-github first] (Recommended)` or `[--discard-workspace]` (destroys unpushed fixes — say so). |
| Sonar auth failure (401/403) during fetch | Tell the user their Sonar credentials/token need refreshing: they fix `SONAR_USER` / clear `SONAR_TOKEN` in the skill `.env` themselves, re-run (s01 re-mints). You never touch `.env`. |
| SSL certificate error against Sonar | Tell the user to set `SONAR_VERIFY_SSL=false` in the skill `.env` themselves (internal cert), re-run. |
| Connection/DNS error | Retry once (proxy auto-detection kicks in on retry). Still failing → report: likely VPN/network; stop. |
| `GitHub mode needs GITHUB_TOKEN/ORG/REPO` | The user runs `python set_mode.py github` in their own terminal, then you re-run. |

## Solving (pick_issue.py / editing / workspace.py)

| Situation | Exact action |
|---|---|
| `summary.json ... not found` | Run the init pipeline for that branch (`run_all.py`), then continue the skill. |
| `pick_issue.py --next` exits 2 | Not an error — all issues resolved. Go to the report step. |
| `No issue matches '<sel>'` | Run `--list` and let the user pick from it. |
| Your edit didn't land (empty `git diff --stat`) | Re-read the exact snippet lines and re-apply with a precise match. After 2 failed attempts: record `resolution.json` as `skipped` with reason "edit could not be applied", continue to the next issue — never stall the session on one issue. |
| `workspace.py` exit 2 "github-mode concept" | You are in local mode — edit the checkout directly; do not force workspace commands. |
| `workspace fetch` 404 | The file path or branch is wrong on GitHub — confirm with `issue.json`'s `file` and the branch ref; if they match, the branch content moved: tell the user re-running `/sonar-init` re-extracts against the new state. |

## Verify (verify.py — only ever inside /sonar-verify)

| Situation | Exact action |
|---|---|
| Exit 2 (no TEST_COMMAND, nothing detected) | The one-time test-command setup menu (let AI determine / type it / skip). |
| Exit 3 (no testFiles for a scoped run) | Offer `--full` instead. |
| Exit 4 (github mode) | By design — explain CI verifies after publish. Not an error. |
| Tests FAILED | The 4-option user menu (bisect recommended). NEVER debug without the user picking `investigate`. |

## Publish (publish.py)

| Situation | Exact action |
|---|---|
| Exit 2 mentioning the confirmation prompt | You forgot `--yes` — re-run the same command with `--yes` (only valid after the user confirmed in chat). |
| Exit 2 `Nothing to publish` | Point at `/sonar-issue-pick` / `/sonar-issues-solve`; stop. |
| 403/404 token cannot write | User recreates a write-scope token and runs `set_mode.py github` in their terminal; then re-run. |
| Conflict list (files changed on GitHub) | Ask: `[re-run /sonar-init + re-apply] (Recommended)` or `[--force]` (last-write-wins — say so). |
| 422 branch moved | Re-run publish once. Still 422 → stop and show the user. |

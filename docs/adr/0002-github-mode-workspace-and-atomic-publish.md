# 0002 — GitHub-mode fixes live in a git-ignored workspace and publish as one atomic API commit

## Status

Accepted (2026-08-18)

## Context

GitHub mode's promise is "fix Sonar issues without any local checkout". That requires
(a) somewhere to edit files that does not depend on a git repo, and (b) a way to get the
edits onto GitHub without local git. Two designs were on the table for (b): push each
issue's changes separately (one commit / patch per issue), or one commit for the whole
session. An earlier session also produced real confusion worth recording: users ran
`git diff` after GitHub-mode fixes and saw nothing, concluding the fixes were lost.

## Decision

- Fixes are made on byte-exact copies fetched from the GitHub contents API into
  `SONAR_ISSUES/<branch>/_workspace/` (`orig/` pristine, `edited/` fixed). The whole
  `SONAR_ISSUES/` tree is git-ignored, so the user's checkout — if one even exists — is
  never touched. `changes.patch` (unified diff, `git apply`-compatible) is regenerated
  after every fix as a REVIEW ARTIFACT only.
- `/publish-to-github` pushes the **edited file contents** as ONE atomic multi-file
  commit via the GitHub Git Data API (blob → tree → commit → ref), never the patch and
  never per-issue commits. Blob-SHA conflict detection refuses to overwrite files that
  moved on GitHub since extraction (`--force` overrides).
- Nothing in the GitHub-mode path may require a `.git` folder; `set_mode.py github`
  accepts a pasted repo URL when no git remote exists.

## Consequences

- All-or-nothing publishing: no half-published state when call N of M fails; one commit
  URL covers the session, with per-issue detail in the commit body (`issuesCovered`).
- Per-issue revert on GitHub is coarser (revert the one commit, or re-run a session);
  this was judged acceptable against N× the API calls and failure points.
- `git diff` showing nothing after a GitHub-mode fix is EXPECTED — skills must say so
  after every fix; the Phantom-Fix Guard for this mode is the file appearing in the
  regenerated patch.
- Because confirmation happens in chat, `publish.py` is always run with `--yes` after
  the user confirms (agent terminals have no interactive stdin).

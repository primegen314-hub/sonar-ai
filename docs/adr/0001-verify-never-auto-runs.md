# 0001 — Verification never auto-runs during solving

## Status

Accepted (2026-08-18)

## Context

Earlier versions ran a scoped test verify after every fix (always in automated mode,
optionally in interactive mode) and a full-suite verify at the end of each solving
session; the `xMax` effort tier even ran the full suite after every single fix. In real
sessions — especially on mid-tier agent models — a failing verify dragged the agent into
long, token-hungry root-cause investigations, and test-suite runtime dominated the whole
session. Solving 12 issues could trigger 13+ test runs.

## Decision

No skill ever runs tests automatically. Solving sessions (`/sonar-issues-solve`,
`/sonar-issue-pick`) only: apply the fix, prove the edit landed (Phantom-Fix Guard),
record `resolution.json`, and continue. All verification lives in a dedicated
user-invoked skill, `/sonar-verify`, which the solve skills point to at hand-off. On a
verify failure the USER chooses the next step (bisect per issue with
`verify.py --issue`, change the test command, ask for an investigation, or skip); the
agent never debugs on its own initiative. Effort tiers were redefined as pure analysis
depth.

## Consequences

- Solving sessions are dramatically faster and their cost is predictable — one test run
  per session (or zero), at a moment the user picks.
- A fix that breaks the build is not caught (or auto-reverted) at fix time; it surfaces
  at `/sonar-verify` time and is bisected with scoped runs (`verify.py --issue <n>`),
  which the pipeline pre-computed `testFiles` for.
- `resolution.json.testsRun` is always `[]` at solve time; `/sonar-verify` fills it in.
- Cleanup of a branch folder in local mode is gated on the user reporting a passing full
  verify, not on the solve session itself.

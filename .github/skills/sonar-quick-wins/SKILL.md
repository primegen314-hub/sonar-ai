---
name: sonar-quick-wins
description: Auto-fix the LOW-EFFORT Sonar issues in one automated pass - unresolved issues recommended for the mechanical Sonar suggestion (rec:sonar) with effort tier "normal", optionally restricted to one severity. Clears the easy majority fast and ends with a clear list of the harder issues left. Use when the user says "quick wins", "fix the easy ones", "clear the trivial issues", or wants fast progress on a big backlog.
---

# sonar-quick-wins `[branchRef | sonar-url] [severity]`

Clears the easy majority of a backlog in one automated pass and — just as important —
ends by telling you exactly which harder issues remain.

**Contract reuse**: read `.github/skills/sonar-issues-solve/SKILL.md` FIRST and obey
everything in it — Choice Presentation Contract, token economy, project standards /
Style Snapshot, fallout sweep, phantom-fix guard, resolution.json shape, hand-off,
RECOVERY.md rule. This file only defines what is DIFFERENT: the selection rule and the
report.

## Phases (mirror these as your progress/todo display)

1. Locate tree
2. Select quick wins
3. Automated fix loop ("issue i/N")
4. Report: fixed · left for you

## Steps

1. **Locate the tree** — exactly like sonar-issues-solve step 1.

2. **Select the quick wins** from `pick_issue.py --list --branch <branchRef>`: every
   issue that is
   - `[unresolved]`, AND
   - `rec:sonar` (the rule's compliant example applies mechanically), AND
   - `eff:normal` (low composite complexity),
   - and, when a severity argument was given (`BLOCKER`|`CRITICAL`|`MAJOR`|`MINOR`|`INFO`),
     of that severity only.
   Show the selection ("N quick wins found") and confirm ONCE:
   `[Fix all N] (Recommended)` · `[Show the list first]` · `[Cancel]`.
   Zero matches → say so, show what IS unresolved, stop.

3. **Automated fix loop** — sonar-issues-solve step 5 verbatim (apply the Sonar
   suggestion, fallout sweep, phantom-fix guard, resolution.json; anything that fails
   cleanly twice → `skipped` with reason, continue). No per-issue prompts, no tier
   question (these are all `normal` by selection).

4. **Report** — re-run `--list`, then TWO groups:
   - **fixed** (the cleared quick wins)
   - **left for you** — every remaining unresolved issue with its `--list` line
     (severity, rec:, eff:), so the user knows exactly what was NOT solved and why it
     needs more attention (higher tier, `rec:ai`, or a skip reason).
   Suggest the follow-ups: `/sonar-batch-fix` for a chosen chunk of the remainder,
   `/sonar-issue-pick` for single hard ones, `/sonar-verify` (local) before shipping.
   Cleanup is NOT offered here.

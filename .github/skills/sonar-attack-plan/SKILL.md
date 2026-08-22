---
name: sonar-attack-plan
description: Show the backlog report for a branch - unresolved Sonar issues grouped by rule - plus a pre-computed attack plan (quick wins, then same-rule batches, then the hard tail). Read-only - fixes nothing, changes nothing. Use right after /sonar-init on a big backlog, or when the user says "attack plan", "backlog report", "what should I fix first", or "how do I tackle all these issues".
---

# sonar-attack-plan `[branchRef | sonar-url]`

The battle-map skill: it shows WHERE the backlog is heavy and the fastest correct
order through it — it never fixes anything itself and never launches another skill
without the user choosing to.

Scripts home: `.github/skills/sonar-issues/`. Never read `.env`; never modify anything
under `SONAR_ISSUES/`. **On any script error**: read
`.github/skills/sonar-issues/RECOVERY.md` (only then) and apply the one mapped action;
unlisted errors are shown verbatim — never improvise a recovery.

The Choice Presentation Contract of `sonar-issues-solve/SKILL.md` applies to the one
choice this skill offers (native question tool when the host has one, else the exact
numbered menu).

## Steps

1. **Resolve the branch** exactly like sonar-issue-pick step 1: take `--branch` from
   the message, or a pasted Sonar URL's `branch=` param, or (local mode) the current
   git branch; when in doubt run
   `python .github/skills/sonar-issues/pick_issue.py --branches` and present the
   trees as a choice. No extracted tree → run `/sonar-init` first.

2. **Run the report**:
   `python .github/skills/sonar-issues/pick_issue.py --stats --branch <branchRef>`
   and show its output as-is — the by-rule table AND the numbered attack plan
   (quick wins → same-rule batches → hard tail by severity, with the verify + commit
   gate line). Do NOT re-derive, reorder, or pad the plan — it is deterministic on
   purpose; you may add at most one line of context per step. No other reads: the
   report is the whole token budget of this skill.

3. **Offer, never push**:
   `[Start step 1 of the plan now] (Recommended — biggest slice cleared with the
   least effort)` · `[Just wanted the report]` (stop — every plan line is already a
   copy-paste command the user can run whenever they like).
   If the user starts a step, invoke that step's own skill (`/sonar-quick-wins`,
   `/sonar-batch-fix <rule>`, `/sonar-issue-pick <seq>`) and let ITS instructions take
   over completely. When a step's session ends, remind in one line: quick gate
   (`/sonar-verify` compile-only) + commit (local) or `/publish-to-github` (github)
   before the next chunk — then offer the next plan step the same way.

Everything already resolved (the script says so): say the backlog is clear and point
at `/sonar-verify` (local) or `/publish-to-github` (github) as the remaining step.

The full 200+-issue walkthrough built around this report lives in the repo-root
`USECASE.md`.

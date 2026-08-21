---
name: sonar-batch-fix
description: Fix a chosen SUBSET of extracted Sonar issues in one batch - by comma-separated selectors ("3,5,7-12"), a rule id ("S1481"), or a severity ("BLOCKER"). Built for large projects (hundreds of issues) where you solve in chunks instead of all at once. Use when the user says "batch fix", "fix issues 3 to 12", "fix all the S1481s", or names several issues together.
---

# sonar-batch-fix `[branchRef | sonar-url] <subset>`

The chunking tool for large projects: same fix machinery as `/sonar-issues-solve`, but
restricted to the subset you name — solve 300 issues in controlled chunks of 30–50,
verify per chunk, push per chunk.

**Contract reuse**: read `.github/skills/sonar-issues-solve/SKILL.md` FIRST and obey
everything in it — the Choice Presentation Contract, token economy, project standards /
Style Snapshot, fallout sweep, phantom-fix guard, resolution.json shape, hand-off, and
the RECOVERY.md rule. This file only defines what is DIFFERENT: subset selection and
the report.

## Phases (mirror these as your progress/todo display — todo-list tool when the host
has one, marking each completed; else one-line statuses)

1. Locate tree
2. Resolve subset
3. Session choices (interactive/automated + effort tier)
4. Fix loop (announce "issue i/N of the batch")
5. Report: fixed · skipped · still unresolved

## Steps

1. **Locate the tree** — exactly like sonar-issues-solve step 1 (argument, URL
   `branch=`, current branch, `--branches` when in doubt).

2. **Resolve the subset** from the `<subset>` argument against
   `pick_issue.py --list --branch <branchRef>` output:
   - Comma-separated selectors: sequence numbers, folder prefixes, or Sonar keys
     (`3,5,003_S2095`), each resolved via `pick_issue.py <selector>`.
   - Ranges expand by sequence number: `7-12` → 7,8,9,10,11,12.
   - A rule id (`S1481`) → every unresolved issue of that rule.
   - A severity (`BLOCKER` | `CRITICAL` | `MAJOR` | `MINOR` | `INFO`) → every
     unresolved issue of that severity.
   - Already-resolved matches are skipped silently; a selector matching nothing is
     reported ("no match: <x>") and the rest continue — never guess.
   - Show the resolved batch ("N issues selected: ...") before fixing. Empty batch →
     say so and stop.

3. **Session choices** — as in sonar-issues-solve steps 3 + 3b, with
   `[automated] (Recommended — this is a batch tool)` listed first, then the effort
   tier ONCE (recommended from the `--list` footer).

4. **Fix loop** — sonar-issues-solve steps 4/5 verbatim (fallout sweep, phantom-fix
   guard, resolution.json), iterating ONLY the subset, announcing "issue i/N of the
   batch".

5. **Report** — re-run `--list`, then present THREE groups so nothing is invisible:
   - **fixed** (this batch)
   - **skipped** (this batch, each with its recorded reason)
   - **still unresolved** (everything outside the batch or left over) — count + the
     `--list` lines, so the user always knows exactly which issues remain.
   Hand-off exactly as sonar-issues-solve step 7 (`/sonar-verify` local /
   `/publish-to-github` github). Cleanup is NOT offered here — batches imply more
   work remains.

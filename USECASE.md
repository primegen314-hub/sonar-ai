# Use case: clearing a 200+ issue legacy backlog

You inherited a legacy service. Sonar reports **240 issues** on your branch
(`TASK-3487-report-cleanup`). Here is the fastest way through them with this
toolkit that still keeps quality — the funnel: **report → safe-fix passes →
same-rule batches → hard tail**, with a verify + commit gate between every chunk.

Never try to solve 240 issues in one session. Chunks keep every diff reviewable,
every failure bisectable, and every commit small.

## Step 0 — Extract once

```bash
/sonar-init   # paste your Sonar URL when asked; pick local or github mode once
```

Everything lands under `SONAR_ISSUES/<branch>/` — one folder per issue, all
briefs and recommendations pre-computed. Re-running later is safe: solved issues
stay solved.

## Step 1 — Feed a reference (biggest quality lever, 2 minutes)

Legacy repos rarely have instruction files, so the solving skills will ask once
for reference material. Don't skip it on a big backlog: paste one class that
shows "how good code looks here", or name up to 3 repo files (comma-separated),
or hand over a migration/framework skill doc. Every one of the 240 fixes then
follows those conventions instead of 240 individually-plausible styles. Accept
the offer to save it as `instructions.md` — future sessions pick it up
automatically.

## Step 2 — Get the report and the fix roadmap

```bash
/sonar-roadmap
```

(or run the script directly: `python .github/skills/sonar-issues/pick_issue.py --stats`)

```
branch: TASK-3487-report-cleanup | project: report-service | mode: local | unresolved: 240/240
by rule:
  S1481      x82   sev MAJOR:80 MINOR:2 | rec sonar:82 | eff normal:82 | Remove this unused local variable...
  S1068      x41   sev MAJOR:41         | rec sonar:41 | eff normal:41 | Remove this unused private field...
  S3776      x18   sev CRITICAL:18      | rec ai:18    | eff max:15 high:3 | Refactor to reduce cognitive complexity...
  S2095      x6    sev BLOCKER:6        | rec ai:6     | eff high:6   | Close this resource...
  ...
fix roadmap (fastest correct order - verify + commit between steps):
  1. /sonar-quick-wins                  - 131 safe-fix issue(s) in one automated pass
  2. /sonar-batch-fix S3776             - 18 issue(s), same rule - one chunk, one review
  3. hard tail - 9 issue(s) one at a time, highest severity first: /sonar-issue-pick ...
between steps: quick gate with /sonar-verify (--compile) and commit/publish the chunk.
```

The plan is computed deterministically from the extracted data — the AI only
presents it, so any agent, weak or strong, shows the same plan. It is a
suggestion, never imposed: the skill offers `[Start step 1 now]` or
`[Just wanted the report]`, and every plan line is a copy-paste command you can
run yourself whenever you like.

## Step 3 — Quick wins first (usually 40–60% of a legacy backlog)

```bash
/sonar-quick-wins
```

One automated pass over everything Sonar itself knows how to fix from its own recipe
(`rec:sonar` + `eff:normal`): unused variables/fields/imports, redundant casts,
literal duplication. No prompts per issue; failures are skipped and recorded,
never forced. Then gate it:

```bash
/sonar-verify        # choose the compile-only quick check (seconds)
git add -A && git commit -m "fix(sonar): quick wins - S1481, S1068 (131 issues)"
```

## Step 4 — Same-rule batches for the middle

Fixing 18 instances of ONE rule in one sitting is far faster and more consistent
than 18 issues of 18 different rules — you (and the AI) understand the rule once.

```bash
/sonar-batch-fix S3776
```

Pick `interactive` when the batch is complex (`eff:max`/`xMax` — confirm each
diff), `automated` when it is mostly safe-fix issues. After each batch: compile check,
full `/sonar-verify` if the batch touched risky code, commit, next batch.
Chunks of 30–50 issues are the sweet spot; a rule with 82 hits splits fine with
ranges (`/sonar-batch-fix 1-40`, then `41-82`).

## Step 5 — The hard tail, one at a time

The last few issues are the real engineering: BLOCKER resource leaks, cognitive
complexity in core classes. Take them individually, highest severity first, at
the recommended (high/max/xMax) effort tier:

```bash
/sonar-issue-pick 007
```

Higher tiers widen how much related code the AI reads before fixing (blast
radius, co-changed files, tests) — no tier ever runs tests during solving.

## Step 6 — Finish

- Full `/sonar-verify` (whole test suite) before shipping.
- GitHub mode: `/publish-to-github` pushes all workspace fixes as one atomic
  commit; tests then run in CI.
- Push, let CI re-analyze the branch — Sonar clears the issues on re-scan.
- Accept the cleanup offer to delete `SONAR_ISSUES/<branch>/` once everything
  is verified/published.

## The rhythm that makes 200+ tractable

| Slice | Tool | Session size | Mode |
|---|---|---|---|
| Safe-fix (40–60%) | `/sonar-quick-wins` | all at once | automated |
| Same-rule clusters | `/sonar-batch-fix <rule>` | 30–50 per chunk | automated or interactive |
| Hard tail | `/sonar-issue-pick <seq>` | one issue | interactive, high+ effort |

Between every slice: **compile gate → commit → continue.** You are never more
than one small commit away from a clean, verified state — that is how quantity
stops hurting quality.

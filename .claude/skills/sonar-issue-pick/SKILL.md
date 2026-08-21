---
name: sonar-issue-pick
description: Pick and solve exactly ONE extracted Sonar issue - by selector (sequence number, folder prefix, or Sonar key) or from a filterable menu of all issues. Fast by design - no test runs; verification is a separate user-invoked step (/sonar-verify). Use when the user names a specific sonar issue ("fix issue 3", "solve the S1481 one") or wants to browse the extracted issues and choose.
---

# sonar-issue-pick (wrapper)

The canonical instructions live in the shared agentic folder:
read `.github/skills/sonar-issue-pick/SKILL.md` and follow it exactly.
Scripts home: `.github/skills/sonar-issues/`. In Claude Code, present every choice with
the AskUserQuestion tool (that is the "native question/choice tool" the canonical skill
refers to).

---
name: sonar-issues-solve
description: Solve the extracted Sonar issues for a branch, interactively (one by one with user choices) or automated (all at once). Fast by design - no test runs during solving; verification is a separate user-invoked step (/sonar-verify). Use when the user says "solve sonar issues", "fix the sonar findings", or after sonar-init has produced SONAR_ISSUES/{branchRef}/.
---

# sonar-issues-solve (wrapper)

The canonical instructions live in the shared agentic folder:
read `.github/skills/sonar-issues-solve/SKILL.md` and follow it exactly.
Scripts home: `.github/skills/sonar-issues/`. In Claude Code, present every choice with
the AskUserQuestion tool (that is the "native question/choice tool" the canonical skill
refers to).

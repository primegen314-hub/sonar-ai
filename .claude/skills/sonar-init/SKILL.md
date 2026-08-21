---
name: sonar-init
description: Initialize the Sonar issues workspace - fetch SonarQube issues for a branch into SONAR_ISSUES/{branchRef}/ folders (issue.md, issue.json, context.json, summary.json) ready for solving. Use when the user pastes a SonarQube URL, says "init sonar", "pull/list sonar issues", or wants to prepare sonar issues for fixing.
---

# sonar-init (wrapper)

The canonical instructions and all scripts live in the shared agentic folder:
read `.github/skills/sonar-init/SKILL.md` and follow it exactly.
Scripts home: `.github/skills/sonar-issues/` (its `.env` lives there too — never at the repo root).

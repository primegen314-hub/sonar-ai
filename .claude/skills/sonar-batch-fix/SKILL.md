---
name: sonar-batch-fix
description: Fix a chosen SUBSET of extracted Sonar issues in one batch - by comma-separated selectors ("3,5,7-12"), a rule id ("S1481"), or a severity ("BLOCKER"). Built for large projects (hundreds of issues) where you solve in chunks instead of all at once. Use when the user says "batch fix", "fix issues 3 to 12", "fix all the S1481s", or names several issues together.
---

# sonar-batch-fix (wrapper)

The canonical instructions live in the shared agentic folder:
read `.github/skills/sonar-batch-fix/SKILL.md` and follow it exactly.
Scripts home: `.github/skills/sonar-issues/`. In Claude Code, present every choice with
the AskUserQuestion tool (that is the "native question/choice tool" the canonical skill
refers to).

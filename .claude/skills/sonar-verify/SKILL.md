---
name: sonar-verify
description: Run the project's tests to verify solved Sonar issues (full suite or scoped to one issue's tests) - always user-invoked, never automatic. Use when the user says "verify", "run the tests", "check my sonar fixes", or after finishing a /sonar-issues-solve or /sonar-issue-pick session in local mode.
---

# sonar-verify (wrapper)

The canonical instructions live in the shared agentic folder:
read `.github/skills/sonar-verify/SKILL.md` and follow it exactly.
Scripts home: `.github/skills/sonar-issues/`. In Claude Code, present every choice with
the AskUserQuestion tool (that is the "native question/choice tool" the canonical skill
refers to).

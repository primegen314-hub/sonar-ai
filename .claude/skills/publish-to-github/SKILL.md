---
name: publish-to-github
description: Publish GitHub-mode Sonar fixes to GitHub - commit the scratch-workspace changes (changes.patch) to a target branch via the GitHub REST API, after a preview and explicit confirmation. Use when the user says "publish", "push my sonar fixes", or after sonar-issues-solve finished in GitHub mode.
---

# publish-to-github (wrapper)

The canonical instructions live in the shared agentic folder:
read `.github/skills/publish-to-github/SKILL.md` and follow it exactly.
Scripts home: `.github/skills/sonar-issues/`. In Claude Code, present every choice with
the AskUserQuestion tool (that is the "native question/choice tool" the canonical skill
refers to).

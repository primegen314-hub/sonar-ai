# sonar-ai

AI-assisted SonarQube issue solving: extract issues into reviewable folders, fix them
one-by-one or all at once — **Local** (fixes edit your git checkout directly) or
**GitHub** (no checkout needed: fixes through the GitHub API, pushed with
`/publish-to-github`).

Built to be **fast on any agent model**: the Python scripts (stdlib-only) do all the
deciding — URL parsing, branch resolution, issue ranking, diffing, publishing — so the
agent only reads short script output and writes the actual fix. Test runs never
interrupt solving: verification is its own step (`/sonar-verify`) that you invoke when
you're ready.

## The fast path

1. `/sonar-init <sonar-url>` — one-time setup (Local | GitHub choice) + extract all issues
   (big backlog? `/sonar-attack-plan` shows it grouped by rule with a suggested order)
2. Fix — pick the right tool for the backlog size:
   - `/sonar-quick-wins` — auto-clear the easy majority (rec:sonar + low effort)
   - `/sonar-batch-fix 7-40` — a chosen chunk (selectors, ranges, a rule id, a severity)
   - `/sonar-issues-solve` — everything unresolved · `/sonar-issue-pick <n>` — one issue
3. `/sonar-verify` — run the tests once, at the end (Local mode)
4. Ship — `git push` in Local mode, `/publish-to-github` in GitHub mode

(`/sonar-mode` shows or switches the Local | GitHub mode anytime — re-run `/sonar-init`
after switching; progress survives.)

Every solving session ends by listing exactly what is **still unresolved**, so on a
300-issue project you always know what remains.

Everything lives in the canonical home **[.github/skills/sonar-issues/](.github/skills/sonar-issues/)**:

| Doc | What's inside |
|---|---|
| [README](.github/skills/sonar-issues/README.md) | how to run it, what you need per mode, install, security |
| [USECASE.md](USECASE.md) | the 200+-issue legacy-backlog playbook — report, attack plan, chunking rhythm |
| [FLOWS.md](.github/skills/sonar-issues/FLOWS.md) | diagrams — the whole journey, every dropdown, per-skill flows |
| [USAGE.md](.github/skills/sonar-issues/USAGE.md) | per-script runbook with real output |
| [CONTEXT.md](CONTEXT.md) | the project's ubiquitous language |
| [docs/adr/](docs/adr/) | architecture decision records |

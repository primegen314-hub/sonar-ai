# FLOWS — what the AI will ask you, and what happens for each choice

Every decision below is presented by the AI as a **dropdown** (Claude Code) or a
**numbered menu** (Copilot chat). The recommended option is always listed first and
marked — it comes pre-computed from the scripts, so you can just press Enter on it.
Every skill also announces its phases as it goes ("issue 3/12"), so you always know
where the session is.

## The whole journey — every question you'll be asked

One diagram, use-case level: the **Local | GitHub** fork decides everything downstream.
`{{❓}}` hexagons are dropdowns; 🔐 is a hidden prompt in YOUR terminal (the AI never
sees the token). Notice what is NOT here anymore: no branch question at setup, and no
test runs during solving — `/sonar-verify` is its own step you invoke when ready.

```mermaid
flowchart TD
    START["/sonar-init &lt;sonar-url&gt;"] --> MODE{{"❓ Workflow mode? — asked ONCE, saved<br>Local — I work in this git checkout (recommended)<br>GitHub — no checkout, via the GitHub API"}}

    MODE -- Local --> LSET["set_mode.py local — asks nothing<br>(branch comes from the Sonar URL<br>or the current checkout, per run)"]
    LSET --> LEXT["issues extracted →<br>SONAR_ISSUES/&lt;branch&gt;/"]

    MODE -- GitHub --> TOK["🔐 you run set_mode.py github in your terminal<br>GitHub token, hidden input, WRITE access<br>(no checkout? paste the repo URL)"]
    TOK --> REXT["issues extracted (checkout irrelevant) →<br>SONAR_ISSUES/&lt;branch&gt;/"]

    LEXT --> SOLVE["/sonar-issues-solve (all) or /sonar-issue-pick (one)"]
    REXT --> SOLVE
    SOLVE --> IM{{"❓ interactive | automated (solve-all only)"}}
    IM --> EFF{{"❓ AI effort — normal | high | max | xMax<br>(analysis depth only — never runs tests)"}}
    EFF --> FIXQ{{"❓ per issue: Apply Sonar suggestion |<br>Let AI solve it | Your own fix | skip"}}

    FIXQ -- "Local: fix edits the checkout<br>+ git diff --stat proves it landed" --> LKEEP{{"❓ keep issue folder | delete it"}}
    LKEEP --> LVER["/sonar-verify — when YOU are ready<br>(recommended: after all issues)"]
    LVER --> LCLEAN{{"❓ Cleanup? delete SONAR_ISSUES/&lt;branch&gt;/ | keep"}}
    LCLEAN --> LPUSH["you commit + push with git<br>→ CI re-analyzes → Sonar clears the issues"]

    FIXQ -- "GitHub: fix edits the workspace copy<br>(your checkout untouched — git diff empty is EXPECTED)" --> RKEEP{{"❓ keep issue folder | delete it"}}
    RKEEP --> PUB["/publish-to-github — preview: files + diffstat"]
    PUB --> TB{{"❓ Target branch? analyzed branch (recommended) |<br>new branch | another existing branch"}}
    TB --> CONF{{"❓ Push N file(s) to org/repo@branch? | Cancel"}}
    CONF --> RCLEAN{{"❓ Cleanup? delete SONAR_ISSUES/&lt;branch&gt;/ | keep"}}
    RCLEAN --> RCI["CI re-analyzes the target branch<br>→ Sonar clears the issues"]
```

## The big picture

```mermaid
flowchart LR
    A["/sonar-init &lt;sonar-url&gt;"] --> B[("SONAR_ISSUES/&lt;branch&gt;/<br>one folder per issue")]
    B --> C["/sonar-issues-solve<br>(all issues)"]
    B --> D["/sonar-issue-pick<br>(one issue)"]
    C --> E{"Local: fixes in your checkout<br>GitHub: changes.patch ready"}
    D --> E
    E -- "Local" --> V["/sonar-verify<br>(tests, once, when you choose)"]
    V --> F["you push with git"]
    E -- "GitHub" --> P["/publish-to-github<br>(confirmed API commit)"]
    F --> G["CI re-analysis<br>→ Sonar clears the issues"]
    P --> G
```

## /sonar-init — extract (one dropdown, once)

```mermaid
flowchart TD
    A["/sonar-init &lt;pasted-sonar-url&gt;"] --> B{".env exists in<br>.github/skills/sonar-issues/?"}
    B -- no --> C["AI copies .env.example → .env<br>asks you to fill SONAR_USER"] --> W
    B -- yes --> W{"mode already chosen?<br>(set_mode.py --show)"}
    W -- yes --> D
    W -- no --> M{{"❓ Workflow mode? — asked ONCE<br>Local (recommended) | GitHub"}}
    M -- Local --> LCK["set_mode.py local — asks nothing;<br>no git repo here? open the project folder<br>and retry (that's the whole message)"] --> D
    M -- GitHub --> TOK["🔐 you run set_mode.py github in your terminal<br>(token hidden input; org/repo from the git remote<br>or a pasted repo URL — no checkout required)"] --> D
    D{"Branch gate"}
    D -- "Sonar has no such branch<br>(git and Sonar names differ)" --> SB{{"❓ Sonar branch name?<br>→ set_mode.py --sonar-branch &lt;name&gt;"}} --> A
    D -- "github: branch missing on GitHub" --> F["🔴 hard error:<br>pass --branch or set GITHUB_BRANCH"]
    D -- "local: wrong branch checked out /<br>OUT OF SYNC with origin" --> S["🔴 ONE command printed:<br>git checkout &lt;branch&gt; &amp;&amp; git pull<br>AI offers to run it — you approve, then re-run<br>(no mode switching, ever)"]
    S --> A
    D -- ok --> G["s01 auth (first run: LDAP password<br>prompted once, token minted;<br>leftover SONAR_PASSWORD always cleared)"]
    G --> H["s02–s06: fetch issues + rules,<br>build folders, context, summary<br>(unpublished workspace edits block the<br>re-fetch: publish or --discard-workspace)"]
    H --> I["Report: N issues by severity + the mode<br>(re-runs keep resolution.json progress)"]
```

## /sonar-issues-solve — solve everything (no test runs — that's /sonar-verify)

```mermaid
flowchart TD
    A["/sonar-issues-solve [branch|url]"] --> B{"summary.json exists?"}
    B -- no --> C["run the init pipeline first"] --> D
    B -- yes --> D["show plan: pick_issue.py --list<br>(header shows mode: local | github)"]
    D --> M{{"❓ Mode"}}
    M -- "interactive (confirm each)" --> EF
    M -- "automated (fix all, report at end)" --> EF
    EF{{"❓ AI effort — asked ONCE<br>normal | high | max | xMax<br>(analysis depth only; recommended from TOTAL Sonar effort)"}}
    EF --> L["loop: pick_issue.py --next — announce issue i/N"]

    L --> INT{"mode?"}
    INT -- interactive --> O{{"❓ Fix approach (recommended first)<br>1 Apply Sonar suggestion<br>2 Let AI solve it<br>3 Your own fix / notes<br>4 skip"}}
    O --> WFM{"workflow mode?"}
    INT -- automated --> AUTOFIX["follow the rec: flag<br>(sonar → compliant example,<br>ai → tailored minimal fix)"]
    AUTOFIX --> WFM

    WFM -- local --> FIX["apply minimal fix to the checkout<br>then PROVE it: git diff --stat -- &lt;file&gt;<br>(empty diff = retry, never record fixed)"]
    WFM -- github --> RFIX["workspace.py fetch &lt;file&gt; →<br>edit the workspace copy →<br>workspace.py diff (rebuilds changes.patch)<br>+ remind: your checkout is untouched"]

    FIX --> R["write resolution.json (testsRun: [])"]
    RFIX --> R

    R -- automated --> N{"more issues?"}
    R -- "interactive:<br>❓ keep folder (recommended) | delete it<br>(deleted = still counts as resolved)" --> N
    N -- yes --> L
    N -- no --> REP["report: N fixed / M skipped"]
    REP --> WFM2{"workflow mode?"}
    WFM2 -- local --> HAND["hand-off: run /sonar-verify when ready<br>(cleanup only after it passes)"]
    WFM2 -- github --> NEXT["hand-off: /publish-to-github<br>(cleanup only offered after publishing)"]
```

## /sonar-issue-pick — solve one issue

```mermaid
flowchart TD
    A["/sonar-issue-pick [selector]"] --> B{"selector given?<br>(seq | folder prefix | Sonar key)"}
    B -- yes --> P["pick_issue.py &lt;selector&gt;<br>(output shows mode: + workspace: lines)"]
    B -- no --> BR{"how many branch trees?<br>(pick_issue.py --branches — shows each mode)"}
    BR -- one --> LIST
    BR -- several --> BQ{{"❓ Which branch?<br>(each shows resolved count)"}} --> LIST
    BR -- none --> INIT["run /sonar-init first"]
    LIST{{"❓ Which issue?<br>unresolved list grouped by severity<br>🔴🟠🟡🔵 — free-text filter allowed"}} --> P

    P --> BRIEF["brief from script output:<br>rule, file:line, message,<br>recommend: sonar|ai + reason,<br>ai effort: tier, rules: files"]
    BRIEF --> O{{"❓ Fix approach (recommended first)<br>1 Apply Sonar suggestion<br>2 Let AI solve it<br>3 Your own fix / notes"}}
    O -- "AI-done fix" --> EF{{"❓ AI effort<br>normal | high | max | xMax<br>(analysis depth only)"}}
    O -- "Sonar suggestion" --> WFM
    EF --> WFM{"workflow mode?"}
    WFM -- local --> FIX["apply fix to the checkout,<br>respecting the rules: files<br>then PROVE it: git diff --stat -- &lt;file&gt;"]
    WFM -- github --> RFIX["workspace.py fetch &lt;file&gt; →<br>edit the workspace copy →<br>workspace.py diff (rebuilds changes.patch)"]
    FIX --> R["resolution.json (testsRun: []) + report with sonarUrl<br>hand-off: /sonar-verify when ready"]
    RFIX --> R2["resolution.json + report with sonarUrl<br>(fix lives in the workspace — checkout untouched —<br>until /publish-to-github)"]
    R --> DEL{{"❓ Issue folder?<br>keep (recommended) | delete it<br>(deleted = still counts as resolved)"}}
    R2 --> DEL
```

## /sonar-verify — run the tests (always YOU invoke it, never automatic)

```mermaid
flowchart TD
    A["/sonar-verify [issue-selector]"] --> B{"branch tree?<br>(pick_issue.py --branches)"}
    B -- none --> INIT["nothing to verify — /sonar-init first"]
    B -- "mode: github" --> GH["explain: fixes live in the workspace,<br>no fixed code here to test —<br>CI verifies after /publish-to-github<br>(or pull the published branch and verify there)"]
    B -- "mode: local" --> RUN{"selector given?"}
    RUN -- no --> FULL["verify.py --full<br>(the whole suite — the normal case)"]
    RUN -- yes --> SCOPED["verify.py --issue &lt;n&gt;<br>(only that issue's testFiles)"]
    FULL --> TC{"exit 2: no test command<br>and nothing auto-detected?"}
    SCOPED --> TC
    TC -- yes --> TCQ{{"❓ Test command (asked ONCE)<br>let AI determine it (recommended) |<br>type it yourself | skip verification<br>→ saved via verify.py --set-command"}}
    TCQ --> FULL
    TC -- no --> RES{"tests pass?"}
    RES -- pass --> OK["✅ report; fill testsRun in the<br>verified resolutions — green light for cleanup"]
    RES -- fail --> FQ{{"❓ On failure — YOU decide (no auto-debugging)<br>1 bisect per issue (recommended) — test each fix alone,<br>the one that fails alone is the culprit<br>2 try a different test command<br>3 investigate the failure (only now the AI debugs)<br>4 skip / deal with it later"}}
```

## /publish-to-github — push GitHub-mode fixes (GitHub mode only)

```mermaid
flowchart TD
    A["/publish-to-github [branch]"] --> B{"mode is github?<br>(pick_issue.py --list)"}
    B -- "local" --> LR["refuse: in local mode you<br>commit + push with git yourself"]
    B -- "nothing extracted" --> INIT["run /sonar-init first"]
    B -- github --> PRE["publish.py --dry-run:<br>repo, target, files + diffstat,<br>issues covered"]
    PRE -- "nothing to publish" --> NP["stop: solve an issue first<br>(/sonar-issue-pick | /sonar-issues-solve)"]
    PRE --> TB{{"❓ Target branch?<br>analyzed branch (recommended) |<br>new branch (type the name) |<br>another existing branch"}}
    TB --> CONF{{"❓ Push N file(s) to org/repo@target? | Cancel"}}
    CONF -- Cancel --> STOP["nothing pushed"]
    CONF -- Push --> RUN["publish.py --target-branch &lt;t&gt; --yes<br>(--yes ALWAYS after chat confirmation —<br>agent terminals have no stdin)<br>ONE atomic commit via the Git Data API<br>(creates the branch when missing)"]
    RUN -- "403: token can't write" --> TOK["🔐 re-run set_mode.py github<br>with a WRITE-scope token"]
    RUN -- "files changed on GitHub<br>since extraction" --> DRIFT{{"❓ Conflict<br>re-run /sonar-init + re-apply (recommended) |<br>--force overwrite (last-write-wins)"}}
    RUN -- "422: branch moved mid-publish" --> RETRY["just re-run publish"]
    RUN -- ok --> DONE["commit URL + publish.json written<br>workspace re-baselined (clean)"]
    DONE --> CL{{"❓ Cleanup?<br>delete SONAR_ISSUES/&lt;branch&gt;/ | keep"}}
    CL --> CI["CI re-analyzes the target branch<br>→ Sonar clears the issues"]
```

## Worked example — local mode (interactive, Claude Code)

```text
You:  /sonar-issue-pick 003_S2095_ReportService.java_L26 --branch TASK-3487

AI:  🔴 BLOCKER S2095 — ReportService.java:26
     "Use try-with-resources or close this 'FileInputStream'..."
     mode: local
     recommend: sonar — the rule's compliant example matches this file's language
     ai effort: normal (Sonar estimates 10min)

     ❓ Fix approach?          → [Apply the Sonar suggestion (Recommended)]
                                 [Let AI solve it]  [Your own fix / notes]
You:  Apply the Sonar suggestion

AI:  (rewrites lines 26–31 as try-with-resources)
     $ git diff --stat -- src/main/java/.../ReportService.java
       1 file changed, 4 insertions(+), 2 deletions(-)     ← the fix landed
     resolution.json written (fixed).
     The fix is applied but untested — run /sonar-verify when you're ready.
     Sonar link: https://sonar.../project/issues?...&open=AY8x...

You:  /sonar-verify

AI:  [verify] auto-detected maven: mvn -B test
     [verify] PASSED ✅ — testsRun recorded; cleanup is now safe
```

## Worked example — GitHub mode (ends in publish)

```text
You:  /sonar-issue-pick 3 --branch TASK-3487

AI:  🔴 BLOCKER S2095 — ReportService.java:26
     mode: github
     workspace: not fetched yet — run: python .../workspace.py fetch src/main/java/.../ReportService.java

     ❓ Fix approach?          → [Apply the Sonar suggestion (Recommended)] ...
You:  Apply the Sonar suggestion

AI:  (workspace.py fetch → edits the WORKSPACE copy → workspace.py diff)
     [workspace] changes.patch rebuilt — 1 file(s) changed
     resolution.json written (fixed). Your checkout is untouched — `git diff`
     shows nothing by design; the fix lives in the workspace until
     /publish-to-github pushes it. Tests run in CI on the pushed branch.

You:  /publish-to-github

AI:  repo          : acme/report-service
     target branch : TASK-3487
     files to push : 1
       src/main/java/.../ReportService.java  +4 -2
     issues covered: 1
     ❓ Target branch?          → [TASK-3487 (Recommended)]  [a new branch]  [another existing]
     ❓ Push 1 file(s) to acme/report-service@TASK-3487?  → [Push]  [Cancel]
You:  Push

AI:  [publish] pushed 1 file(s) to TASK-3487 — commit 9f3ab12c04
     Sonar clears the issues after CI re-analyzes that branch.
     ❓ Cleanup? → [delete SONAR_ISSUES/TASK-3487/]  [keep]
```

Every choice above maps 1-to-1 to a box in the diagrams — if you're ever unsure what a
menu will do, find its ❓ box and follow the arrow.

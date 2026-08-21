"""Step 06 - Write summary.json (brief view of every issue) and validate that
each issue folder holds the complete contract (issue.json / issue.md / context.json).
Exits non-zero when validation fails.
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import init_console, RAW_DIR_NAME
from lib import config
from lib.effort import effort_minutes, ai_effort_for_batch, complexity_score

REQUIRED_FILES = ["issue.json", "issue.md", "context.json"]
REQUIRED_ISSUE_KEYS = ["key", "rule", "message", "file", "severity", "type", "sonarUrl", "branchRef"]


def main():
    init_console()
    args = config.build_parser(__doc__).parse_args()
    settings = config.Settings(args)
    meta = settings.load_meta()

    folders = sorted(
        d for d in os.listdir(settings.branch_dir)
        if d != RAW_DIR_NAME and os.path.isdir(os.path.join(settings.branch_dir, d))
    )

    errors = []
    entries = []
    scored = []
    by_severity, by_type = {}, {}
    for folder in folders:
        folder_path = os.path.join(settings.branch_dir, folder)
        for required in REQUIRED_FILES:
            if not os.path.isfile(os.path.join(folder_path, required)):
                errors.append(f"{folder}: missing {required}")
        issue_path = os.path.join(folder_path, "issue.json")
        if not os.path.isfile(issue_path):
            continue
        issue = config.load_json(issue_path)
        for key in REQUIRED_ISSUE_KEYS:
            if issue.get(key) in (None, "", []):
                errors.append(f"{folder}: issue.json missing '{key}'")
        by_severity[issue.get("severity", "?")] = by_severity.get(issue.get("severity", "?"), 0) + 1
        by_type[issue.get("type", "?")] = by_type.get(issue.get("type", "?"), 0) + 1
        entries.append({
            "seq": issue.get("seq"),
            "folder": folder,
            "key": issue.get("key"),
            "ruleId": issue.get("rule", {}).get("id"),
            "file": issue.get("file"),
            "line": issue.get("line"),
            "severity": issue.get("severity"),
            "type": issue.get("type"),
            "effort": issue.get("effort"),
            "status": issue.get("status"),
            "message": issue.get("message"),
            "recommended": issue.get("recommended"),
            "recommendedReason": issue.get("recommendedReason"),
            "aiEffort": issue.get("aiEffort"),
            "aiEffortReason": issue.get("aiEffortReason"),
            "complexityScore": issue.get("complexityScore"),
        })
        context_path = os.path.join(folder_path, "context.json")
        context = config.load_json(context_path) if os.path.isfile(context_path) else {}
        scored.append(complexity_score(issue, context))

    summary = {
        "project": meta["project"],
        "branchRef": meta["branchRef"],
        "fetchedAt": meta["fetchedAt"],
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "workflowMode": meta.get("workflowMode", "local"),
        "scope": meta["scope"],
        "filters": {"issueStatuses": meta["issueStatuses"]},
        "sonarHost": meta["host"],
        "totals": {
            "issues": len(entries),
            "bySeverity": by_severity,
            "byType": by_type,
            "effortMinutes": sum(effort_minutes(e.get("effort")) or 0 for e in entries),
        },
        "issues": entries,
    }
    batch_tier, batch_reason = ai_effort_for_batch(scored)
    summary["recommendedBatchEffort"] = batch_tier
    summary["recommendedBatchEffortReason"] = batch_reason
    config.dump_json(os.path.join(settings.branch_dir, "summary.json"), summary)

    print(f"[s06] summary.json: {len(entries)} issues "
          f"| severity {by_severity} | type {by_type}")
    for entry in entries:
        print(f"[s06]   {entry['folder']}: {entry['message']}")

    if errors:
        print(f"[s06] VALIDATION FAILED ({len(errors)} problems):", file=sys.stderr)
        for err in errors:
            print(f"[s06]   {err}", file=sys.stderr)
        sys.exit(1)
    print(f"[s06] validation OK - {settings.branch_dir} is complete")


if __name__ == "__main__":
    main()

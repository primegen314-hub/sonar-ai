"""List issues for a branch, or resolve one issue selector to its folder paths.

The bridge between humans/AI-skills and the SONAR_ISSUES tree - never guess
folder names, ask this script.

Usage:
  python pick_issue.py --list            [--branch NAME]   all issues + solve status
  python pick_issue.py 3                 [--branch NAME]   by sequence number
  python pick_issue.py 003_S1481_Repo... [--branch NAME]   by folder name (prefix ok)
  python pick_issue.py AY8xKEY           [--branch NAME]   by Sonar issue key
  python pick_issue.py --next            [--branch NAME]   first unresolved issue
  python pick_issue.py --branches                          every extracted branch tree

Exit codes: 0 = found/listed, 1 = error, 2 = --next found nothing (all resolved).

A solving skill marks progress by writing resolution.json into the issue folder:
  {"status": "fixed"|"skipped", "reason": "...", "filesChanged": [...], "testsRun": [...],
   "mode": "local"|"github",
   // github mode only:
   "workspaceFiles": [...], "patchFile": "changes.patch"}
"testsRun" stays [] at solve time - verification never auto-runs; /sonar-verify
sessions fill it in later.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import init_console, fail
from lib import config
from lib.instructions import find_instruction_files


def normalize_mode(mode):
    """Old summaries say 'remote'; the canonical name is now 'github'."""
    return "github" if (mode or "").strip().lower() in ("remote", "github") else "local"


def resolution_status(branch_dir, folder):
    folder_path = os.path.join(branch_dir, folder)
    if not os.path.isdir(folder_path):
        # solved-and-deleted by the user: still counts as resolved so --next
        # never re-offers it
        return "removed"
    path = os.path.join(folder_path, "resolution.json")
    if not os.path.isfile(path):
        return "unresolved"
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f).get("status", "unresolved")
    except (OSError, ValueError):
        return "unresolved"


def list_branch_folders(output_root):
    """[(folder, branchRef, issues, fixed)] for every extracted branch tree."""
    found = []
    if not os.path.isdir(output_root):
        return found
    for folder in sorted(os.listdir(output_root)):
        path = os.path.join(output_root, folder, "summary.json")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                summary = json.load(f)
        except (OSError, ValueError):
            continue
        entries = summary.get("issues", [])
        fixed = sum(1 for e in entries
                    if resolution_status(os.path.join(output_root, folder), e["folder"])
                    in ("fixed", "skipped", "removed"))
        found.append((folder, summary.get("branchRef", folder), len(entries), fixed,
                      normalize_mode(summary.get("workflowMode", "local"))))
    return found


def print_branches(settings):
    branches = list_branch_folders(settings.output_root)
    if not branches:
        fail(f"No extracted branches under {settings.output_root} - run the pipeline first:\n"
             f"  python {os.path.join(settings.skill_dir, 'run_all.py')} <sonar-url>")
    for folder, branch_ref, total, done, mode in branches:
        print(f"  {folder}  branch: {branch_ref}  mode: {mode}  {done}/{total} resolved")


def load_summary(settings):
    path = os.path.join(settings.branch_dir, "summary.json")
    if not os.path.isfile(path):
        others = list_branch_folders(settings.output_root)
        hint = ""
        if others:
            listing = "\n".join(f"    {f}  (branch: {b}, {d}/{t} resolved)" for f, b, t, d, _ in others)
            hint = (f"\n  Extracted branches that DO exist - pass one with --branch:\n{listing}")
        fail(f"{path} not found - run the pipeline first:\n"
             f"  python {os.path.join(settings.skill_dir, 'run_all.py')} <sonar-url>{hint}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def print_issue(settings, entry, status, mode="local"):
    folder_path = os.path.join(settings.branch_dir, entry["folder"])
    print(f"seq     : {entry['seq']}")
    print(f"folder  : {folder_path}")
    print(f"issue   : {os.path.join(folder_path, 'issue.json')}")
    print(f"context : {os.path.join(folder_path, 'context.json')}")
    print(f"md      : {os.path.join(folder_path, 'issue.md')}")
    print(f"mode    : {mode}")
    if mode == "github":
        from lib import workspace as ws
        edited = ws.edited_path(settings, entry["file"])
        if os.path.isfile(edited):
            print(f"workspace: {edited}")
        else:
            print(f"workspace: not fetched yet - run: python "
                  f"{os.path.join(settings.skill_dir, 'workspace.py')} fetch {entry['file']} "
                  f"--branch {settings.branch}")
    print(f"status  : {status}")
    print(f"severity: {entry['severity']} | type: {entry['type']} | effort: {entry.get('effort') or '-'}")
    print(f"file    : {entry['file']}:{entry.get('line') or '?'}")
    print(f"message : {entry['message']}")
    if entry.get("recommended"):
        print(f"recommend: {entry['recommended']} - {entry.get('recommendedReason', '')}")
    if entry.get("aiEffort"):
        print(f"ai effort: {entry['aiEffort']} ({entry.get('aiEffortReason') or 'complexity score'})")
    rules = find_instruction_files(settings.repo_root)
    print(f"rules    : {'; '.join(rules) if rules else '(none found - proceed with the fix)'}")


def main():
    init_console()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("selector", nargs="?", default=None,
                        help="sequence number, folder name (prefix), or Sonar issue key")
    parser.add_argument("--branch", default=None, help="branch ref (default: current git branch)")
    parser.add_argument("--list", action="store_true", help="list every issue with solve status")
    parser.add_argument("--next", action="store_true", help="print the first unresolved issue")
    parser.add_argument("--branches", action="store_true",
                        help="list every extracted branch tree under SONAR_ISSUES/")
    parser.add_argument("--fixtures", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.url = None  # Settings expects it

    settings = config.Settings(args)
    if args.branches:
        print_branches(settings)
        return
    if not settings.branch:
        if settings.workflow_mode == "github":
            fail("No branch ref. GitHub mode never uses the checkout - pass --branch <name> "
                 "(see --branches for what is extracted)")
        fail("No branch ref. Run inside a git checkout or pass --branch <name>")
    summary = load_summary(settings)
    entries = summary.get("issues", [])
    mode = normalize_mode(summary.get("workflowMode", "local"))

    if args.list:
        done = 0
        print(f"branch: {summary['branchRef']} | project: {summary['project']} "
              f"| mode: {mode} | fetched: {summary['fetchedAt']}")
        for e in entries:
            status = resolution_status(settings.branch_dir, e["folder"])
            if status in ("fixed", "removed"):
                done += 1
            msg = e["message"] if len(e["message"]) <= 70 else e["message"][:67] + "..."
            rec = f"rec:{e.get('recommended') or '-':5s}"
            eff = f"eff:{e.get('aiEffort') or '-':6s}"
            print(f"  [{status:10s}] {e['folder']}  {e['severity']:8s} {rec} {eff} {msg}")
        print(f"{done}/{len(entries)} fixed")
        totals = summary.get("totals", {})
        if summary.get("recommendedBatchEffort"):
            print(f"total effort: ~{totals.get('effortMinutes', 0)}min "
                  f"| recommended batch ai effort: {summary['recommendedBatchEffort']} "
                  f"({summary.get('recommendedBatchEffortReason', '')})")
        return

    if args.next:
        for e in entries:
            status = resolution_status(settings.branch_dir, e["folder"])
            if status not in ("fixed", "skipped", "removed"):
                print_issue(settings, e, status, mode)
                return
        print("All issues are resolved (fixed or skipped).")
        sys.exit(2)

    if not args.selector:
        parser.print_help()
        sys.exit(1)

    sel = args.selector.strip()
    match = None
    if sel.isdigit():
        match = next((e for e in entries if e["seq"] == int(sel)), None)
    if match is None:
        match = next((e for e in entries if e["folder"].startswith(sel)), None)
    if match is None:
        match = next((e for e in entries if e["key"] == sel), None)
    if match is None:
        fail(f"No issue matches '{sel}'. Use --list to see all issues.")
    print_issue(settings, match, resolution_status(settings.branch_dir, match["folder"]), mode)


if __name__ == "__main__":
    main()

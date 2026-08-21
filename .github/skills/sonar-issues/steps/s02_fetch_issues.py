"""Step 02 - Fetch all matching issues from SonarQube into SONAR_ISSUES/{branchRef}/_raw/.

Wipes the branch folder first (rerun policy: the folder always mirrors Sonar's
current state) but stashes every resolution.json by issue key so s04 can restore
solve progress for issues that still exist. Writes issues.json and meta.json
(the resolved run parameters every later step reads).
"""
import datetime
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import init_console, fail, RAW_DIR_NAME
from lib import config
from lib import workspace as ws

RESOLUTIONS_STASH = "resolutions.json"


def stash_resolutions(branch_dir):
    """{issueKey: resolution-dict} for every issue folder that has both
    issue.json and resolution.json - collected before the wipe."""
    stash = {}
    if not os.path.isdir(branch_dir):
        return stash
    for folder in os.listdir(branch_dir):
        folder_path = os.path.join(branch_dir, folder)
        if folder == RAW_DIR_NAME or not os.path.isdir(folder_path):
            continue
        issue_path = os.path.join(folder_path, "issue.json")
        resolution_path = os.path.join(folder_path, "resolution.json")
        if not (os.path.isfile(issue_path) and os.path.isfile(resolution_path)):
            continue
        try:
            with open(issue_path, "r", encoding="utf-8-sig") as f:
                key = json.load(f).get("key")
            with open(resolution_path, "r", encoding="utf-8-sig") as f:
                resolution = json.load(f)
        except (OSError, ValueError):
            continue
        if key:
            stash[key] = resolution
    return stash


def main():
    init_console()
    args = config.build_parser(__doc__).parse_args()
    settings = config.Settings(args)
    settings.require_fetch_params()

    # github mode: never silently wipe unpublished workspace edits - they are
    # uncommitted work product, unlike resolution.json which is only a record
    if settings.workflow_mode == "github" and ws.is_dirty(settings):
        if getattr(args, "discard_workspace", False):
            ws.discard(settings)
            print("[s02] discarded unpublished workspace changes (--discard-workspace)")
        else:
            fail(f"Unpublished workspace changes exist for this branch ({settings.patch_path}).\n"
                 f"  Publish them first (/publish-to-github), or re-run with --discard-workspace "
                 f"to delete them.")

    settings.check_branch()

    print(f"[s02] mode     : {settings.workflow_mode}")
    print(f"[s02] project  : {settings.project}")
    print(f"[s02] branchRef: {settings.branch}  (folder: {settings.branch_folder})")
    print(f"[s02] scope    : {'new code' if settings.new_code else 'all code'}"
          f" | statuses: {','.join(settings.statuses)}")

    client = settings.sonar_client()
    result = client.search_all_issues(
        project_key=settings.project,
        branch=settings.branch,
        statuses=settings.statuses,
        new_code_only=settings.new_code,
    )
    print(f"[s02] fetched {len(result['issues'])} issues (server total: {result['total']})")

    stash = stash_resolutions(settings.branch_dir)
    if os.path.isdir(settings.branch_dir):
        shutil.rmtree(settings.branch_dir)
        print(f"[s02] wiped previous {settings.branch_dir}"
              + (f" (kept {len(stash)} resolution(s) for restore)" if stash else ""))

    config.dump_json(os.path.join(settings.raw_dir, "issues.json"), result)
    if stash:
        config.dump_json(os.path.join(settings.raw_dir, RESOLUTIONS_STASH), stash)
    meta = {
        "fetchedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "host": settings.host,
        "project": settings.project,
        "branchRef": settings.branch,
        "branchFolder": settings.branch_folder,
        "scope": "new_code" if settings.new_code else "all",
        "issueStatuses": settings.statuses,
        "workflowMode": settings.workflow_mode,
        "contextSource": settings.context_source,
        "sonarBranch": settings.sonar_branch_override,
        "gitBranch": settings.git_branch,
        "githubBranch": settings.github_branch if settings.workflow_mode == "github" else None,
        "fixtures": settings.fixtures,
        "serverVersion": client.version() if not settings.fixtures else "fixtures",
        "issueCount": len(result["issues"]),
        "truncated": result["truncated"],
    }
    config.dump_json(settings.meta_path, meta)
    print(f"[s02] wrote {settings.raw_dir}\\issues.json and meta.json")


if __name__ == "__main__":
    main()

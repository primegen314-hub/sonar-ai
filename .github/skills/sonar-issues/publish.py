"""Publish github-mode fixes to GitHub: commit the scratch-workspace changes
to a target branch as ONE atomic multi-file commit (Git Data API, stdlib only).

Github-mode only - in local mode you commit and push with git yourself (exit 2).
The pipeline must have run first (/sonar-init) and at least one fix must exist
in the workspace. GITHUB_TOKEN needs WRITE access to the repository
(classic: 'repo' scope; fine-grained: Contents read/write).

Usage:
  python publish.py [--branch B] [--target-branch T] [--message MSG]
                    [--dry-run] [--yes] [--force] [--fixtures]

  --dry-run        print what would be pushed and stop (the only mode allowed
                   under --fixtures - offline runs never write to the network)
  --target-branch  branch to commit to (default: the analyzed branch; created
                   from the analyzed branch head when it doesn't exist)
  --yes            skip the interactive confirmation (the skill passes this
                   only AFTER the user confirmed the push)
  --force          overwrite files that changed on GitHub since extraction
                   (last-write-wins; use only when you understand the drift)

Exit codes: 0 pushed (or dry-run ok) | 1 error/conflict | 2 wrong mode / not
initialized / nothing to publish.
"""
import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import init_console, fail, warn, ok
from lib import config
from lib import workspace as ws
from lib.http_client import HttpError


def gather_fixed_issues(settings):
    """[(folder, ruleId, message)] for every issue resolved as fixed."""
    summary = config.load_json(os.path.join(settings.branch_dir, "summary.json"))
    fixed = []
    for entry in summary.get("issues", []):
        res_path = os.path.join(settings.branch_dir, entry["folder"], "resolution.json")
        if not os.path.isfile(res_path):
            continue
        try:
            resolution = config.load_json(res_path)
        except ValueError:
            continue
        if resolution.get("status") == "fixed":
            fixed.append((entry["folder"], entry.get("ruleId") or "?", entry.get("message") or ""))
    return fixed


def default_message(fixed, changed):
    rules = sorted({rule for _, rule, _ in fixed})
    if fixed:
        subject = f"fix(sonar): resolve {len(fixed)} issue(s) - {', '.join(rules)}"
    else:
        subject = f"fix(sonar): apply workspace changes ({len(changed)} file(s))"
    body_lines = [f"- {folder}: {message}" for folder, _, message in fixed]
    return subject + ("\n\n" + "\n".join(body_lines) if body_lines else "")


def print_preview(settings, target, fixed):
    print(f"repo          : {settings.github_org}/{settings.github_repo}")
    print(f"target branch : {target}")
    stats = ws.diffstat(settings)
    print(f"files to push : {len(stats)}")
    for s in stats:
        tag = "  [new file]" if s["new"] else ""
        print(f"  {s['file']}  +{s['added']} -{s['removed']}{tag}")
    print(f"patch         : {settings.patch_path}")
    if fixed:
        print(f"issues covered: {len(fixed)}")
        for folder, rule, message in fixed:
            print(f"  {folder} ({rule}): {message}")
    else:
        print("issues covered: none marked fixed yet (pushing raw workspace changes)")


def check_conflicts(settings, client, target_sha, changed, manifest, force):
    """Fail when a file we are about to overwrite moved on GitHub since fetch."""
    if target_sha is None:
        return  # brand-new branch: nothing to drift against
    if manifest.get("baseCommitSha") in (target_sha, None):
        return  # branch tip unchanged since fetch (or unknown base - checked per file below)
    drifted = []
    for rel in changed:
        _, current_sha = client.get_file_blob(rel, ref=target_sha)
        baseline = manifest.get("files", {}).get(rel, {}).get("blobSha")
        if baseline is None:
            # a file the fix created without fetching: conflict only if it already exists
            if current_sha is not None:
                drifted.append(rel)
        elif current_sha != baseline:
            drifted.append(rel)
    if drifted:
        listing = "\n".join(f"  {rel}" for rel in drifted)
        if force:
            warn(f"--force: overwriting {len(drifted)} file(s) that changed on GitHub since "
                 f"extraction (last-write-wins):\n{listing}")
            return
        fail(f"These files changed on GitHub since extraction - publishing would overwrite "
             f"someone's work:\n{listing}\n"
             f"Re-run /sonar-init to re-extract against the new state (then re-apply the fixes), "
             f"or pass --force to overwrite anyway.")


def push(settings, client, target, message, changed, manifest):
    target_sha = client.get_branch_sha(target)
    check = target_sha
    if target_sha is None:
        base_branch = settings.github_branch
        base_sha = client.get_branch_sha(base_branch)
        if base_sha is None:
            fail(f"Neither target branch '{target}' nor analyzed branch '{base_branch}' "
                 f"exists on GitHub - nothing to base the commit on")
        print(f"[publish] target branch '{target}' does not exist - creating it from "
              f"'{base_branch}' ({base_sha[:10]})")
        parent_sha = base_sha
    else:
        parent_sha = target_sha

    entries = []
    for rel in changed:
        with open(ws.edited_path(settings, rel), "rb") as f:
            content = f.read()
        entries.append({"path": rel, "sha": client.create_blob(content)})
    tree_sha = client.create_tree(client.get_commit_tree(parent_sha), entries)
    commit = client.create_commit(message, tree_sha, [parent_sha])
    if check is None:
        client.create_ref(target, commit["sha"])
    else:
        client.update_ref(target, commit["sha"])
    return commit


def main():
    init_console()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--branch", default=None, help="the extracted branch ref")
    parser.add_argument("--target-branch", default=None,
                        help="branch to commit to (default: the analyzed branch)")
    parser.add_argument("--message", default=None, help="commit message override")
    parser.add_argument("--dry-run", action="store_true", help="preview only, no network writes")
    parser.add_argument("--yes", action="store_true", help="skip the interactive confirmation")
    parser.add_argument("--force", action="store_true",
                        help="overwrite files that changed on GitHub since extraction")
    parser.add_argument("--fixtures", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.url = None  # Settings expects it

    settings = config.Settings(args)
    settings.require_mode()
    if settings.workflow_mode != "github":
        fail("publish is github-mode only - in local mode commit and push with git yourself "
             "(git add / git commit / git push)", code=2)
    if not settings.branch:
        fail("No branch ref - pass --branch <branchRef> (see pick_issue.py --branches)", code=2)
    if not os.path.isfile(os.path.join(settings.branch_dir, "summary.json")):
        fail(f"No extracted issues for branch '{settings.branch}' - run /sonar-init first", code=2)

    changed = ws.regenerate_patch(settings)  # defensive rebuild so preview == reality
    if not changed:
        fail("Nothing to publish - the workspace has no changes "
             "(solve an issue first: /sonar-issue-pick or /sonar-issues-solve)", code=2)

    target = args.target_branch or settings.github_branch
    fixed = gather_fixed_issues(settings)
    print_preview(settings, target, fixed)

    if args.dry_run:
        ok("[publish] dry-run only - nothing pushed")
        return
    if settings.fixtures:
        fail("--fixtures is offline - only --dry-run is allowed (no network writes)", code=2)

    if not args.yes:
        no_stdin_msg = ("This shell has no interactive stdin (normal inside agent terminals), so the "
                        "confirmation prompt cannot run. This is NOT an error in your changes: "
                        "ask the user to confirm the push in chat, then re-run the exact same "
                        "command with --yes added.")
        if not sys.stdin.isatty():
            fail(no_stdin_msg, code=2)
        try:
            answer = input(f"Type 'push' to commit these files to "
                           f"{settings.github_org}/{settings.github_repo}@{target}: ").strip()
        except EOFError:
            # Windows quirk: NUL/pipe stdin can still report isatty() == True
            fail(no_stdin_msg, code=2)
        if answer.lower() != "push":
            fail("Aborted - nothing pushed", code=2)

    client = settings.github_client()
    manifest = ws.load_manifest(settings) or {}
    message = args.message or default_message(fixed, changed)
    try:
        check_conflicts(settings, client, client.get_branch_sha(target), changed, manifest, args.force)
        commit = push(settings, client, target, message, changed, manifest)
    except HttpError as e:
        if e.status in (403, 404):
            fail(f"GITHUB_TOKEN cannot write to {settings.github_org}/{settings.github_repo} "
                 f"(HTTP {e.status}) - it needs write access (classic: 'repo' scope; "
                 f"fine-grained: Contents read/write). SSO orgs: a valid token still gets "
                 f"403 until authorized (token page -> 'Configure SSO' -> Authorize "
                 f"'{settings.github_org}'). Recreate/authorize the token and run "
                 f"set_mode.py github again.")
        if e.status == 422:
            fail(f"The branch moved during publish (HTTP 422) - re-run publish. ({e.body[:200]})")
        fail(f"GitHub API error HTTP {e.status}: {e.body[:300]}")

    record = {
        "commitSha": commit["sha"],
        "commitUrl": commit.get("html_url"),
        "targetBranch": target,
        "files": changed,
        "issuesCovered": [folder for folder, _, _ in fixed],
        "publishedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    }
    config.dump_json(settings.publish_record_path, record)

    # published state becomes the new baseline: workspace is clean again
    manifest["baseCommitSha"] = commit["sha"]
    ws.save_manifest(settings, manifest)
    ws.rebaseline(settings)

    ok(f"[publish] pushed {len(changed)} file(s) to {target} - commit {commit['sha'][:10]}")
    if commit.get("html_url"):
        print(f"[publish] {commit['html_url']}")
    print("[publish] Sonar clears the issues after CI re-analyzes that branch.")


if __name__ == "__main__":
    main()

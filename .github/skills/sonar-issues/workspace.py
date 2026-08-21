"""GitHub-mode scratch workspace CLI - fetch files to fix, regenerate the
cumulative changes.patch, inspect or discard the workspace.

GitHub-mode only: in local mode fixes edit the checkout directly and this
script refuses to run (exit 2).

Usage:
  python workspace.py fetch <repo-relative-path> [--branch B] [--fixtures]
  python workspace.py diff    [--branch B] [--fixtures]   # rebuild changes.patch, print diffstat
  python workspace.py status  [--branch B] [--fixtures]   # what's fetched, what's dirty
  python workspace.py discard [--branch B] [--fixtures] --yes

Exit codes: 0 ok | 1 error | 2 wrong mode / not initialized
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import init_console, fail, ok
from lib import config, workspace


def build_settings(args):
    settings = config.Settings(args)
    settings.require_mode()
    if settings.workflow_mode != "github":
        fail("The workspace is a github-mode concept - in local mode edit the checkout "
             "directly. (Switch modes with set_mode.py github, then re-run /sonar-init.)", code=2)
    if not settings.branch:
        fail("No branch ref - pass --branch <branchRef>", code=2)
    if not os.path.isfile(os.path.join(settings.branch_dir, "summary.json")):
        fail(f"No extracted issues for branch '{settings.branch}' - run /sonar-init first", code=2)
    return settings


def print_diffstat(settings):
    stats = workspace.diffstat(settings)
    if not stats:
        print("workspace: clean (no changes yet)")
        return
    for s in stats:
        tag = "  [new file]" if s["new"] else ""
        print(f"  {s['file']}  +{s['added']} -{s['removed']}{tag}")
    print(f"patch: {settings.patch_path}")


def main():
    init_console()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["fetch", "diff", "status", "discard"])
    parser.add_argument("path", nargs="?", default=None,
                        help="fetch: repo-relative file path (as shown in the issue)")
    parser.add_argument("--branch", default=None, help="Branch ref (the extracted branch)")
    parser.add_argument("--fixtures", action="store_true",
                        help="Offline mode: fetch from the bundled fixtures instead of GitHub")
    parser.add_argument("--yes", action="store_true", help="discard: skip the confirmation prompt")
    args = parser.parse_args()

    settings = build_settings(args)

    if args.command == "fetch":
        if not args.path:
            fail("fetch needs a file path: workspace.py fetch <repo-relative-path>")
        edited = workspace.fetch_file(settings, args.path)
        ok(f"[workspace] ready - apply the fix to THIS file (never the checkout):")
        print(edited)
    elif args.command == "diff":
        changed = workspace.regenerate_patch(settings)
        if changed:
            ok(f"[workspace] changes.patch rebuilt - {len(changed)} file(s) changed")
        else:
            print("[workspace] no changes - patch removed")
        print_diffstat(settings)
    elif args.command == "status":
        manifest = workspace.load_manifest(settings)
        if manifest is None:
            print("workspace: not created yet (workspace.py fetch <path> creates it)")
            return
        print(f"branch    : {manifest.get('branchRef')} (GitHub: {manifest.get('githubBranch')})")
        print(f"base sha  : {manifest.get('baseCommitSha')}")
        print(f"fetched   : {len(manifest.get('files', {}))} file(s)")
        for rel in sorted(manifest.get("files", {})):
            print(f"  {rel}")
        print_diffstat(settings)
    elif args.command == "discard":
        if not workspace.is_dirty(settings) or args.yes:
            workspace.discard(settings)
            ok("[workspace] discarded (workspace + changes.patch deleted)")
        else:
            fail("The workspace has UNPUBLISHED changes - re-run with --yes to delete them anyway")


if __name__ == "__main__":
    main()

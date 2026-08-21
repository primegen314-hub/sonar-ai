"""Choose and verify the workflow mode (local | github) in one guided step.

local  - fixes are made directly in this git checkout. The branch is resolved
         per run (Sonar URL branch= param, then SONAR_BRANCH, then the current
         checkout) - this script asks nothing and NEVER runs git checkout/pull
         for you; the pipeline tells you the exact command when the checkout
         needs to change. Tests run locally (verify.py via /sonar-verify).
github - no checkout needed; extraction reads code from the GitHub API, fixes
         land in a scratch workspace + changes.patch, and /publish-to-github
         commits them to GitHub. Tests run in CI after publishing.
         ("remote" is accepted as a permanent alias for "github".)

The chosen mode is persisted as WORKFLOW_MODE in the skill's .env (and
CONTEXT_SOURCE is derived from it - github -> github). Run with --show to
verify the current configuration without changing anything (exit 2 = no mode
chosen yet - /sonar-init uses this to know when to ask).

Usage:
  python set_mode.py local  [--sonar-branch NAME]
  python set_mode.py github [--token TOKEN | --no-token] [--org ORG] [--repo REPO]
                            [--repo-url URL] [--api-url URL] [--branch <analyzed-branch>]
  python set_mode.py --sonar-branch NAME     # local follow-up: Sonar names the branch differently
  python set_mode.py --show
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import init_console, fail, warn, ok, SKILL_DIR
from lib import envfile, gitinfo


def _write(env_path, pairs):
    for key, value in pairs:
        envfile.update_env(env_path, key, value)


def _normalize_mode(value):
    mode = (value or "").strip().lower()
    return "github" if mode == "remote" else mode


def show(env):
    mode = _normalize_mode(env.get("WORKFLOW_MODE"))
    if mode not in ("local", "github"):
        print("mode        : not set (run set_mode.py local|github)")
        sys.exit(2)
    print(f"mode        : {mode}")
    if mode == "local":
        branch = gitinfo.current_branch(os.getcwd())
        print(f"git branch  : {branch or 'NOT DETECTED (no git checkout?)'}")
        sonar_branch = (env.get("SONAR_BRANCH") or "").strip()
        print(f"sonar branch: {sonar_branch or '(same as git branch)'}")
    else:
        org, repo = env.get("GITHUB_ORG"), env.get("GITHUB_REPO")
        api = (env.get("GITHUB_API_URL") or "https://api.github.com").rstrip("/")
        print(f"github      : {org or '?'}/{repo or '?'} @ {api}")
        print(f"token       : {'set' if env.get('GITHUB_TOKEN') else 'MISSING (run set_mode.py github)'}")
    print(f"sonar host  : {env.get('SONAR_HOST') or 'not set'}")
    print(f"sonar token : {'minted' if env.get('SONAR_TOKEN') else 'not yet (s01 mints it)'}")
    missing = []
    if mode == "github":
        missing = [k for k in ("GITHUB_TOKEN", "GITHUB_ORG", "GITHUB_REPO") if not env.get(k)]
    if missing:
        print(f"status      : INCOMPLETE - missing {', '.join(missing)}")
    else:
        print("status      : configured")
    sys.exit(0)


def setup_local(args, env_path):
    root = gitinfo.repo_root()
    if not root:
        fail("local mode needs a git checkout, but no git repository was found here - "
             "open the project repository folder and re-run. "
             "(No checkout at all? Configure GitHub mode instead: set_mode.py github)")
    _write(env_path, [("WORKFLOW_MODE", "local"), ("CONTEXT_SOURCE", "local"),
                      ("SONAR_BRANCH", args.sonar_branch or "")])
    branch = gitinfo.current_branch(root)
    ok(f"[mode] WORKFLOW_MODE=local saved"
       + (f" - current checkout: '{branch}'" if branch else "")
       + (f" (Sonar branch: {args.sonar_branch})" if args.sonar_branch else ""))
    print("[mode] the branch is resolved per run: Sonar URL branch= param, then "
          "SONAR_BRANCH, then the current checkout. Fixes edit the checkout directly.")
    print("[mode] next: run the pipeline - python run_all.py <sonar-url>")


def parse_github_url(text):
    """Any way a user names a repo -> (host, org, repo, branch).

    Handles: bare 'org/repo', ssh 'git@host:org/repo.git', and full web URLs
    including deep links like .../org/repo/tree/<branch>/... or /blob/... -
    org/repo are the FIRST TWO path segments (dotted repo names preserved),
    and the segment after 'tree'/'blob' is the branch. host is None for the
    bare form; branch is None when the URL names no branch.
    """
    text = (text or "").strip()
    if not text:
        return None, None, None, None
    m = re.fullmatch(r"([\w.-]+)/([\w.-]+?)(?:\.git)?/?", text)  # bare org/repo
    if m:
        return None, m.group(1), m.group(2)[:-4] if m.group(2).endswith(".git") else m.group(2), None
    m = re.fullmatch(r"(?:ssh://)?git@([^:/\s]+)[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?/?", text)
    if m:
        return m.group(1), m.group(2), m.group(3), None
    m = re.match(r"(?:https?://)?([^/\s]+)/(.+)", text)  # web URL: host / path...
    if m:
        host, path = m.group(1), m.group(2)
        segments = [s for s in path.split("?")[0].split("#")[0].split("/") if s]
        if len(segments) >= 2:
            org, repo = segments[0], segments[1]
            if repo.endswith(".git"):
                repo = repo[:-4]
            branch = None
            if len(segments) >= 4 and segments[2] in ("tree", "blob"):
                branch = segments[3]
            return host, org, repo, branch
    return None, None, None, None


def _parse_repo_ref(text):
    """Back-compat shim: (org, repo) from any repo reference."""
    _, org, repo, _ = parse_github_url(text)
    return org, repo


def setup_github(args, env_path, env):
    org, repo = args.org, args.repo
    url_host = url_branch = None
    if args.repo_url and not (org and repo):
        url_host, org, repo, url_branch = parse_github_url(args.repo_url)
        if not (org and repo):
            fail(f"Could not parse org/repo from '{args.repo_url}' - "
                 "expected https://github.com/<org>/<repo>[/tree/<branch>] or <org>/<repo>")
    if not (org and repo):
        detected_org, detected_repo = gitinfo.remote_org_repo(os.getcwd())
        org = org or env.get("GITHUB_ORG") or detected_org
        repo = repo or env.get("GITHUB_REPO") or detected_repo
        if detected_org:
            print(f"[mode] origin remote -> org: {detected_org}, repo: {detected_repo}")
    if not (org and repo):
        # no git checkout here (github mode never requires one) - ask directly
        if sys.stdin.isatty():
            try:
                pasted = input("[mode] no git remote found here (that's fine - github mode "
                               "needs no checkout).\n[mode] Paste the GitHub repo URL "
                               "(a /tree/<branch> deep link works too) or org/repo: ").strip()
            except EOFError:
                pasted = ""
            url_host, org, repo, url_branch = parse_github_url(pasted)
        if not (org and repo):
            fail("Could not determine the repository - pass --repo-url "
                 "https://github.com/<org>/<repo> (or --org and --repo)")

    # a /tree/<branch> deep link names the analyzed branch - use it unless overridden
    if url_branch and not args.branch:
        args.branch = url_branch
        print(f"[mode] branch from the pasted URL -> GITHUB_BRANCH={url_branch}")
    # a non-github.com host means GitHub Enterprise - derive its API base
    if (url_host and url_host.lower() not in ("github.com", "www.github.com")
            and not args.api_url and not env.get("GITHUB_API_URL")):
        args.api_url = f"https://{url_host}/api/v3"
        print(f"[mode] GitHub Enterprise host detected -> GITHUB_API_URL={args.api_url}")

    token = args.token or env.get("GITHUB_TOKEN")
    if not token and args.no_token:
        print("[mode] --no-token: saving mode/org/repo without a token (status will be "
              "INCOMPLETE). Add it before extracting/publishing: run "
              "'python set_mode.py github' in YOUR terminal (hidden prompt).")
    elif not token:
        if sys.stdin.isatty():
            import getpass
            token = getpass.getpass(
                "[mode] GitHub token (hidden - needs WRITE access to the repo for publishing; "
                "or Ctrl+C and paste it into .env as GITHUB_TOKEN yourself): ").strip()
        else:
            warn("No terminal to prompt for the token - leaving GITHUB_TOKEN empty. "
                 f"Paste it into {env_path} manually.")
    _write(env_path, [("WORKFLOW_MODE", "github"), ("CONTEXT_SOURCE", "github"),
                      ("GITHUB_ORG", org), ("GITHUB_REPO", repo)])
    if token:
        envfile.update_env(env_path, "GITHUB_TOKEN", token)
    if args.api_url:
        envfile.update_env(env_path, "GITHUB_API_URL", args.api_url.rstrip("/"))
    if args.branch:
        envfile.update_env(env_path, "GITHUB_BRANCH", args.branch)

    ok(f"[mode] WORKFLOW_MODE=github saved to {env_path} ({org}/{repo})")
    if token:
        _validate_github(args, env, org, repo, token)
    print("[mode] done - the local checkout no longer matters. Fixes go to "
          "SONAR_ISSUES/<branch>/_workspace/ + changes.patch; push them with /publish-to-github.")


def _validate_github(args, env, org, repo, token):
    """Best-effort token + branch validation; never fatal."""
    from lib.github_api import GitHubClient
    api = (args.api_url or env.get("GITHUB_API_URL") or "https://api.github.com").rstrip("/")
    verify_ssl = env.get("SONAR_VERIFY_SSL", "true").strip().lower() != "false"
    client = GitHubClient(token, org, repo, api_base=api, verify_ssl=verify_ssl)
    try:
        scopes = client.token_scopes()
    except Exception as e:
        warn(f"could not validate the token against the API ({e}) - saved anyway")
        return
    if scopes is not None and not ({"repo", "public_repo"} & set(scopes)):
        warn(f"classic token scopes are [{', '.join(scopes) or 'none'}] - no 'repo' scope, "
             "so /publish-to-github will get 403. Recreate the token with write access. "
             "(SSO orgs: also authorize the token - token page -> 'Configure SSO'.)")
    branch = args.branch or gitinfo.current_branch(os.getcwd())
    if branch:
        try:
            exists = client.branch_exists(branch)
            ok(f"[mode] token works - branch '{branch}' "
               f"{'found' if exists else 'NOT found (pass --branch or set GITHUB_BRANCH if named differently)'}")
        except Exception as e:
            warn(f"could not check branch '{branch}' ({e}) - saved anyway")


def main():
    init_console()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", nargs="?", choices=["local", "github", "remote"],
                        help="workflow mode to configure ('remote' = alias for 'github')")
    parser.add_argument("--show", action="store_true", help="print the current mode and status, change nothing")
    parser.add_argument("--branch", default=None,
                        help="github: the analyzed branch when named differently on GitHub (GITHUB_BRANCH)")
    parser.add_argument("--sonar-branch", default=None,
                        help="local: the Sonar-side branch name when it differs from the git branch")
    parser.add_argument("--token", default=None, help="github: GitHub token (default: hidden prompt)")
    parser.add_argument("--no-token", action="store_true",
                        help="github: save mode/org/repo WITHOUT prompting for a token "
                             "(set it later - status stays INCOMPLETE until then)")
    parser.add_argument("--org", default=None, help="github: GitHub org (default: parsed from origin or --repo-url)")
    parser.add_argument("--repo", default=None, help="github: GitHub repo (default: parsed from origin or --repo-url)")
    parser.add_argument("--repo-url", default=None,
                        help="github: repo URL to derive org/repo from when there is no git checkout")
    parser.add_argument("--api-url", default=None,
                        help="github: API base for GitHub Enterprise, e.g. https://<host>/api/v3")
    args = parser.parse_args()

    env_path = envfile.env_path(SKILL_DIR)
    env = envfile.load_env(env_path)

    if args.show:
        show(env)
    elif args.mode == "local":
        setup_local(args, env_path)
    elif args.mode in ("github", "remote"):
        setup_github(args, env_path, env)
    elif args.sonar_branch:
        envfile.update_env(env_path, "SONAR_BRANCH", args.sonar_branch)
        ok(f"[mode] SONAR_BRANCH={args.sonar_branch} saved - extraction now queries Sonar "
           "with this branch name; re-run the pipeline.")
    else:
        parser.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()

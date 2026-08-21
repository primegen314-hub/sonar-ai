"""Resolve run settings from CLI args + pasted Sonar URL + .env, in that precedence order.

Every step script accepts the same arguments and calls resolve(); s02 persists the
resolved values to <branch>/_raw/meta.json so later steps stay consistent with the fetch.
"""
import argparse
import json
import os

from . import SKILL_DIR, OUTPUT_DIR_NAME, RAW_DIR_NAME, fail
from . import envfile, gitinfo, naming, url_parser

FIXTURES_DIR = os.path.join(SKILL_DIR, "fixtures")
DEFAULT_STATUSES = ["OPEN", "CONFIRMED"]


def build_parser(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("url", nargs="?", default=None,
                        help="Pasted SonarQube URL (host, project id, issueStatus, newCodePeriod are parsed from it)")
    parser.add_argument("--branch", default=None,
                        help="Branch ref override (default: URL branch param, then SONAR_BRANCH/.env, "
                             "then the current git branch in local mode)")
    parser.add_argument("--fixtures", action="store_true",
                        help="Offline mode: read bundled fixture API responses instead of the network")
    parser.add_argument("--discard-workspace", action="store_true",
                        help="Delete unpublished github-mode workspace edits instead of refusing to re-fetch")
    return parser


class Settings:
    def __init__(self, args):
        self.fixtures = bool(getattr(args, "fixtures", False))
        self.skill_dir = SKILL_DIR
        self.repo_root = gitinfo.repo_root() or os.getcwd()

        # .env lives inside the skill folder only (a host repo's root .env is ignored)
        self.env_path = envfile.find_env_file(self.skill_dir)
        self.env = envfile.load_env(self.env_path)
        url_info = url_parser.parse_sonar_url(args.url) if getattr(args, "url", None) else {}

        self.host = url_info.get("host") or self.env.get("SONAR_HOST")
        self.project = url_info.get("project") or self.env.get("SONAR_PROJECT_KEY")
        self.statuses = url_info.get("statuses") or _split(self.env.get("ISSUE_STATUSES")) or list(DEFAULT_STATUSES)
        if "new_code" in url_info:
            self.new_code = url_info["new_code"]
        else:
            self.new_code = self.env.get("SCOPE", "new_code").strip().lower() != "all"

        # ---- workflow mode ------------------------------------------------
        # WORKFLOW_MODE (local|github) is the single user-facing switch, set by
        # set_mode.py. "remote" is a permanently accepted alias for "github"
        # (older .env files). CONTEXT_SOURCE is derived from it (github ->
        # github) and kept only as the internal knob the extraction steps use.
        raw_mode = (self.env.get("WORKFLOW_MODE") or "").strip().lower()
        if raw_mode == "remote":
            raw_mode = "github"
        self.context_source = self.env.get("CONTEXT_SOURCE", "local").strip().lower()
        self.mode_configured = raw_mode in ("local", "github")
        if self.mode_configured:
            self.workflow_mode = raw_mode
            expected_source = "github" if raw_mode == "github" else "local"
            if self.context_source != expected_source:
                from . import warn
                warn(f"WORKFLOW_MODE={raw_mode} but CONTEXT_SOURCE={self.context_source} in .env - "
                     f"WORKFLOW_MODE wins; using CONTEXT_SOURCE={expected_source}. "
                     f"Run set_mode.py to repair .env.")
                self.context_source = expected_source
        else:
            # legacy .env without WORKFLOW_MODE: derive from CONTEXT_SOURCE
            self.workflow_mode = "github" if self.context_source == "github" else "local"

        self.sonar_branch_override = (self.env.get("SONAR_BRANCH") or "").strip() or None

        if self.workflow_mode == "github":
            # github mode: the checkout is irrelevant - the branch must come from
            # the CLI/URL/.env, NEVER from whatever happens to be checked out here
            self.git_branch = None
            self.branch = (getattr(args, "branch", None)
                           or url_info.get("branch")
                           or (self.env.get("GITHUB_BRANCH") or "").strip() or None)
        else:
            self.git_branch = gitinfo.current_branch(self.repo_root)
            self.branch = (getattr(args, "branch", None)
                           or url_info.get("branch")
                           or self.sonar_branch_override
                           or self.git_branch)
        self.verify_ssl = self.env.get("SONAR_VERIFY_SSL", "true").strip().lower() != "false"

        self.token = self.env.get("SONAR_TOKEN") or None
        self.user = self.env.get("SONAR_USER") or None
        self.password = self.env.get("SONAR_PASSWORD") or None

        self.test_command = self.env.get("TEST_COMMAND") or None
        self.build_command = self.env.get("BUILD_COMMAND") or None

        self.github_token = self.env.get("GITHUB_TOKEN") or None
        self.github_org = self.env.get("GITHUB_ORG") or None
        self.github_repo = self.env.get("GITHUB_REPO") or None
        self.github_api_url = (self.env.get("GITHUB_API_URL") or "https://api.github.com").rstrip("/")
        # explicit override for when the Sonar branch name does not exist on GitHub
        self.github_branch_override = self.env.get("GITHUB_BRANCH") or None

        if self.fixtures:
            self.host = self.host or "https://sonar.example.com"
            self.project = self.project or "example_report-service"
            self.branch = self.branch or "fixture-branch"

    # ---- derived paths ----------------------------------------------------
    @property
    def branch_folder(self):
        return naming.branch_folder(self.branch)

    @property
    def output_root(self):
        return os.path.join(self.repo_root, OUTPUT_DIR_NAME)

    @property
    def branch_dir(self):
        return os.path.join(self.output_root, self.branch_folder)

    @property
    def raw_dir(self):
        return os.path.join(self.branch_dir, RAW_DIR_NAME)

    @property
    def meta_path(self):
        return os.path.join(self.raw_dir, "meta.json")

    # ---- github-mode workspace paths --------------------------------------
    @property
    def workspace_dir(self):
        return os.path.join(self.branch_dir, "_workspace")

    @property
    def patch_path(self):
        return os.path.join(self.branch_dir, "changes.patch")

    @property
    def publish_record_path(self):
        return os.path.join(self.branch_dir, "publish.json")

    # ---- validation -------------------------------------------------------
    def require_fetch_params(self):
        if not self.host:
            fail("No Sonar host. Paste a Sonar URL or set SONAR_HOST in .env")
        if not self.project:
            fail("No project key. Paste a Sonar URL containing id=<projectKey> or set SONAR_PROJECT_KEY in .env")
        if not self.branch:
            if self.workflow_mode == "github":
                fail("No branch ref. GitHub mode never uses the checked-out branch - "
                     "pass --branch <name>, paste a Sonar URL with branch=, or set GITHUB_BRANCH in .env")
            fail("No branch ref. Run inside a git checkout or pass --branch <name>")

    def require_mode(self):
        """Hard gate for scripts that only make sense after /sonar-init chose a mode."""
        if not self.mode_configured:
            fail(f"Workflow mode is not configured - run /sonar-init first "
                 f"(it runs: python {os.path.join(self.skill_dir, 'set_mode.py')} local|github)", code=2)

    def load_meta(self):
        if not os.path.isfile(self.meta_path):
            fail(f"{self.meta_path} not found - run s02_fetch_issues.py first (same URL/--branch arguments)")
        with open(self.meta_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def sonar_client(self):
        from .sonar_api import SonarClient
        return SonarClient(
            host=self.host,
            token=self.token,
            user=self.user,
            password=self.password,
            verify_ssl=self.verify_ssl,
            fixtures_dir=FIXTURES_DIR if self.fixtures else None,
        )

    # ---- GitHub (CONTEXT_SOURCE=github) -----------------------------------
    @property
    def github_branch(self):
        """Branch name to use on GitHub: explicit .env override wins, else the Sonar branch."""
        return self.github_branch_override or self.branch

    def github_client(self):
        from .github_api import GitHubClient
        missing = [k for k, v in (("GITHUB_TOKEN", self.github_token),
                                  ("GITHUB_ORG", self.github_org),
                                  ("GITHUB_REPO", self.github_repo)) if not v]
        if missing:
            fail(f"GitHub mode needs {', '.join(missing)} in {self.env_path or 'the skill .env'} - "
                 f"run: python {os.path.join(self.skill_dir, 'set_mode.py')} github")
        return GitHubClient(
            token=self.github_token,
            org=self.github_org,
            repo=self.github_repo,
            api_base=self.github_api_url,
            verify_ssl=self.verify_ssl,
        )

    def _check_sonar_branch(self):
        """Fail early with a clean message when Sonar has no such branch (the
        git-name != sonar-name mismatch case); silent when the server can't answer."""
        try:
            exists = self.sonar_client().branch_exists(self.project, self.branch)
        except Exception:
            return
        if exists is False:
            fail(f"Sonar has no branch '{self.branch}' for project '{self.project}'. "
                 f"If Sonar analyzes this code under a different branch name, provide it:\n"
                 f"  python {os.path.join(self.skill_dir, 'set_mode.py')} --sonar-branch <sonar-branch-name>\n"
                 f"then re-run the pipeline.")

    def check_branch(self):
        """Hard gate before fetching (skipped in fixtures mode).

        github mode: the branch must exist on GitHub (Sonar and GitHub branch
                     names are identical by convention; GITHUB_BRANCH overrides).
                     The local checkout is never consulted.
        local  mode: the Sonar branch must equal the checked-out git branch
                     (unless SONAR_BRANCH declares an intentional name mismatch),
                     and the checkout must be in sync with origin. Failures give
                     exactly ONE remedy command for the user to run - local mode
                     never suggests switching modes mid-flow.
        """
        if self.fixtures:
            return
        if self.context_source == "github":
            from .http_client import HttpError
            client = self.github_client()
            branch = self.github_branch
            try:
                exists = client.branch_exists(branch)
            except HttpError as e:
                if e.status == 403:
                    fail(f"GitHub returned HTTP 403 for {self.github_org}/{self.github_repo} - "
                         f"the token cannot access this repository. Check, in this order:\n"
                         f"  1. Token scope: classic tokens need 'repo'; fine-grained need "
                         f"Contents read/write for this repository.\n"
                         f"  2. SSO: if the org uses SAML SSO, a valid token STILL gets 403 until "
                         f"it is authorized - GitHub -> Settings -> Developer settings -> your "
                         f"token -> 'Configure SSO' -> Authorize '{self.github_org}'.\n"
                         f"  3. GitHub Enterprise: GITHUB_API_URL must be https://<host>/api/v3.\n"
                         f"Fix the token (set_mode.py github in YOUR terminal), then re-run.")
                fail(f"GitHub API error HTTP {e.status} while checking branch '{branch}' on "
                     f"{self.github_org}/{self.github_repo}: {e.body[:200]}")
            if not exists:
                fail(f"Branch '{branch}' does not exist on GitHub "
                     f"({self.github_org}/{self.github_repo}). Sonar and GitHub branch names "
                     f"often differ slightly (e.g. a '-v2' suffix on GitHub only) - find the "
                     f"exact branch name in the GitHub UI and add "
                     f"GITHUB_BRANCH=<github-branch-name> to "
                     f"{self.env_path or envfile.env_path(self.skill_dir)}, or re-run "
                     f"set_mode.py github --branch <github-branch-name>")
            return
        from . import warn
        self._check_sonar_branch()
        local = self.git_branch
        if local is None:
            warn("Could not detect the checked-out git branch (detached HEAD or no git); "
                 "snippets may not match the code Sonar analyzed.")
            return
        if self.sonar_branch_override:
            # intentional mismatch: Sonar analyzes under a different name; the
            # sync gate below still guards the *git* branch we read code from
            pass
        elif self.branch and local != self.branch:
            fail(f"Sonar branch '{self.branch}' != checked-out git branch '{local}'.\n"
                 f"Run this in your terminal, then re-run the pipeline:\n"
                 f"  git checkout {self.branch} && git pull\n"
                 f"(Only if Sonar simply names this branch differently: "
                 f"python {os.path.join(self.skill_dir, 'set_mode.py')} --sonar-branch {self.branch})")
        # now verify the checkout is in sync with origin (Sonar analyzed the
        # PUSHED state; a stale local checkout silently drifts lines)
        if self.env.get("SYNC_CHECK", "true").strip().lower() == "false":
            return
        remote_sha = gitinfo.remote_head(local, self.repo_root)
        if remote_sha is None:
            warn("Could not reach origin to verify the branch is in sync (offline? no remote?) "
                 "- continuing. Set SYNC_CHECK=false in .env to silence this.")
            return
        local_sha = gitinfo.local_head(self.repo_root)
        if local_sha == remote_sha:
            return
        if gitinfo.is_ancestor(remote_sha, local_sha, self.repo_root):
            warn(f"Local '{local}' is AHEAD of origin (unpushed commits) - Sonar has not "
                 "analyzed them yet; extraction continues against your local code.")
            return
        fail(f"Local '{local}' is OUT OF SYNC with origin (Sonar analyzed the pushed "
             f"state; a stale checkout gives wrong line numbers).\n"
             f"Run this in your terminal, then re-run the pipeline:\n"
             f"  git pull\n"
             f"(SYNC_CHECK=false in .env disables this gate entirely)")


def _split(value):
    if not value:
        return None
    return [s.strip().upper() for s in value.split(",") if s.strip()]


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

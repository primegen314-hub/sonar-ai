"""Regression tests for the sonar-issues pipeline. Stdlib only (unittest).

Run from the repo root:
  python -m unittest discover .github/skills/sonar-issues/tests -v

Two layers:
  * unit tests on the pure decision functions (URL parsing, mode normalization,
    repo-ref parsing, effort tiers)
  * gate tests that run the real scripts against the bundled fixtures in an
    isolated temp copy (no network, no credentials, never touches the repo's
    own .env or SONAR_ISSUES/)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)

from lib import effort, url_parser  # noqa: E402
import pick_issue  # noqa: E402
import set_mode  # noqa: E402


class UrlParserTests(unittest.TestCase):
    def test_full_url(self):
        info = url_parser.parse_sonar_url(
            "https://sonar.example.com/project/issues?id=my_proj&branch=feat%2Fx"
            "&issueStatuses=OPEN,CONFIRMED&inNewCodePeriod=true")
        self.assertEqual(info["project"], "my_proj")
        self.assertEqual(info["branch"], "feat/x")
        self.assertEqual(info["statuses"], ["OPEN", "CONFIRMED"])
        self.assertTrue(info["new_code"])

    def test_schemeless_url(self):
        info = url_parser.parse_sonar_url("sonar.example.com/project/issues?id=p1")
        self.assertEqual(info["project"], "p1")
        self.assertEqual(info["host"], "https://sonar.example.com")


class ModeNormalizationTests(unittest.TestCase):
    def test_remote_alias_is_github(self):
        self.assertEqual(pick_issue.normalize_mode("remote"), "github")
        self.assertEqual(pick_issue.normalize_mode("GitHub"), "github")
        self.assertEqual(pick_issue.normalize_mode("local"), "local")
        self.assertEqual(pick_issue.normalize_mode(None), "local")

    def test_set_mode_show_normalization(self):
        self.assertEqual(set_mode._normalize_mode("remote"), "github")
        self.assertEqual(set_mode._normalize_mode(" github "), "github")


class RepoRefTests(unittest.TestCase):
    def test_org_repo_forms(self):
        cases = {
            "org/repo": ("org", "repo"),
            "org/repo.git": ("org", "repo"),
            "https://github.com/org/repo": ("org", "repo"),
            "https://github.com/org/repo.git/": ("org", "repo"),
            "git@github.com:org/repo.git": ("org", "repo"),
            "": (None, None),
            "no-slash-here": (None, None),
        }
        for text, expected in cases.items():
            self.assertEqual(set_mode._parse_repo_ref(text), expected, text)

    def test_deep_links_and_hosts(self):
        # the enterprise shape: dotted repo name + /tree/<branch> deep link
        host, org, repo, branch = set_mode.parse_github_url(
            "https://github.com/ExampleOrgInternal/123.abc1.abc-download-service"
            "/tree/TASK-4567-abc-or-download-service-or-upgrade-spring-boot-v2")
        self.assertEqual(host, "github.com")
        self.assertEqual(org, "ExampleOrgInternal")
        self.assertEqual(repo, "123.abc1.abc-download-service")
        self.assertEqual(branch,
                         "TASK-4567-abc-or-download-service-or-upgrade-spring-boot-v2")
        # blob deep link
        self.assertEqual(
            set_mode.parse_github_url("https://github.com/o/r/blob/main/src/App.java")[3],
            "main")
        # GitHub Enterprise host survives (used to auto-derive api/v3)
        self.assertEqual(
            set_mode.parse_github_url("https://ghe.corp.net/org/repo/tree/dev")[0],
            "ghe.corp.net")
        # plain repo URL: no branch
        self.assertEqual(
            set_mode.parse_github_url("https://github.com/o/r")[3], None)
        # query strings / fragments don't leak into segments
        self.assertEqual(
            set_mode.parse_github_url("https://github.com/o/r/tree/dev?tab=readme")[3],
            "dev")


class EffortTierTests(unittest.TestCase):
    def test_minutes(self):
        self.assertEqual(effort.effort_minutes("1h30min"), 90)
        self.assertEqual(effort.effort_minutes("2d"), 960)
        self.assertIsNone(effort.effort_minutes(None))

    def test_simple_issue_is_normal(self):
        # trivial code smell, tests exist, tiny blast radius, no Sonar estimate:
        # the score still computes (never fails) and stays low
        entry = {"type": "CODE_SMELL", "severity": "MINOR", "recommended": "sonar"}
        ctx = {"usedBy": [], "coChangedFiles": [], "testFiles": ["T.java"]}
        tier, reason = effort.ai_effort_for_issue(entry, ctx)
        self.assertEqual(tier, "normal")
        self.assertEqual(reason, "simple, low-risk fix")

    def test_blast_radius_bug_without_tests_is_max(self):
        entry = {"type": "BUG", "severity": "MAJOR", "recommended": "sonar"}
        ctx = {"usedBy": [{}, {}, {}], "coChangedFiles": [], "testFiles": []}
        tier, reason = effort.ai_effort_for_issue(entry, ctx)  # 2+1+1 = 4
        self.assertEqual(tier, "max")
        self.assertIn("usedBy", reason)

    def test_vulnerability_wide_radius_is_xmax(self):
        entry = {"type": "VULNERABILITY", "severity": "BLOCKER", "recommended": "ai",
                 "effort": "1h"}
        ctx = {"usedBy": [{}, {}, {}], "coChangedFiles": [{}, {}, {}], "testFiles": []}
        tier, _ = effort.ai_effort_for_issue(entry, ctx)  # 2+1+2+1+1+1+1 = 9
        self.assertEqual(tier, "xMax")

    def test_missing_context_never_fails(self):
        # empty entry + no context at all: only the no-tests factor fires (+1)
        score, factors = effort.complexity_score({}, None)
        self.assertEqual(score, 1)
        self.assertEqual(factors, ["no tests covering the file"])
        tier, reason = effort.ai_effort_for_issue({}, None)
        self.assertEqual(tier, "normal")
        self.assertIn("no tests", reason)

    def test_batch_from_distribution(self):
        scored = [(0, []), (1, ["2 usedBy file(s)"]), (4, ["BUG", "no tests covering the file"])]
        tier, reason = effort.ai_effort_for_batch(scored)
        self.assertEqual(tier, "high")  # mean 1.67 -> round 2 -> high
        self.assertIn("3 issue(s)", reason)
        self.assertEqual(effort.ai_effort_for_batch([]), ("normal", "no issues to estimate"))

    def test_no_tier_mentions_verify(self):
        # tiers are analysis depth ONLY - the docstring must not promise test runs
        self.assertNotIn("full-suite verify", effort.__doc__)
        self.assertIn("No tier ever runs tests", effort.__doc__)


class GateTests(unittest.TestCase):
    """Real script runs against fixtures, fully isolated in a temp folder."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="sonar-tests-")
        cls.sk = os.path.join(cls.tmp, "sk")
        shutil.copytree(SKILL_DIR, cls.sk,
                        ignore=shutil.ignore_patterns("__pycache__", "tests", ".env"))
        env_file = os.path.join(cls.sk, ".env")
        if os.path.exists(env_file):
            os.remove(env_file)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_script(self, script, *args, env_lines=None):
        env_file = os.path.join(self.sk, ".env")
        if env_lines is None:
            if os.path.exists(env_file):
                os.remove(env_file)
        else:
            with open(env_file, "w", encoding="utf-8") as f:
                f.write("\n".join(env_lines) + "\n")
        result = subprocess.run(
            [sys.executable, os.path.join(self.sk, script)] + list(args),
            cwd=self.tmp, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=120, stdin=subprocess.DEVNULL)
        return result.returncode, (result.stdout or "") + (result.stderr or "")

    GITHUB_ENV = ["WORKFLOW_MODE=github", "CONTEXT_SOURCE=github",
                  "GITHUB_ORG=x", "GITHUB_REPO=y", "GITHUB_TOKEN=t"]

    def test_01_fixtures_pipeline_local(self):
        code, out = self.run_script("run_all.py", "--fixtures", "--branch", "demo")
        self.assertEqual(code, 0, out)
        self.assertIn("validation OK", out)

    def test_02_fixtures_pipeline_github_via_remote_alias(self):
        code, out = self.run_script(
            "run_all.py", "--fixtures", "--branch", "demo-r",
            env_lines=["WORKFLOW_MODE=remote", "CONTEXT_SOURCE=github",
                       "GITHUB_ORG=x", "GITHUB_REPO=y"])
        self.assertEqual(code, 0, out)
        self.assertIn("mode     : github", out)

    def test_02c_stats_report_and_roadmap(self):
        # fixtures tree (from test_01): S1068+S1481 are rec:sonar/eff:normal
        # (quick-wins slice), S2095 is the hard tail - no cluster reaches 3
        code, out = self.run_script("pick_issue.py", "--stats", "--fixtures",
                                    "--branch", "demo")
        self.assertEqual(code, 0, out)
        self.assertIn("unresolved: 3/3", out)
        self.assertIn("by rule:", out)
        self.assertIn("S1481", out)
        self.assertIn("fix roadmap", out)
        self.assertIn("/sonar-quick-wins", out)
        self.assertIn("2 safe-fix issue(s)", out)
        self.assertIn("/sonar-issue-pick", out)
        self.assertIn("/sonar-verify", out)
        # resolved issues drop out of every count (clean up so later tests
        # still see an untouched demo tree)
        demo = os.path.join(self.tmp, "SONAR_ISSUES", "demo")
        folder = next(f for f in os.listdir(demo) if "S1481" in f)
        res_path = os.path.join(demo, folder, "resolution.json")
        with open(res_path, "w", encoding="utf-8") as f:
            json.dump({"status": "fixed", "reason": "x", "filesChanged": [],
                       "testsRun": [], "mode": "local"}, f)
        try:
            code, out = self.run_script("pick_issue.py", "--stats", "--fixtures",
                                        "--branch", "demo")
            self.assertEqual(code, 0, out)
            self.assertIn("unresolved: 2/3", out)
            self.assertNotIn("S1481", out)
        finally:
            os.remove(res_path)

    def test_03_verify_refuses_in_github_mode_exit_4(self):
        code, out = self.run_script("verify.py", "--issue", "2", "--branch", "demo-r",
                                    "--fixtures", env_lines=self.GITHUB_ENV)
        self.assertEqual(code, 4, out)

    def test_03b_verify_compile_only(self):
        # BUILD_COMMAND set: quick compile check passes without any tests
        code, out = self.run_script(
            "verify.py", "--compile", "--branch", "demo", "--fixtures",
            env_lines=["WORKFLOW_MODE=local", "CONTEXT_SOURCE=local",
                       "BUILD_COMMAND=echo build-ok"])
        self.assertEqual(code, 0, out)
        self.assertIn("COMPILES", out)
        # github mode still refuses by design
        code, out = self.run_script("verify.py", "--compile", "--branch", "demo-r",
                                    "--fixtures", env_lines=self.GITHUB_ENV)
        self.assertEqual(code, 4, out)

    def test_04_publish_refuses_in_local_mode_exit_2(self):
        code, out = self.run_script(
            "publish.py", "--branch", "demo", "--fixtures",
            env_lines=["WORKFLOW_MODE=local", "CONTEXT_SOURCE=local"])
        self.assertEqual(code, 2, out)
        self.assertIn("github-mode only", out)

    def test_05_mode_gate_exit_2_when_unset(self):
        code, out = self.run_script("set_mode.py", "--show")
        self.assertEqual(code, 2, out)
        self.assertIn("not set", out)

    def test_06_set_mode_github_without_git_via_repo_url(self):
        code, out = self.run_script(
            "set_mode.py", "github",
            "--repo-url", "https://github.com/acme/report-service", "--token", "t")
        self.assertEqual(code, 0, out)
        with open(os.path.join(self.sk, ".env"), encoding="utf-8") as f:
            env = f.read()
        self.assertIn("WORKFLOW_MODE=github", env)
        self.assertIn("GITHUB_ORG=acme", env)
        self.assertIn("GITHUB_REPO=report-service", env)

    def test_06b_set_mode_github_no_token_skip_path(self):
        # "[Skip - set it later]": agent-safe, never prompts, saves INCOMPLETE state
        code, out = self.run_script(
            "set_mode.py", "github",
            "--repo-url", "https://github.com/acme/later-repo/tree/dev", "--no-token")
        self.assertEqual(code, 0, out)
        self.assertIn("--no-token", out)
        with open(os.path.join(self.sk, ".env"), encoding="utf-8") as f:
            env = f.read()
        self.assertIn("GITHUB_REPO=later-repo", env)
        self.assertIn("GITHUB_BRANCH=dev", env)
        self.assertNotIn("GITHUB_TOKEN=", env.replace("GITHUB_TOKEN=\n", ""))
        code, out = self.run_script("set_mode.py", "--show",
                                    env_lines=["WORKFLOW_MODE=github",
                                               "GITHUB_ORG=acme", "GITHUB_REPO=later-repo"])
        self.assertIn("INCOMPLETE", out)

    def test_07_set_mode_local_never_touches_git(self):
        # no .git in tmp: local must refuse with the open-the-repo message
        code, out = self.run_script("set_mode.py", "local")
        self.assertNotEqual(code, 0)
        self.assertIn("open the project repository folder", out)

    def test_08_publish_non_tty_needs_yes_exit_2(self):
        # put one edit in the workspace so publish reaches the confirmation gate,
        # which (non-fixtures, non-tty, no --yes) must fail with guidance, exit 2 -
        # all before any network I/O
        rel = "src/main/java/com/example/report/ReportService.java"
        code, out = self.run_script("workspace.py", "fetch", rel, "--branch", "demo-r",
                                    "--fixtures", env_lines=self.GITHUB_ENV)
        self.assertEqual(code, 0, out)
        edited = os.path.join(self.tmp, "SONAR_ISSUES", "demo-r", "_workspace",
                              "edited", rel.replace("/", os.sep))
        with open(edited, "a", encoding="utf-8") as f:
            f.write("// touched by test\n")
        code, out = self.run_script("publish.py", "--branch", "demo-r",
                                    env_lines=self.GITHUB_ENV)
        self.assertEqual(code, 2, out)
        self.assertIn("--yes", out)

    def test_09_sync_gate_prints_single_command(self):
        # scratch repo behind its origin -> the OUT OF SYNC error names ONLY git pull
        work = os.path.join(self.tmp, "work")
        origin = os.path.join(self.tmp, "origin.git")
        for cmd in (["git", "init", "-q", "--bare", origin],
                    ["git", "clone", "-q", origin, work]):
            subprocess.run(cmd, cwd=self.tmp, capture_output=True, timeout=60)
        def git(*a):
            subprocess.run(["git"] + list(a), cwd=work, capture_output=True, timeout=60)
        git("checkout", "-q", "-b", "main")
        git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
            "--allow-empty", "-m", "A")
        git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
            "--allow-empty", "-m", "B")
        git("push", "-q", "origin", "main")
        git("reset", "-q", "--hard", "HEAD~1")
        with open(os.path.join(self.sk, ".env"), "w", encoding="utf-8") as f:
            f.write("SONAR_HOST=http://127.0.0.1:9\nSONAR_PROJECT_KEY=x\n"
                    "WORKFLOW_MODE=local\nCONTEXT_SOURCE=local\n")
        result = subprocess.run(
            [sys.executable, os.path.join(self.sk, "steps", "s02_fetch_issues.py"),
             "--branch", "main"],
            cwd=work, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=120, stdin=subprocess.DEVNULL)
        out = (result.stdout or "") + (result.stderr or "")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("OUT OF SYNC", out)
        self.assertIn("git pull", out)
        self.assertNotIn("remote mode", out)      # no mode-switch offer
        self.assertNotIn("WORKFLOW_MODE=", out)   # no edit-.env-yourself offer


if __name__ == "__main__":
    unittest.main()

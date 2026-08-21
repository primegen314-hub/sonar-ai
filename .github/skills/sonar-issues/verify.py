"""Run the verification tests for solved Sonar issues.

Command resolution: TEST_COMMAND from the skill's .env wins; when empty the
runner is auto-detected from the repository (maven / gradle / npm / pytest)
and the chosen command is printed before running.

Usage:
  python verify.py --full                [--branch NAME]   whole test suite
  python verify.py --issue <selector>    [--branch NAME]   only that issue's testFiles
                                                           (selector = seq | folder prefix | Sonar key)
  python verify.py --set-command "<cmd>"                   persist TEST_COMMAND into the
                                                           skill .env (asked once, reused forever)

Exit codes: 0 = tests passed, 3 = nothing to run (no testFiles and no BUILD_COMMAND),
2 = usage/config error, 4 = github mode (tests can NOT run locally - by design),
anything else = the test runner's exit code.
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import init_console, fail, warn, ok
from lib import config, envfile


def detect_runner(repo_root):
    """Return (kind, full_command) detected from project files, or (None, None)."""
    def has(*names):
        return any(os.path.exists(os.path.join(repo_root, n)) for n in names)

    if has("pom.xml"):
        mvn = "mvnw.cmd" if (os.name == "nt" and has("mvnw.cmd")) else \
              "./mvnw" if has("mvnw") else "mvn"
        return "maven", f"{mvn} -B test"
    if has("build.gradle", "build.gradle.kts"):
        gradle = "gradlew.bat" if (os.name == "nt" and has("gradlew.bat")) else \
                 "./gradlew" if has("gradlew") else "gradle"
        return "gradle", f"{gradle} test"
    if has("package.json"):
        try:
            with open(os.path.join(repo_root, "package.json"), "r", encoding="utf-8-sig") as f:
                if "test" in (json.load(f).get("scripts") or {}):
                    return "npm", "npm test"
        except (OSError, ValueError):
            pass
    if has("pytest.ini", "setup.cfg", "pyproject.toml", "conftest.py"):
        return "pytest", f"{os.path.basename(sys.executable)} -m pytest"
    return None, None


def scoped_command(kind, full_command, test_files):
    """Narrow the full command to only the given test files, per runner."""
    if kind == "maven":
        classes = ",".join(stem(p) for p in test_files)
        return f"{full_command.split(' test')[0]} test -Dtest={classes} -DfailIfNoTests=false"
    if kind == "gradle":
        filters = " ".join(f'--tests "{stem(p)}"' for p in test_files)
        return f"{full_command} {filters}"
    if kind == "npm":
        return f"{full_command} -- " + " ".join(f'"{p}"' for p in test_files)
    if kind == "pytest":
        return f"{full_command} " + " ".join(f'"{p}"' for p in test_files)
    return None


def stem(path):
    return path.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]


def find_issue_folder(settings, selector):
    summary_path = os.path.join(settings.branch_dir, "summary.json")
    if not os.path.isfile(summary_path):
        fail(f"{summary_path} not found - run the pipeline first", code=2)
    with open(summary_path, "r", encoding="utf-8") as f:
        entries = json.load(f).get("issues", [])
    sel = selector.strip()
    match = None
    if sel.isdigit():
        match = next((e for e in entries if e["seq"] == int(sel)), None)
    if match is None:
        match = next((e for e in entries if e["folder"].startswith(sel)), None)
    if match is None:
        match = next((e for e in entries if e["key"] == sel), None)
    if match is None:
        fail(f"No issue matches '{sel}'", code=2)
    return match["folder"]


def run(command, repo_root):
    print(f"[verify] running: {command}")
    print(f"[verify] cwd    : {repo_root}")
    result = subprocess.run(command, shell=True, cwd=repo_root)
    return result.returncode


def main():
    init_console()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--full", action="store_true", help="run the whole test suite")
    parser.add_argument("--issue", default=None, help="run only this issue's testFiles")
    parser.add_argument("--branch", default=None, help="branch ref (default: current git branch)")
    parser.add_argument("--set-command", default=None, metavar="CMD",
                        help="persist CMD as TEST_COMMAND in the skill .env, then exit")
    parser.add_argument("--fixtures", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.url = None  # Settings expects it
    if not args.full and not args.issue and not args.set_command:
        parser.print_help()
        sys.exit(2)

    settings = config.Settings(args)

    if args.set_command:
        env_path = settings.env_path or envfile.env_path(settings.skill_dir)
        envfile.update_env(env_path, "TEST_COMMAND", args.set_command)
        ok(f"[verify] TEST_COMMAND saved to {env_path} - reused for every future verify")
        return

    if settings.workflow_mode == "github":
        fail("GitHub mode: fixes live in SONAR_ISSUES/<branch>/_workspace/, not in any "
             "checkout, so there is no fixed code here to test - running local tests "
             "would test the UNFIXED code. Verify after publishing instead: let CI test "
             "the pushed branch, or pull the published branch locally and run the tests "
             "there.", code=4)

    kind = None
    if settings.test_command:
        full_command = settings.test_command
        print(f"[verify] TEST_COMMAND from .env: {full_command}")
    else:
        kind, full_command = detect_runner(settings.repo_root)
        if not full_command:
            fail("No TEST_COMMAND in the skill .env and no known runner detected "
                 "(pom.xml / build.gradle / package.json / pytest). "
                 f"Set TEST_COMMAND in {settings.env_path or 'the skill .env'}", code=2)
        print(f"[verify] auto-detected {kind}: {full_command}")

    if args.full:
        code = run(full_command, settings.repo_root)
    else:
        folder = find_issue_folder(settings, args.issue)
        context_path = os.path.join(settings.branch_dir, folder, "context.json")
        with open(context_path, "r", encoding="utf-8") as f:
            test_files = json.load(f).get("testFiles", [])
        if not test_files:
            if settings.build_command:
                warn(f"{folder}: no testFiles known - running BUILD_COMMAND instead")
                code = run(settings.build_command, settings.repo_root)
            else:
                warn(f"{folder}: no testFiles known and no BUILD_COMMAND set - nothing to run. "
                     "Use --full for a safety net.")
                sys.exit(3)
        else:
            command = scoped_command(kind, full_command, test_files) if kind else None
            if command is None:
                # custom TEST_COMMAND (or unknown runner): can't scope reliably
                print("[verify] cannot scope a custom TEST_COMMAND - running it in full")
                command = full_command
            code = run(command, settings.repo_root)

    if code == 0:
        ok("[verify] PASSED")
    else:
        print(f"[verify] FAILED (exit {code})", file=sys.stderr)
    sys.exit(code)


if __name__ == "__main__":
    main()

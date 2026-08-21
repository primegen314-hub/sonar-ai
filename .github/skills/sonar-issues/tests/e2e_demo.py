"""End-to-end demo: the WHOLE journey, both modes, offline, in a temp folder.

Proves the pipeline works without touching your repo, network, or credentials:

  LOCAL : init -> list -> fix in a real git checkout -> phantom-fix guard
          (git diff --stat) -> resolution.json -> /sonar-verify (--full) -> 1/3 fixed
  GITHUB: init (remote alias) -> workspace fetch -> fix the workspace copy ->
          changes.patch (validated with `git apply --check`) -> resolution.json ->
          publish --dry-run preview

Run from the repo root (stdlib only, ~10 seconds):
  python .github/skills/sonar-issues/tests/e2e_demo.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REL_FILE = "src/main/java/com/example/report/ReportService.java"
PASSED = []


def stage(name, ok, detail=""):
    mark = "\x1b[92mPASS\x1b[0m" if ok else "\x1b[91mFAIL\x1b[0m"
    print(f"  [{mark}] {name}" + (f" - {detail}" if detail else ""))
    PASSED.append(ok)
    if not ok:
        print("\ne2e demo FAILED at the stage above.")
        sys.exit(1)


def run(cmd, cwd, env_lines=None, sk=None):
    if env_lines is not None and sk:
        with open(os.path.join(sk, ".env"), "w", encoding="utf-8") as f:
            f.write("\n".join(env_lines) + "\n")
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=180,
                       stdin=subprocess.DEVNULL)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    tmp = tempfile.mkdtemp(prefix="sonar-e2e-")
    sk = os.path.join(tmp, "sk")
    shutil.copytree(SKILL_DIR, sk, ignore=shutil.ignore_patterns("__pycache__", "tests", ".env"))
    py = sys.executable

    print("\n== LOCAL MODE ==")
    work = os.path.join(tmp, "checkout")
    os.makedirs(work)
    shutil.copytree(os.path.join(sk, "fixtures", "sample_src", "src"),
                    os.path.join(work, "src"))
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t",
                 "commit", "-q", "-m", "baseline"]):
        run(cmd, work)

    code, out = run([py, os.path.join(sk, "run_all.py"), "--fixtures", "--branch", "demo"],
                    work, env_lines=["WORKFLOW_MODE=local", "CONTEXT_SOURCE=local",
                                     "TEST_COMMAND=echo tests-ok"], sk=sk)
    stage("init: run_all --fixtures (local)", code == 0 and "validation OK" in out)

    code, out = run([py, os.path.join(sk, "pick_issue.py"), "--next", "--branch", "demo",
                     "--fixtures"], work)
    stage("solve: pick_issue --next briefs issue 1", code == 0 and "seq     : 1" in out)

    src = os.path.join(work, REL_FILE.replace("/", os.sep))
    text = open(src, encoding="utf-8").read()
    fixed = text.replace("private TranslateService translateService;", "", 1)
    open(src, "w", encoding="utf-8", newline="").write(fixed)
    code, out = run(["git", "diff", "--stat", "--", REL_FILE], work)
    stage("guard: git diff --stat proves the edit landed",
          code == 0 and "1 file changed" in out, out.strip().splitlines()[-1])

    branch_dir = os.path.join(work, "SONAR_ISSUES", "demo")
    folder = next(d for d in os.listdir(branch_dir) if d.startswith("001_"))
    with open(os.path.join(branch_dir, folder, "resolution.json"), "w", encoding="utf-8") as f:
        json.dump({"status": "fixed", "reason": "removed unused field",
                   "filesChanged": [REL_FILE], "testsRun": [], "mode": "local"}, f)
    code, out = run([py, os.path.join(sk, "verify.py"), "--full", "--branch", "demo",
                     "--fixtures"], work)
    stage("verify: /sonar-verify full suite", code == 0 and "PASSED" in out)

    code, out = run([py, os.path.join(sk, "pick_issue.py"), "--list", "--branch", "demo",
                     "--fixtures"], work)
    stage("report: 1/3 fixed in --list", code == 0 and "1/3 fixed" in out)

    print("\n== GITHUB MODE (via the 'remote' alias) ==")
    gh_env = ["WORKFLOW_MODE=remote", "CONTEXT_SOURCE=github",
              "GITHUB_ORG=acme", "GITHUB_REPO=report-service", "GITHUB_TOKEN=t"]
    code, out = run([py, os.path.join(sk, "run_all.py"), "--fixtures", "--branch", "demo-r"],
                    tmp, env_lines=gh_env, sk=sk)
    stage("init: run_all --fixtures (github, no checkout needed)",
          code == 0 and "mode     : github" in out)

    code, out = run([py, os.path.join(sk, "workspace.py"), "fetch", REL_FILE,
                     "--branch", "demo-r", "--fixtures"], tmp)
    stage("solve: workspace fetch (checkout untouched)", code == 0)

    edited = os.path.join(tmp, "SONAR_ISSUES", "demo-r", "_workspace", "edited",
                          REL_FILE.replace("/", os.sep))
    text = open(edited, encoding="utf-8").read()
    open(edited, "w", encoding="utf-8", newline="").write(
        text.replace("private TranslateService translateService;", "", 1))
    code, out = run([py, os.path.join(sk, "workspace.py"), "diff", "--branch", "demo-r",
                     "--fixtures"], tmp)
    stage("guard: changes.patch rebuilt lists the file",
          code == 0 and "1 file(s) changed" in out)

    orig_root = os.path.join(tmp, "patch-check")
    shutil.copytree(os.path.join(tmp, "SONAR_ISSUES", "demo-r", "_workspace", "orig"),
                    orig_root)
    run(["git", "init", "-q"], orig_root)
    code, out = run(["git", "apply", "--check",
                     os.path.join(tmp, "SONAR_ISSUES", "demo-r", "changes.patch")],
                    orig_root)
    stage("patch: git apply --check accepts changes.patch", code == 0, out.strip())

    branch_dir = os.path.join(tmp, "SONAR_ISSUES", "demo-r")
    folder = next(d for d in os.listdir(branch_dir) if d.startswith("001_"))
    with open(os.path.join(branch_dir, folder, "resolution.json"), "w", encoding="utf-8") as f:
        json.dump({"status": "fixed", "reason": "removed unused field",
                   "filesChanged": [REL_FILE], "testsRun": [], "mode": "github",
                   "workspaceFiles": [REL_FILE], "patchFile": "changes.patch"}, f)
    code, out = run([py, os.path.join(sk, "publish.py"), "--dry-run", "--branch", "demo-r",
                     "--fixtures"], tmp)
    stage("publish: --dry-run preview (files + issue covered)",
          code == 0 and "files to push : 1" in out and "issues covered: 1" in out)

    code, out = run([py, os.path.join(sk, "verify.py"), "--full", "--branch", "demo-r",
                     "--fixtures"], tmp)
    stage("verify: exit 4 by design in github mode", code == 4)

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nE2E DEMO: all {len(PASSED)} stages passed - the whole journey works.\n")


if __name__ == "__main__":
    main()

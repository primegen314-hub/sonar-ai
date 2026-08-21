"""Run the whole sonar-issues pipeline: s01 auth -> s02 fetch -> s03 rules
-> s04 folders -> s05 context -> s06 summary. Stops at the first failing step.

Usage:
  python run_all.py "sonar.example.com/project/issues?issueStatus=OPEN%2CCONFIRMED&newCodePeriod=true&id=<projectKey>"
  python run_all.py --fixtures --branch demo-branch     (offline demo)
"""
import os
import subprocess
import sys

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
STEPS = [
    "s01_setup_auth.py",
    "s02_fetch_issues.py",
    "s03_fetch_rules.py",
    "s04_build_folders.py",
    "s05_build_context.py",
    "s06_summarize.py",
]


def main():
    forwarded = sys.argv[1:]
    if "--help" in forwarded or "-h" in forwarded:
        print(__doc__)
        print("Arguments are forwarded to every step: [url] [--branch NAME] [--fixtures]")
        return
    for step in STEPS:
        script = os.path.join(SKILL_DIR, "steps", step)
        print(f"\n=== {step} " + "=" * max(0, 60 - len(step)), flush=True)
        result = subprocess.run([sys.executable, script] + forwarded)
        if result.returncode != 0:
            print(f"\nPipeline stopped: {step} exited with {result.returncode}", file=sys.stderr)
            sys.exit(result.returncode)
    print("\nPipeline complete.")


if __name__ == "__main__":
    main()

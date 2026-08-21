"""Shared helpers for the sonar-issues pipeline. Python stdlib only."""
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR_NAME = "SONAR_ISSUES"
RAW_DIR_NAME = "_raw"

RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
RESET = "\033[0m"


def init_console():
    """Force UTF-8 stdout/stderr so issue messages with unicode print safely on Windows,
    and enable ANSI colors on Windows terminals."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if sys.platform == "win32":
        os.system("")  # enables VT escape processing in cmd/PowerShell


def _paint(color, text):
    if os.environ.get("NO_COLOR"):
        return text
    return f"{color}{text}{RESET}"


def fail(message, code=1):
    print(_paint(RED, f"ERROR: {message}"), file=sys.stderr)
    sys.exit(code)


def warn(message):
    print(_paint(YELLOW, f"WARNING: {message}"), file=sys.stderr)


def ok(message):
    print(_paint(GREEN, message))

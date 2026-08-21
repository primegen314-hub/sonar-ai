"""Load and update .env files without external packages.

The pipeline's .env lives INSIDE the skill folder (next to run_all.py), never at
the repository root - a host project may have its own root .env and the two must
not interfere.
"""
import os

ENV_FILENAME = ".env"


def env_path(skill_dir):
    return os.path.join(skill_dir, ENV_FILENAME)


def find_env_file(skill_dir):
    path = env_path(skill_dir)
    return path if os.path.isfile(path) else None


def _parse_line(line):
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, _, value = stripped.partition("=")
    key = key.strip()
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        value = value[1:-1]
    return key, value


def load_env(path):
    values = {}
    if not path or not os.path.isfile(path):
        return values
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            parsed = _parse_line(line)
            if parsed:
                values[parsed[0]] = parsed[1]
    return values


def update_env(path, key, value):
    """Set key=value in the .env file, preserving all other lines. Creates the file if missing."""
    lines = []
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
    replaced = False
    for i, line in enumerate(lines):
        parsed = _parse_line(line)
        if parsed and parsed[0] == key:
            lines[i] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

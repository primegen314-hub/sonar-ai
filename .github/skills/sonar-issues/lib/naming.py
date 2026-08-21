"""Windows-safe folder naming for branch refs and issue folders."""
import re

_INVALID = re.compile(r'[<>:"/\\|?*\s]+')


def sanitize(text, max_len=80):
    cleaned = _INVALID.sub("_", text.strip())
    cleaned = re.sub(r"_{2,}", "_", cleaned).strip("_.")
    return cleaned[:max_len].rstrip("_.") or "unnamed"


def branch_folder(branch_ref):
    return sanitize(branch_ref, max_len=100)


def rule_id(rule_key):
    """'java:S1481' -> 'S1481' (falls back to the whole key when there is no repo prefix)."""
    return rule_key.split(":", 1)[1] if ":" in rule_key else rule_key


def issue_folder(seq, rule_key, file_path, line):
    base_name = file_path.replace("\\", "/").rsplit("/", 1)[-1] if file_path else "project"
    line_part = f"L{line}" if line else "L0"
    name = f"{seq:03d}_{sanitize(rule_id(rule_key), 20)}_{sanitize(base_name, 40)}_{line_part}"
    return name[:80]

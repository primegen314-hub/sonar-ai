"""Discover the host project's AI/coding-standards instruction files.

Pure filesystem checks against the well-known locations of every major agentic
tool, so the solving AI never spends tokens hunting for them - it gets a ready
list and reads only what exists (and skips whatever its host already auto-loads).
"""
import glob
import os

# (relative path or glob, description)
_KNOWN = [
    ("CLAUDE.md", "Claude Code project rules"),
    ("CLAUDE.local.md", "Claude Code local rules"),
    (".claude/rules/*.md", "Claude Code rule files"),
    (".github/copilot-instructions.md", "Copilot repo instructions"),
    (".github/instructions/*.instructions.md", "Copilot path-scoped instructions"),
    ("instructions.md", "project instructions (root-level)"),
    ("AGENTS.md", "agent instructions (open standard)"),
    (".cursorrules", "Cursor rules"),
    (".cursor/rules/*.mdc", "Cursor rule files"),
    ("GEMINI.md", "Gemini CLI rules"),
    (".windsurfrules", "Windsurf rules"),
]


def find_instruction_files(repo_root):
    """Existing instruction files, repo-relative with forward slashes."""
    found = []
    for pattern, _ in _KNOWN:
        full = os.path.join(repo_root, pattern.replace("/", os.sep))
        matches = glob.glob(full) if any(c in pattern for c in "*?") else \
            ([full] if os.path.isfile(full) else [])
        for path in sorted(matches):
            rel = os.path.relpath(path, repo_root).replace(os.sep, "/")
            if rel not in found:
                found.append(rel)
    return found

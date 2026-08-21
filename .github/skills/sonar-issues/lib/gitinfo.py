"""Local git queries via subprocess. Everything degrades to None/[] when git or the repo is absent."""
import os
import subprocess


def _git(args, cwd=None):
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _git_visible(args, cwd=None, timeout=120):
    """Run git showing its combined output. Returns (returncode, output_text).

    Unlike _git(), failures are NOT swallowed - set_mode.py needs the real
    exit code and stderr of `git checkout` / `git pull` to show the user.
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except OSError as e:
        return 127, f"git not runnable: {e}"
    except subprocess.TimeoutExpired:
        return 124, f"git {' '.join(args)} timed out"
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output.strip()


def checkout(branch, cwd=None):
    """git checkout <branch> -> (returncode, output)."""
    return _git_visible(["checkout", branch], cwd=cwd)


def pull(cwd=None):
    """git pull -> (returncode, output)."""
    return _git_visible(["pull"], cwd=cwd)


def repo_root(cwd=None):
    return _git(["rev-parse", "--show-toplevel"], cwd=cwd)


def current_branch(cwd=None):
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    if branch in (None, "HEAD"):  # detached HEAD gives "HEAD"
        return None
    return branch


def local_head(cwd=None):
    return _git(["rev-parse", "HEAD"], cwd=cwd)


def remote_head(branch, cwd=None):
    """Tip SHA of the branch on origin (one lightweight network call using the
    user's normal git credentials), or None when unreachable/missing."""
    out = _git(["ls-remote", "origin", f"refs/heads/{branch}"], cwd=cwd)
    if not out:
        return None
    return out.split()[0]


def is_ancestor(ancestor, descendant, cwd=None):
    """True/False, or None when git can't answer (unknown SHA etc.)."""
    try:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=cwd, capture_output=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    return None


def remote_org_repo(cwd=None):
    """('org', 'repo') parsed from origin's URL (https or ssh), or (None, None)."""
    url = _git(["remote", "get-url", "origin"], cwd=cwd)
    if not url:
        return None, None
    import re
    m = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$", url.strip())
    if not m:
        return None, None
    return m.group(1), m.group(2)


def ls_files(root):
    """All tracked+untracked (non-ignored) files, repo-relative with forward slashes."""
    out = _git(["ls-files", "--cached", "--others", "--exclude-standard"], cwd=root)
    if out is None:
        return None
    return [line for line in out.splitlines() if line]


def referencing_files(symbol, root, exclude=(), limit=20):
    """Files whose text references `symbol` as a whole word (reverse-dependency
    heuristic: who uses this class). Returns [{'file', 'references'}] ranked by count."""
    out = _git(["grep", "-c", "-w", "--", symbol], cwd=root)
    if not out:
        return []
    excluded = set(exclude)
    hits = []
    for line in out.splitlines():
        path, _, count = line.rpartition(":")
        if not path or path in excluded:
            continue
        try:
            hits.append({"file": path, "references": int(count)})
        except ValueError:
            continue
    hits.sort(key=lambda h: (-h["references"], h["file"]))
    return hits[:limit]


def co_changed_files(rel_path, root, max_commits=20, limit=10):
    """Files most often changed in the same commits as rel_path (excluding itself)."""
    out = _git(
        ["log", "-n", str(max_commits), "--name-only", "--pretty=format:%H", "--", rel_path],
        cwd=root,
    )
    if not out:
        return []
    counts = {}
    for line in out.splitlines():
        line = line.strip()
        if not line or len(line) == 40 and all(c in "0123456789abcdef" for c in line):
            continue
        if line == rel_path:
            continue
        counts[line] = counts.get(line, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"file": f, "coChanges": n} for f, n in ranked[:limit]]

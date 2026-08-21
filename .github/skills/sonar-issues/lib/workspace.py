"""GitHub-mode scratch workspace: fixes are made on copies of files fetched
from the GitHub API, never on the local checkout.

Layout (whole SONAR_ISSUES/ tree is git-ignored):
  SONAR_ISSUES/<branchRef>/_workspace/
    workspace.json      manifest: base commit + per-file blob SHAs
    orig/<path>         pristine copy as fetched from GitHub (byte-exact)
    edited/<path>       the copy fixes are applied to
  SONAR_ISSUES/<branchRef>/changes.patch   cumulative unified diff (orig vs edited)

The patch is a review artifact - it is regenerated wholesale after every fix
(idempotent even when several issues touch one file) and is `git apply`
compatible. publish.py commits the edited/ file contents directly.
"""
import datetime
import difflib
import hashlib
import os
import shutil

from . import fail
from . import config

MANIFEST_NAME = "workspace.json"
ORIG_DIR = "orig"
EDITED_DIR = "edited"


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def git_blob_sha(content_bytes):
    """SHA-1 exactly as git computes it for a blob."""
    header = f"blob {len(content_bytes)}\0".encode("ascii")
    return hashlib.sha1(header + content_bytes).hexdigest()


def manifest_path(settings):
    return os.path.join(settings.workspace_dir, MANIFEST_NAME)


def load_manifest(settings):
    path = manifest_path(settings)
    if not os.path.isfile(path):
        return None
    return config.load_json(path)


def save_manifest(settings, manifest):
    config.dump_json(manifest_path(settings), manifest)


def orig_path(settings, rel_path):
    return os.path.join(settings.workspace_dir, ORIG_DIR, rel_path.replace("/", os.sep))


def edited_path(settings, rel_path):
    return os.path.join(settings.workspace_dir, EDITED_DIR, rel_path.replace("/", os.sep))


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def _write_bytes(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)


def fetch_file(settings, rel_path):
    """Ensure rel_path exists in the workspace; returns the edited/ path.

    First fetch of a file downloads it byte-exact from GitHub (or copies the
    bundled fixture in --fixtures mode) into BOTH orig/ and edited/. An already
    fetched file is never re-downloaded and an existing edited/ copy is NEVER
    overwritten - in-progress fixes survive.
    """
    rel_path = rel_path.replace("\\", "/").lstrip("/")
    manifest = load_manifest(settings)
    if manifest is None:
        manifest = {"branchRef": settings.branch, "githubBranch": settings.github_branch,
                    "baseCommitSha": None, "createdAt": _now(), "files": {}}
        if settings.fixtures:
            manifest["baseCommitSha"] = "fixtures"
        else:
            manifest["baseCommitSha"] = settings.github_client().get_branch_sha(settings.github_branch)

    if rel_path in manifest["files"] and os.path.isfile(edited_path(settings, rel_path)):
        return edited_path(settings, rel_path)

    if settings.fixtures:
        src = os.path.join(config.FIXTURES_DIR, "sample_src", rel_path.replace("/", os.sep))
        if not os.path.isfile(src):
            fail(f"No fixture source for '{rel_path}' (looked in fixtures/sample_src/)")
        content = _read_bytes(src)
    else:
        content, _ = settings.github_client().get_file_blob(rel_path, ref=settings.github_branch)
        if content is None:
            fail(f"'{rel_path}' not found on GitHub branch '{settings.github_branch}' "
                 f"({settings.github_org}/{settings.github_repo})")

    _write_bytes(orig_path(settings, rel_path), content)
    if not os.path.isfile(edited_path(settings, rel_path)):
        _write_bytes(edited_path(settings, rel_path), content)
    manifest["files"][rel_path] = {"blobSha": git_blob_sha(content), "fetchedAt": _now()}
    save_manifest(settings, manifest)
    return edited_path(settings, rel_path)


def _all_workspace_paths(settings):
    """Every repo-relative path present under edited/ (covers brand-new files
    a fix created without fetching)."""
    root = os.path.join(settings.workspace_dir, EDITED_DIR)
    paths = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            paths.append(os.path.relpath(full, root).replace(os.sep, "/"))
    return sorted(paths)


def changed_files(settings):
    """Repo-relative paths whose edited/ copy differs from orig/ (a missing
    orig/ counterpart means the fix created a new file)."""
    if not os.path.isdir(settings.workspace_dir):
        return []
    changed = []
    for rel in _all_workspace_paths(settings):
        opath, epath = orig_path(settings, rel), edited_path(settings, rel)
        if not os.path.isfile(opath):
            changed.append(rel)
        elif _read_bytes(opath) != _read_bytes(epath):
            changed.append(rel)
    return changed


def is_dirty(settings):
    return bool(changed_files(settings))


def _lines_for_diff(content_bytes):
    text = content_bytes.decode("utf-8", errors="surrogateescape")
    return text.splitlines(keepends=True)


def _emit(out, diff_lines):
    """Write difflib output adding git's 'No newline at end of file' markers."""
    for line in diff_lines:
        if line.endswith("\n"):
            out.append(line)
        else:
            out.append(line + "\n")
            out.append("\\ No newline at end of file\n")


def regenerate_patch(settings):
    """Rebuild changes.patch from scratch (all changed files, sorted).
    Returns the list of changed files; deletes the patch when nothing changed."""
    changed = changed_files(settings)
    if not changed:
        if os.path.isfile(settings.patch_path):
            os.remove(settings.patch_path)
        return changed
    out = []
    for rel in changed:
        opath = orig_path(settings, rel)
        orig_lines = _lines_for_diff(_read_bytes(opath)) if os.path.isfile(opath) else []
        edited_lines = _lines_for_diff(_read_bytes(edited_path(settings, rel)))
        fromfile = f"a/{rel}" if os.path.isfile(opath) else "/dev/null"
        out.append(f"diff --git a/{rel} b/{rel}\n")
        if fromfile == "/dev/null":
            out.append("new file mode 100644\n")
        _emit(out, difflib.unified_diff(orig_lines, edited_lines,
                                        fromfile=fromfile, tofile=f"b/{rel}"))
    with open(settings.patch_path, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
        f.write("".join(out))
    return changed


def diffstat(settings):
    """[{'file', 'added', 'removed', 'new'}] for every changed file."""
    stats = []
    for rel in changed_files(settings):
        opath = orig_path(settings, rel)
        orig_lines = _lines_for_diff(_read_bytes(opath)) if os.path.isfile(opath) else []
        edited_lines = _lines_for_diff(_read_bytes(edited_path(settings, rel)))
        added = removed = 0
        for line in difflib.unified_diff(orig_lines, edited_lines, fromfile="a", tofile="b"):
            if line.startswith("+") and not line.startswith("+++"):
                added += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed += 1
        stats.append({"file": rel, "added": added, "removed": removed,
                      "new": not os.path.isfile(opath)})
    return stats


def rebaseline(settings):
    """After a successful publish: orig/ <- edited/ so the workspace is clean
    again (the published state IS the new baseline); the patch empties away."""
    manifest = load_manifest(settings)
    for rel in _all_workspace_paths(settings):
        content = _read_bytes(edited_path(settings, rel))
        _write_bytes(orig_path(settings, rel), content)
        if manifest and rel in manifest.get("files", {}):
            manifest["files"][rel]["blobSha"] = git_blob_sha(content)
        elif manifest is not None:
            manifest["files"][rel] = {"blobSha": git_blob_sha(content), "fetchedAt": _now()}
    if manifest is not None:
        save_manifest(settings, manifest)
    regenerate_patch(settings)


def discard(settings):
    """Delete the workspace and the patch entirely."""
    if os.path.isdir(settings.workspace_dir):
        shutil.rmtree(settings.workspace_dir)
    if os.path.isfile(settings.patch_path):
        os.remove(settings.patch_path)

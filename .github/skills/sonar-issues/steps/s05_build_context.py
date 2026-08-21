"""Step 05 - Write context.json per issue: the starting points an AI (or human)
needs to fix it — the issue file, its tests (naming conventions), and files
that historically change together with it (git log).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import init_console, RAW_DIR_NAME
from lib import config, gitinfo
from lib.effort import complexity_score, tier_for_score

LANG_BY_EXT = {
    ".java": "java", ".ts": "typescript", ".tsx": "typescript", ".js": "javascript",
    ".jsx": "javascript", ".py": "python", ".cs": "csharp", ".kt": "kotlin",
    ".go": "go", ".html": "html", ".css": "css", ".scss": "css", ".xml": "xml",
}
SNIPPET_PAD = 8


def test_name_candidates(stem):
    s = stem.lower()
    return {
        f"{s}test", f"{s}tests", f"test{s}", f"test_{s}", f"{s}_test",
        f"{s}.spec", f"{s}.test",
    }


def is_test_file(path):
    """True when the file itself is a test (issue inside a unit test)."""
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    stem = name.rsplit(".", 1)[0].lower()
    return (stem.startswith("test") or stem.endswith(("test", "tests", "_test", ".spec", ".test"))
            or "/test/" in path.replace("\\", "/").lower())


def find_test_files(all_files, issue_file):
    base = issue_file.replace("\\", "/").rsplit("/", 1)[-1]
    stem = base.rsplit(".", 1)[0]
    candidates = test_name_candidates(stem)
    matches = []
    for path in all_files:
        name = path.replace("\\", "/").rsplit("/", 1)[-1]
        name_stem = name.rsplit(".", 1)[0].lower()
        # "foo.spec.ts" -> stem "foo.spec"; plain "FooTest.java" -> "footest"
        if name_stem in candidates:
            matches.append(path)
    return sorted(matches)


def find_used_by(settings, issue_file, all_files, limit=20):
    """Reverse dependencies: files that reference the issue file's class/module name
    as a whole word - i.e. who would be affected if this file changes."""
    base = issue_file.replace("\\", "/").rsplit("/", 1)[-1]
    symbol = base.rsplit(".", 1)[0]
    if not symbol:
        return []
    if settings.fixtures:
        import re
        root = os.path.join(config.FIXTURES_DIR, "sample_src")
        pattern = re.compile(r"\b" + re.escape(symbol) + r"\b")
        hits = []
        for rel in all_files:
            if rel == issue_file:
                continue
            path = os.path.join(root, rel.replace("/", os.sep))
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    count = len(pattern.findall(f.read()))
            except OSError:
                continue
            if count:
                hits.append({"file": rel, "references": count})
        hits.sort(key=lambda h: (-h["references"], h["file"]))
        return hits[:limit]
    return gitinfo.referencing_files(symbol, settings.repo_root,
                                     exclude=(issue_file,), limit=limit)


def list_project_files(settings, github):
    if settings.fixtures:
        root = os.path.join(config.FIXTURES_DIR, "sample_src")
        found = []
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                rel = os.path.relpath(os.path.join(dirpath, fn), root)
                found.append(rel.replace(os.sep, "/"))
        return found
    if github is not None:
        paths, truncated = github.list_tree(settings.github_branch)
        if truncated:
            from lib import warn
            warn("GitHub tree listing was truncated (very large repo) - "
                 "test-file discovery may be incomplete.")
        return paths
    return gitinfo.ls_files(settings.repo_root) or []


def main():
    init_console()
    args = config.build_parser(__doc__).parse_args()
    settings = config.Settings(args)
    meta = settings.load_meta()

    github = None
    if meta.get("contextSource") == "github" and not settings.fixtures:
        github = settings.github_client()

    all_files = list_project_files(settings, github)
    print(f"[s05] {len(all_files)} project files scanned for related tests"
          + (" (via GitHub API)" if github else ""))

    folders = sorted(
        d for d in os.listdir(settings.branch_dir)
        if d != RAW_DIR_NAME and os.path.isdir(os.path.join(settings.branch_dir, d))
    )
    for folder in folders:
        folder_path = os.path.join(settings.branch_dir, folder)
        issue = config.load_json(os.path.join(folder_path, "issue.json"))
        issue_file = issue["file"]
        ext = "." + issue_file.rsplit(".", 1)[-1].lower() if "." in issue_file else ""
        text_range = issue.get("textRange") or {}
        start = text_range.get("startLine") or issue.get("line")
        end = text_range.get("endLine") or start

        test_files = find_test_files(all_files, issue_file)
        if is_test_file(issue_file) and issue_file not in test_files:
            # the issue lives inside a test: that test itself must run after the fix
            test_files.insert(0, issue_file)
        if github is not None:
            # no local git in github mode: these need `git grep` / `git log`
            co_changed = []
            used_by = []
        else:
            co_changed = [] if settings.fixtures else gitinfo.co_changed_files(issue_file, settings.repo_root)
            used_by = find_used_by(settings, issue_file, all_files)

        context = {
            "issueKey": issue["key"],
            "issueFile": issue_file,
            "language": issue["rule"].get("lang") or LANG_BY_EXT.get(ext, ""),
            "snippetRange": {
                "startLine": max(1, (start or 1) - SNIPPET_PAD),
                "endLine": (end or 1) + SNIPPET_PAD,
                "issueStartLine": start,
                "issueEndLine": end,
            } if start else None,
            "testFiles": test_files,
            "usedBy": used_by,
            "coChangedFiles": co_changed,
            "relatedFiles": sorted({issue_file, *test_files,
                                    *(u["file"] for u in used_by),
                                    *(c["file"] for c in co_changed)}),
            "branchRef": meta["branchRef"],
            "repoRoot": settings.repo_root,
            "contextSource": meta.get("contextSource", "local"),
            "notesForSolver": [
                "Fix must keep behavior identical unless the Sonar message says otherwise.",
                "If testFiles is non-empty, run those tests after the fix.",
                "usedBy = files that reference this class (impact analysis): if the fix changes the class's API/signature/visibility, check every usedBy file.",
                "coChangedFiles are files that historically change together with the issue file - check them for ripple effects.",
            ] + ([
                "contextSource=github: usedBy and coChangedFiles are unavailable (they need local git history) - do the impact analysis manually before wide-reaching changes.",
            ] if github is not None else []),
        }
        config.dump_json(os.path.join(folder_path, "context.json"), context)

        # composite AI-effort estimate - now that the context signals exist.
        # Deterministic and total: computes even when Sonar gave no estimate.
        score, factors = complexity_score(issue, context)
        issue["complexityScore"] = score
        issue["aiEffort"] = tier_for_score(score)
        issue["aiEffortReason"] = ", ".join(factors) if factors else "simple, low-risk fix"
        config.dump_json(os.path.join(folder_path, "issue.json"), issue)

        print(f"[s05]   {folder}: {len(test_files)} tests, {len(used_by)} used-by, "
              f"{len(co_changed)} co-changed -> ai effort {issue['aiEffort']} (score {score})")

    print("[s05] done")


if __name__ == "__main__":
    main()

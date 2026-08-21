"""Step 04 - Materialize one folder per issue with issue.json (machine contract)
and issue.md (human-readable, mirrors the SonarQube web presentation).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import init_console, RAW_DIR_NAME
from lib import config, naming
from lib.htmltext import html_to_markdown

SNIPPET_PAD = 8

SEVERITY_ICON = {"BLOCKER": "🔴", "CRITICAL": "🟠", "MAJOR": "🟡", "MINOR": "🔵", "INFO": "⚪"}


def component_paths(issues_data):
    """Map component key -> repo-relative file path."""
    paths = {}
    for comp in issues_data.get("components", []):
        if comp.get("path"):
            paths[comp["key"]] = comp["path"]
    return paths


def resolve_source(settings, client, github, component_key, rel_path, branch):
    """Return the file's text (or None).

    local mode : local checkout first, Sonar API fallback.
    github mode: GitHub API first (the checked-out branch is irrelevant),
                 Sonar API fallback.
    """
    if settings.fixtures:
        local = os.path.join(config.FIXTURES_DIR, "sample_src", rel_path.replace("/", os.sep))
        if os.path.isfile(local):
            with open(local, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        return None
    if github is not None:
        text = github.get_file(rel_path, ref=settings.github_branch)
        if text is not None:
            return text
        return client.source_raw(component_key, branch)
    local = os.path.join(settings.repo_root, rel_path.replace("/", os.sep))
    if os.path.isfile(local):
        with open(local, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    return client.source_raw(component_key, branch)


def build_snippet(source_text, start_line, end_line):
    """Fenced snippet around the flagged range, '>>>' marking flagged lines."""
    if not source_text or not start_line:
        return None
    lines = source_text.splitlines()
    end_line = end_line or start_line
    lo = max(1, start_line - SNIPPET_PAD)
    hi = min(len(lines), end_line + SNIPPET_PAD)
    out = []
    for n in range(lo, hi + 1):
        marker = ">>>" if start_line <= n <= end_line else "   "
        out.append(f"{marker} {n:4d} | {lines[n - 1]}")
    return "\n".join(out)


def rule_sections(rule):
    """{'why': md, 'how': md} from descriptionSections (new) or htmlDesc (old)."""
    sections = {}
    for sec in rule.get("descriptionSections", []):
        sections.setdefault(sec.get("key"), sec.get("content", ""))
    why_html = sections.get("root_cause") or sections.get("default") or sections.get("introduction")
    how_html = sections.get("how_to_fix")
    if not why_html and rule.get("htmlDesc"):
        why_html = rule["htmlDesc"]
    return {
        "why": html_to_markdown(why_html or ""),
        "how": html_to_markdown(how_html or ""),
    }


# Sonar rule-language keys and file extensions, normalized to one vocabulary
SONAR_LANG = {"js": "javascript", "ts": "typescript", "py": "python", "cs": "csharp",
              "web": "html", "kotlin": "kotlin", "java": "java", "go": "go",
              "css": "css", "xml": "xml", "php": "php"}
EXT_LANG = {".java": "java", ".ts": "typescript", ".tsx": "typescript",
            ".js": "javascript", ".jsx": "javascript", ".py": "python",
            ".cs": "csharp", ".kt": "kotlin", ".go": "go", ".html": "html",
            ".vue": "html", ".css": "css", ".scss": "css", ".xml": "xml", ".php": "php"}


def recommend_fix(rule, rel_path, sections):
    """('sonar'|'ai', reason) - deterministic, so the solving skills spend zero
    tokens deciding which option to recommend to the user.

    'ai' when the rule's language doesn't match the file (e.g. a generic rule
    flagged in frontend code - Sonar's canned fix may not apply) or when the
    rule ships no compliant example; 'sonar' otherwise.
    """
    ext = "." + rel_path.rsplit(".", 1)[-1].lower() if "." in rel_path else ""
    file_lang = EXT_LANG.get(ext)
    rule_lang = SONAR_LANG.get(rule.get("lang", ""), rule.get("lang") or None)
    if rule_lang and file_lang and rule_lang != file_lang:
        return "ai", (f"rule targets {rule_lang} but the file is {file_lang} - "
                      "Sonar's generic guidance may not fit this app; prefer an AI fix tailored to the code")
    if not sections["how"]:
        return "ai", "the rule ships no compliant-solution example - AI must derive the fix from the message"
    return "sonar", "the rule's compliant example matches this file's language and can be applied directly"


def sonar_deep_link(host, project, branch, issue_key):
    import urllib.parse
    params = {"id": project, "open": issue_key}
    if branch:
        params["branch"] = branch
    return f"{host}/project/issues?{urllib.parse.urlencode(params)}"


def render_issue_md(record, snippet, sections):
    rule = record["rule"]
    icon = SEVERITY_ICON.get(record.get("severity", ""), "")
    lines = [
        f"# {icon} {rule['id']}: {record['message']}".replace("#  ", "# "),
        "",
        f"- **Rule**: {rule['key']} — {rule.get('name', '')}",
        f"- **Type**: {record.get('type', '')} | **Severity**: {icon} {record.get('severity', '')}".rstrip()
        + f" | **Effort**: {record.get('effort') or '-'}",
        f"- **Status**: {record.get('status', '')} | **Branch**: {record['branchRef']}",
        f"- **Sonar link**: {record['sonarUrl']}",
        "",
        "🛠️ **Solve this issue** — paste this into your AI chat. One-click copy: open this"
        " file in Markdown preview (VS Code: Ctrl+Shift+V) or on GitHub — the block below"
        " shows a copy button on hover:",
        "",
        "```",
        f"/sonar-issue-pick {record['folder']} --branch {record['branchRef']}",
        "```",
        "",
        "## Where is the issue",
        "",
        f"`{record['file']}` — line {record.get('line') or '(file-level)'}",
        "",
    ]
    if snippet:
        lines += ["```", snippet, "```", ""]
    lines += [
        "> **Sonar message:** " + record["message"],
        "",
        "## Why is this an issue",
        "",
        sections["why"] or "_No rule description available._",
        "",
    ]
    lines += ["## Suggested fix", "", f"**Sonar says:** {record['message']}", ""]
    if sections["how"]:
        lines += ["**Rule guidance — how can I fix it?**", "", sections["how"], ""]
    return "\n".join(lines)


def main():
    init_console()
    args = config.build_parser(__doc__).parse_args()
    settings = config.Settings(args)
    meta = settings.load_meta()

    issues_data = config.load_json(os.path.join(settings.raw_dir, "issues.json"))
    rules = config.load_json(os.path.join(settings.raw_dir, "rules.json"))
    paths = component_paths(issues_data)
    client = settings.sonar_client()
    github = None
    if meta.get("contextSource") == "github" and not settings.fixtures:
        github = settings.github_client()

    stash_path = os.path.join(settings.raw_dir, "resolutions.json")
    resolutions = config.load_json(stash_path) if os.path.isfile(stash_path) else {}
    restored = 0

    def sort_key(issue):
        comp = issue.get("component", "")
        rel = paths.get(comp, comp)
        return (rel, issue.get("line") or 0, issue.get("key", ""))

    issues = sorted(issues_data.get("issues", []), key=sort_key)
    print(f"[s04] building {len(issues)} issue folders under {settings.branch_dir}")

    for seq, issue in enumerate(issues, start=1):
        comp_key = issue.get("component", "")
        rel_path = paths.get(comp_key) or (comp_key.split(":", 1)[1] if ":" in comp_key else comp_key)
        text_range = issue.get("textRange") or {}
        line = issue.get("line") or text_range.get("startLine")
        rule_key = issue.get("rule", "")
        rule = rules.get(rule_key, {})

        folder = naming.issue_folder(seq, rule_key, rel_path, line)
        folder_path = os.path.join(settings.branch_dir, folder)
        os.makedirs(folder_path, exist_ok=True)

        sections = rule_sections(rule)
        recommended, rec_reason = recommend_fix(rule, rel_path, sections)
        record = {
            "seq": seq,
            "folder": folder,
            "key": issue.get("key"),
            "rule": {
                "key": rule_key,
                "id": naming.rule_id(rule_key),
                "name": rule.get("name") or "",
                "lang": rule.get("lang") or "",
            },
            "type": issue.get("type"),
            "severity": issue.get("severity"),
            "cleanCodeAttribute": issue.get("cleanCodeAttribute"),
            "impacts": issue.get("impacts", []),
            "message": issue.get("message", ""),
            "file": rel_path,
            "line": line,
            "textRange": text_range,
            "linesAffected": (text_range.get("endLine", line) or 0) - (text_range.get("startLine", line) or 0) + 1
                             if line else None,
            "effort": issue.get("effort") or issue.get("debt"),
            "status": issue.get("issueStatus") or issue.get("status"),
            "tags": issue.get("tags", []),
            "creationDate": issue.get("creationDate"),
            "branchRef": meta["branchRef"],
            "project": meta["project"],
            "sonarUrl": sonar_deep_link(meta["host"], meta["project"], meta["branchRef"], issue.get("key")),
            "recommended": recommended,
            "recommendedReason": rec_reason,
            # final value computed by s05 from the composite complexity score
            # (needs context.json's usedBy/coChangedFiles/testFiles)
            "aiEffort": None,
        }
        config.dump_json(os.path.join(folder_path, "issue.json"), record)
        if record["key"] in resolutions:
            config.dump_json(os.path.join(folder_path, "resolution.json"), resolutions[record["key"]])
            restored += 1

        source_text = resolve_source(settings, client, github, comp_key, rel_path, meta["branchRef"])
        snippet = build_snippet(source_text, text_range.get("startLine") or line,
                                text_range.get("endLine") or line)
        md = render_issue_md(record, snippet, sections)
        with open(os.path.join(folder_path, "issue.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(md)
        print(f"[s04]   {folder}")

    if resolutions:
        print(f"[s04] restored {restored}/{len(resolutions)} stashed resolution(s) "
              f"(the rest belong to issues no longer reported)")
    print("[s04] done")


if __name__ == "__main__":
    main()

"""Deterministic AI-effort estimation: a composite complexity score per issue.

Sonar's remediation-effort minutes are kept only as a MINOR factor - Sonar easily
misjudges real fix complexity. The dominant signals are blast radius (usedBy),
change history (coChangedFiles), rule type/severity, whether a mechanical
compliant example exists, and whether tests cover the file. Everything is
computed here, in scripts, so the estimate ALWAYS exists (even when Sonar gives
no time estimate at all) and the skills spend zero tokens deriving it.

Tiers are ANALYSIS depth for the solving AI. No tier ever runs tests -
verification is a separate, user-invoked step (/sonar-verify):
  normal  minimal fix at the flagged lines
  high    + impact check of usedBy files, targeted skim of the relatedFiles
            relevant to this fix, edge cases
  max     + read the whole issue file and ALL related files in depth, weigh
            alternative fixes, extend the affected tests
  xMax    + adversarial self-review of the diff before recording the resolution
"""
import re

_UNIT_MINUTES = {"d": 8 * 60, "h": 60, "min": 1}  # Sonar work day = 8h

_TIERS = ("normal", "high", "max", "xMax")


def effort_minutes(effort):
    """'1h30min' -> 90; None/unparseable -> None."""
    if not effort:
        return None
    total = 0
    for value, unit in re.findall(r"(\d+)\s*(min|h|d)", effort):
        total += int(value) * _UNIT_MINUTES[unit]
    return total or None


def tier_for_score(score):
    """Composite complexity score -> tier: 0-1 normal, 2-3 high, 4-5 max, >=6 xMax."""
    if score <= 1:
        return "normal"
    if score <= 3:
        return "high"
    if score <= 5:
        return "max"
    return "xMax"


def complexity_score(entry, context):
    """(score, factors) for one issue.

    entry   = the issue.json dict (type, severity, effort, recommended)
    context = the issue's context.json dict (usedBy, coChangedFiles, testFiles);
              may be empty/None - the score still computes (never fails).
    """
    context = context or {}
    score = 0
    factors = []

    used_by = context.get("usedBy") or []
    if len(used_by) >= 3:
        score += 2
        factors.append(f"{len(used_by)} usedBy files (wide blast radius)")
    elif used_by:
        score += 1
        factors.append(f"{len(used_by)} usedBy file(s)")

    co_changed = context.get("coChangedFiles") or []
    if len(co_changed) >= 3:
        score += 1
        factors.append("historically co-changed with other files")

    issue_type = (entry.get("type") or "").upper()
    if issue_type == "VULNERABILITY":
        score += 2
        factors.append("VULNERABILITY")
    elif issue_type == "BUG":
        score += 1
        factors.append("BUG")

    if (entry.get("severity") or "").upper() in ("CRITICAL", "BLOCKER"):
        score += 1
        factors.append(entry["severity"])

    if entry.get("recommended") == "ai":
        score += 1
        factors.append("no mechanical compliant example")

    if not (context.get("testFiles") or []):
        score += 1
        factors.append("no tests covering the file")

    minutes = effort_minutes(entry.get("effort"))
    if minutes is not None and minutes > 30:
        score += 1
        factors.append(f"Sonar estimates {entry.get('effort')}")

    return score, factors


def ai_effort_for_issue(entry, context):
    """(tier, reason) for one issue from the composite complexity score."""
    score, factors = complexity_score(entry, context)
    reason = ", ".join(factors) if factors else "simple, low-risk fix"
    return tier_for_score(score), reason


def ai_effort_for_batch(scored):
    """(tier, reason) for a whole solving session.

    scored = list of (score, factors) tuples, one per issue. The batch tier
    comes from the MEAN score (same thresholds); the reason names the issue
    count and the most common contributing factors.
    """
    scored = [s for s in (scored or []) if s is not None]
    if not scored:
        return "normal", "no issues to estimate"
    scores = [s for s, _ in scored]
    avg = sum(scores) / len(scores)
    counts = {}
    for _, factors in scored:
        for factor in factors:
            counts[factor] = counts.get(factor, 0) + 1
    dominant = [f for f, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:2]]
    reason = f"mean complexity {avg:.1f} across {len(scores)} issue(s)"
    if dominant:
        reason += f"; dominant factors: {'; '.join(dominant)}"
    return tier_for_score(round(avg)), reason

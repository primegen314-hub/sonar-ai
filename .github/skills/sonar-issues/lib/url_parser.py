"""Parse a pasted SonarQube UI URL into pipeline parameters.

Example input (scheme optional):
  sonar.example.com/project/issues?issueStatus=OPEN%2CCONFIRMED&newCodePeriod=true&id=example_report-service
"""
import urllib.parse


def parse_sonar_url(raw):
    """Return a dict containing only the keys actually present in the URL:
    host, project, statuses (list), new_code (bool), branch.
    """
    raw = raw.strip()
    if "://" not in raw:
        raw = "https://" + raw
    parts = urllib.parse.urlsplit(raw)
    query = urllib.parse.parse_qs(parts.query)

    info = {}
    if parts.netloc:
        info["host"] = f"{parts.scheme}://{parts.netloc}"

    def first(*names):
        for name in names:
            if name in query and query[name]:
                return query[name][0]
        return None

    project = first("id", "projectKey")
    if project:
        info["project"] = project

    statuses = first("issueStatus", "issueStatuses", "statuses")
    if statuses:
        info["statuses"] = [s.strip().upper() for s in statuses.split(",") if s.strip()]

    new_code = first("newCodePeriod", "inNewCodePeriod", "sinceLeakPeriod")
    if new_code is not None:
        info["new_code"] = new_code.lower() == "true"

    branch = first("branch")
    if branch:
        info["branch"] = branch

    return info

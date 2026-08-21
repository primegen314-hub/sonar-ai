"""SonarQube Web API client (stdlib only) with an offline fixtures mode.

Auth: SONAR_TOKEN as Basic username with empty password (preferred),
falling back to LDAP user/password Basic auth.

Server-version handling: SonarQube >= 10.4 uses `issueStatuses` +
`inNewCodePeriod`; older servers use `statuses` + `sinceLeakPeriod`.
"""
import base64
import json
import os
import urllib.parse

from .http_client import HttpClient, HttpError

PAGE_SIZE = 500
API_RESULT_CAP = 10000


class SonarError(Exception):
    pass


class SonarClient:
    def __init__(self, host, token=None, user=None, password=None,
                 verify_ssl=True, fixtures_dir=None):
        self.host = (host or "").rstrip("/")
        self.token = token or None
        self.user = user or None
        self.password = password or None
        self.fixtures_dir = fixtures_dir
        self._http = None if fixtures_dir else HttpClient(verify_ssl=verify_ssl)
        self._version = None

    # ---- auth -------------------------------------------------------------
    def _auth_header(self, force_basic=False):
        if self.token and not force_basic:
            raw = f"{self.token}:"
        elif self.user is not None:
            raw = f"{self.user}:{self.password or ''}"
        else:
            raise SonarError("No Sonar credentials: set SONAR_TOKEN or SONAR_USER/SONAR_PASSWORD in .env")
        return {"Authorization": "Basic " + base64.b64encode(raw.encode("utf-8")).decode("ascii")}

    # ---- plumbing ---------------------------------------------------------
    def _get(self, path, params=None):
        url = f"{self.host}/{path}"
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        try:
            return self._http.request_json(url, headers=self._auth_header())
        except HttpError as e:
            raise SonarError(f"Sonar API {path} failed: HTTP {e.status}: {e.body[:500]}") from None

    def _get_text(self, path, params=None):
        url = f"{self.host}/{path}"
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        try:
            _, body = self._http.request(url, headers=self._auth_header())
            return body.decode("utf-8", errors="replace")
        except HttpError as e:
            raise SonarError(f"Sonar API {path} failed: HTTP {e.status}: {e.body[:500]}") from None

    def _fixture(self, name):
        path = os.path.join(self.fixtures_dir, name)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # ---- API calls --------------------------------------------------------
    def version(self):
        if self._version is None:
            if self.fixtures_dir:
                self._version = "10.6.0-fixtures"
            else:
                url = f"{self.host}/api/server/version"
                _, body = self._http.request(url, headers=self._auth_header())
                self._version = body.decode("ascii", errors="replace").strip()
        return self._version

    def is_modern(self):
        """True when the server supports issueStatuses/inNewCodePeriod (>= 10.4)."""
        try:
            parts = self.version().split(".")
            major, minor = int(parts[0]), int(parts[1].split("-")[0])
        except (ValueError, IndexError):
            return True  # unknown format: assume recent
        return (major, minor) >= (10, 4)

    def generate_token(self, name):
        """Mint a user token using LDAP basic auth. Returns the token string."""
        url = f"{self.host}/api/user_tokens/generate"
        try:
            data = self._http.request_json(
                url, method="POST",
                headers=self._auth_header(force_basic=True),
                form={"name": name},
            )
        except HttpError as e:
            raise SonarError(f"Token generation failed: HTTP {e.status}: {e.body[:500]}") from None
        token = data.get("token")
        if not token:
            raise SonarError(f"Token generation returned no token: {data}")
        return token

    def search_all_issues(self, project_key, branch=None, statuses=None, new_code_only=True):
        """All pages of api/issues/search. Returns {issues, components, rules, total, truncated}."""
        if self.fixtures_dir:
            data = self._fixture("issues_search.json")
            return {
                "issues": data.get("issues", []),
                "components": data.get("components", []),
                "rules": data.get("rules", []),
                "total": data.get("paging", {}).get("total", len(data.get("issues", []))),
                "truncated": False,
            }

        params = {"componentKeys": project_key, "ps": PAGE_SIZE, "additionalFields": "comments"}
        if branch:
            params["branch"] = branch
        status_list = list(statuses or [])
        if self.is_modern():
            if status_list:
                params["issueStatuses"] = ",".join(status_list)
            if new_code_only:
                params["inNewCodePeriod"] = "true"
        else:
            if status_list:
                # pre-10.4 status vocabulary: OPEN covers REOPENED separately
                if "OPEN" in status_list and "REOPENED" not in status_list:
                    status_list.append("REOPENED")
                params["statuses"] = ",".join(status_list)
            if new_code_only:
                params["sinceLeakPeriod"] = "true"

        issues, components, rules = [], {}, {}
        page = 1
        total = 0
        while True:
            params["p"] = page
            data = self._get("api/issues/search", params)
            total = data.get("paging", {}).get("total", data.get("total", 0))
            issues.extend(data.get("issues", []))
            for comp in data.get("components", []):
                components[comp.get("key")] = comp
            for rule in data.get("rules", []):
                rules[rule.get("key")] = rule
            fetched = page * PAGE_SIZE
            if fetched >= min(total, API_RESULT_CAP) or not data.get("issues"):
                break
            page += 1
        truncated = total > API_RESULT_CAP
        if truncated:
            print(f"WARNING: Sonar reports {total} issues but the API caps results at {API_RESULT_CAP}.")
        return {
            "issues": issues,
            "components": list(components.values()),
            "rules": list(rules.values()),
            "total": total,
            "truncated": truncated,
        }

    def branch_exists(self, project_key, branch):
        """True/False when the server can answer, None when it can't (endpoint
        missing on very old servers, or insufficient permissions) - callers
        must treat None as 'unknown', never as 'missing'."""
        if self.fixtures_dir:
            return True
        try:
            data = self._get("api/project_branches/list", {"project": project_key})
        except SonarError:
            return None
        branches = data.get("branches")
        if branches is None:
            return None
        return any(b.get("name") == branch for b in branches)

    def rule_show(self, rule_key):
        """api/rules/show -> the rule object (with descriptionSections / htmlDesc)."""
        if self.fixtures_dir:
            data = self._fixture("rules_show.json")
            entry = data.get(rule_key)
            if not entry:
                raise SonarError(f"No fixture rule for {rule_key}")
            return entry.get("rule", entry)
        data = self._get("api/rules/show", {"key": rule_key})
        return data.get("rule", {})

    def source_raw(self, component_key, branch=None):
        """Raw source of a file component, or None when unavailable."""
        if self.fixtures_dir:
            rel = component_key.split(":", 1)[1] if ":" in component_key else component_key
            path = os.path.join(self.fixtures_dir, "sample_src", rel.replace("/", os.sep))
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            return None
        try:
            return self._get_text("api/sources/raw", {"key": component_key, "branch": branch})
        except SonarError:
            return None

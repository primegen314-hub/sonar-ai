"""GitHub API client: read file contents / trees without a local checkout
(github mode extraction), plus the Git Data write endpoints used by publish.py
to commit workspace changes as ONE atomic multi-file commit
(blobs -> tree -> commit -> ref update).

GITHUB_API_URL in .env selects the API base (default https://api.github.com;
GitHub Enterprise uses https://<host>/api/v3).
"""
import base64
import urllib.parse

from .http_client import HttpClient, HttpError


class GitHubClient:
    def __init__(self, token, org, repo, api_base="https://api.github.com", verify_ssl=True):
        self.token = token
        self.org = org
        self.repo = repo
        self.api_base = api_base.rstrip("/")
        self._http = HttpClient(verify_ssl=verify_ssl)

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _repo_url(self, tail):
        return f"{self.api_base}/repos/{self.org}/{self.repo}/{tail}"

    def get_file(self, path, ref=None):
        """File content at a ref, or None when missing."""
        url = self._repo_url(f"contents/{urllib.parse.quote(path)}")
        if ref:
            url += f"?ref={urllib.parse.quote(ref)}"
        try:
            data = self._http.request_json(url, headers=self._headers())
        except HttpError as e:
            if e.status == 404:
                return None
            raise
        if isinstance(data, dict) and data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        return None

    def branch_exists(self, branch):
        url = self._repo_url(f"branches/{urllib.parse.quote(branch)}")
        try:
            self._http.request_json(url, headers=self._headers())
            return True
        except HttpError as e:
            if e.status == 404:
                return False
            raise

    def list_tree(self, branch):
        """All file paths (blobs) on the branch, repo-relative with forward slashes.

        Returns (paths, truncated). GitHub truncates very large trees; the caller
        should warn when truncated is True.
        """
        url = self._repo_url(f"git/trees/{urllib.parse.quote(branch)}?recursive=1")
        data = self._http.request_json(url, headers=self._headers())
        paths = [entry["path"] for entry in data.get("tree", [])
                 if entry.get("type") == "blob"]
        return paths, bool(data.get("truncated"))

    # ---- workspace fetch (byte-accurate) ----------------------------------
    def get_file_blob(self, path, ref=None):
        """(content_bytes, blob_sha) at a ref, or (None, None) when missing.

        Byte-accurate (no decode) so workspace copies and patches preserve the
        exact line endings and encoding stored on GitHub.
        """
        url = self._repo_url(f"contents/{urllib.parse.quote(path)}")
        if ref:
            url += f"?ref={urllib.parse.quote(ref)}"
        try:
            data = self._http.request_json(url, headers=self._headers())
        except HttpError as e:
            if e.status == 404:
                return None, None
            raise
        if isinstance(data, dict) and data.get("encoding") == "base64":
            return base64.b64decode(data["content"]), data.get("sha")
        return None, None

    # ---- Git Data writes (used by publish.py only) ------------------------
    def get_branch_sha(self, branch):
        """Tip commit SHA of a branch, or None when the branch doesn't exist."""
        url = self._repo_url(f"git/ref/{urllib.parse.quote(f'heads/{branch}', safe='/')}")
        try:
            data = self._http.request_json(url, headers=self._headers())
        except HttpError as e:
            if e.status == 404:
                return None
            raise
        return data.get("object", {}).get("sha")

    def get_commit_tree(self, commit_sha):
        """Tree SHA of a commit."""
        data = self._http.request_json(self._repo_url(f"git/commits/{commit_sha}"),
                                       headers=self._headers())
        return data.get("tree", {}).get("sha")

    def create_blob(self, content_bytes):
        """Upload one file's content, return its blob SHA (base64 = binary-safe)."""
        data = self._http.request_json(
            self._repo_url("git/blobs"), method="POST", headers=self._headers(),
            json_body={"content": base64.b64encode(content_bytes).decode("ascii"),
                       "encoding": "base64"})
        return data.get("sha")

    def create_tree(self, base_tree_sha, entries):
        """New tree on top of base_tree_sha; entries = [{path, sha}]. Returns tree SHA."""
        tree = [{"path": e["path"], "mode": "100644", "type": "blob", "sha": e["sha"]}
                for e in entries]
        data = self._http.request_json(
            self._repo_url("git/trees"), method="POST", headers=self._headers(),
            json_body={"base_tree": base_tree_sha, "tree": tree})
        return data.get("sha")

    def create_commit(self, message, tree_sha, parent_shas):
        """New commit object. Returns {'sha', 'html_url'}."""
        data = self._http.request_json(
            self._repo_url("git/commits"), method="POST", headers=self._headers(),
            json_body={"message": message, "tree": tree_sha, "parents": list(parent_shas)})
        return {"sha": data.get("sha"), "html_url": data.get("html_url")}

    def create_ref(self, branch, sha):
        self._http.request_json(
            self._repo_url("git/refs"), method="POST", headers=self._headers(),
            json_body={"ref": f"refs/heads/{branch}", "sha": sha})

    def update_ref(self, branch, sha):
        """Fast-forward the branch to sha (422 = branch moved concurrently)."""
        self._http.request_json(
            self._repo_url(f"git/refs/{urllib.parse.quote(f'heads/{branch}', safe='/')}"),
            method="PATCH", headers=self._headers(), json_body={"sha": sha})

    def token_scopes(self):
        """Classic-PAT scope list from X-OAuth-Scopes, or None when the header is
        absent (fine-grained PATs / GitHub Apps do not send it). Best-effort probe."""
        self._http.request_json(f"{self.api_base}/rate_limit", headers=self._headers())
        raw = self._http.last_headers.get("X-OAuth-Scopes")
        if raw is None:
            return None
        return [s.strip() for s in raw.split(",") if s.strip()]

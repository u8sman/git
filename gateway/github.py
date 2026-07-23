import time
from pathlib import Path

import httpx
import jwt
from django.conf import settings


class GitHubAPIError(Exception):
    def __init__(self, message, status_code=502, details=None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class GitHubClient:
    api_base = "https://api.github.com"

    def __init__(self, project):
        self.project = project
        self.client = httpx.Client(
            timeout=30,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "ai-git-gateway",
            },
        )
        self.client.headers["Authorization"] = f"Bearer {self._access_token()}"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.client.close()

    def _access_token(self):
        if settings.GITHUB_AUTH_MODE == "token":
            if not settings.GITHUB_TOKEN:
                raise GitHubAPIError("GITHUB_TOKEN is not configured on the server.", 500)
            return settings.GITHUB_TOKEN

        if not settings.GITHUB_APP_ID:
            raise GitHubAPIError("GitHub App ID is not configured on the server.", 500)
        if not self.project.installation_id:
            raise GitHubAPIError("This project does not have a GitHub App installation ID.", 400)

        private_key = settings.GITHUB_APP_PRIVATE_KEY.strip()
        if not private_key and settings.GITHUB_APP_PRIVATE_KEY_PATH:
            key_path = Path(settings.GITHUB_APP_PRIVATE_KEY_PATH)
            try:
                private_key = key_path.read_text().strip()
            except OSError as exc:
                raise GitHubAPIError(f"Cannot read GitHub App private key: {exc}", 500) from exc
        if not private_key:
            raise GitHubAPIError(
                "GitHub App private key is not configured. Set GITHUB_APP_PRIVATE_KEY "
                "or GITHUB_APP_PRIVATE_KEY_PATH.",
                500,
            )

        now = int(time.time())
        app_jwt = jwt.encode(
            {"iat": now - 60, "exp": now + 540, "iss": settings.GITHUB_APP_ID},
            private_key,
            algorithm="RS256",
        )
        response = httpx.post(
            f"{self.api_base}/app/installations/{self.project.installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "ai-git-gateway",
            },
            json={
                "repositories": [self.project.github_repo],
                "permissions": {"contents": "write", "metadata": "read"},
            },
            timeout=30,
        )
        if response.status_code >= 400:
            self._raise(response, "Unable to create a GitHub App installation token")
        return response.json()["token"]

    def _request(self, method, path, **kwargs):
        response = self.client.request(method, f"{self.api_base}{path}", **kwargs)
        if response.status_code >= 400:
            self._raise(response, f"GitHub API request failed: {method} {path}")
        return response

    @staticmethod
    def _raise(response, message):
        try:
            details = response.json()
            github_message = details.get("message")
        except ValueError:
            details = response.text[:1000]
            github_message = None
        status = 409 if response.status_code in {409, 422} else 502
        raise GitHubAPIError(
            f"{message}{': ' + github_message if github_message else ''}",
            status,
            details,
        )

    @property
    def repo_path(self):
        return f"/repos/{self.project.github_owner}/{self.project.github_repo}"

    def get_ref(self, branch):
        response = self._request("GET", f"{self.repo_path}/git/ref/heads/{branch}")
        return response.json()["object"]["sha"]

    def get_commit(self, sha):
        return self._request("GET", f"{self.repo_path}/git/commits/{sha}").json()

    def create_blob(self, content, *, is_base64=False):
        if is_base64:
            encoding = "base64"
            value = content
        else:
            encoding = "utf-8"
            value = content
        response = self._request(
            "POST",
            f"{self.repo_path}/git/blobs",
            json={"content": value, "encoding": encoding},
        )
        return response.json()["sha"]

    def create_tree(self, base_tree, entries):
        response = self._request(
            "POST",
            f"{self.repo_path}/git/trees",
            json={"base_tree": base_tree, "tree": entries},
        )
        return response.json()["sha"]

    def create_commit(self, message, tree_sha, parent_sha):
        response = self._request(
            "POST",
            f"{self.repo_path}/git/commits",
            json={"message": message, "tree": tree_sha, "parents": [parent_sha]},
        )
        return response.json()["sha"]

    def update_ref(self, branch, commit_sha):
        self._request(
            "PATCH",
            f"{self.repo_path}/git/refs/heads/{branch}",
            json={"sha": commit_sha, "force": False},
        )

    def push_files(self, *, branch, message, files, expected_head=None):
        head_sha = self.get_ref(branch)
        if expected_head and head_sha != expected_head:
            raise GitHubAPIError(
                f"Branch changed. Expected {expected_head}, but current head is {head_sha}.",
                409,
            )
        commit = self.get_commit(head_sha)
        base_tree = commit["tree"]["sha"]
        entries = []
        for item in files:
            if item.get("delete"):
                entries.append(
                    {"path": item["path"], "mode": "100644", "type": "blob", "sha": None}
                )
                continue
            blob_sha = self.create_blob(
                item.get("content_base64", item.get("content", "")),
                is_base64="content_base64" in item,
            )
            entries.append(
                {
                    "path": item["path"],
                    "mode": item.get("mode", "100644"),
                    "type": "blob",
                    "sha": blob_sha,
                }
            )
        tree_sha = self.create_tree(base_tree, entries)
        if tree_sha == base_tree:
            raise GitHubAPIError("The submitted files do not change the repository.", 400)
        commit_sha = self.create_commit(message, tree_sha, head_sha)
        self.update_ref(branch, commit_sha)
        return {
            "sha": commit_sha,
            "url": f"https://github.com/{self.project.full_name}/commit/{commit_sha}",
            "previous_head": head_sha,
        }

    def get_contents(self, path, branch):
        # path can be empty for repository root
        url_path = f"{self.repo_path}/contents/{path.lstrip('/')}"
        response = self._request("GET", url_path, params={"ref": branch})
        return response.json()

    def get_tree(self, tree_sha, *, recursive=True):
        params = {"recursive": "1"} if recursive else {}
        response = self._request("GET", f"{self.repo_path}/git/trees/{tree_sha}", params=params)
        return response.json()


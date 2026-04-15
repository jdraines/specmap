"""GitLab forge provider — implements ForgeProvider protocol."""

from __future__ import annotations

import base64
import secrets
from urllib.parse import quote, urlencode

import httpx

from specmap.server.forge import ForgeNotFound


def _count_diff_stats(diff_text: str) -> tuple[int, int]:
    """Count additions and deletions from a unified diff."""
    additions = 0
    deletions = 0
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1
    return additions, deletions


def _gitlab_next_url(resp: httpx.Response) -> str | None:
    """Extract next page URL from GitLab pagination headers."""
    next_page = resp.headers.get("x-next-page", "")
    if not next_page:
        return None
    # Reconstruct URL with the next page number
    current_url = str(resp.url)
    # Replace or add page parameter
    from urllib.parse import parse_qs, urlencode as ue, urlparse, urlunparse

    parsed = urlparse(current_url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params["page"] = [next_page]
    new_query = ue({k: v[0] for k, v in params.items()})
    return urlunparse(parsed._replace(query=new_query))


class GitLabProvider:
    """GitLab API provider with normalized responses."""

    name: str = "gitlab"

    def __init__(self, base_url: str = "https://gitlab.com") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_base = f"{self.base_url}/api/v4"

    def _headers(self, token: str) -> dict[str, str]:
        return {"PRIVATE-TOKEN": token}

    def _project_id(self, owner: str, name: str) -> str:
        """URL-encode namespace/project for GitLab API."""
        return quote(f"{owner}/{name}", safe="")

    # --- OAuth ---

    def oauth_authorize_url(
        self, base_url: str, client_id: str, redirect_uri: str
    ) -> tuple[str, str]:
        state = secrets.token_urlsafe(32)
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "read_api read_repository",
            "state": state,
        }
        return f"{self.base_url}/oauth/authorize?{urlencode(params)}", state

    async def oauth_exchange_code(
        self,
        client: httpx.AsyncClient,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
    ) -> dict:
        resp = await client.post(
            f"{self.base_url}/oauth/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        return resp.json()

    # --- Data ---

    async def get_user(self, client: httpx.AsyncClient, token: str) -> dict:
        resp = await client.get(f"{self.api_base}/user", headers=self._headers(token))
        resp.raise_for_status()
        u = resp.json()
        return {
            "id": u["id"],
            "login": u["username"],
            "name": u.get("name") or "",
            "avatar_url": u.get("avatar_url") or "",
        }

    async def list_repos(self, client: httpx.AsyncClient, token: str) -> list[dict]:
        repos: list[dict] = []
        url = f"{self.api_base}/projects?membership=true&per_page=100&order_by=updated_at"
        while url:
            resp = await client.get(url, headers=self._headers(token))
            resp.raise_for_status()
            for p in resp.json():
                repos.append(self._normalize_repo(p))
            url = _gitlab_next_url(resp)
        return repos

    async def list_repos_page(
        self, client: httpx.AsyncClient, token: str,
        *, page: int = 1, per_page: int = 20, search: str = "",
        login: str = "",
    ) -> dict:
        params: dict[str, str] = {
            "membership": "true",
            "order_by": "updated_at",
            "sort": "desc",
            "per_page": str(per_page),
            "page": str(page),
        }
        if search:
            params["search"] = search
        resp = await client.get(
            f"{self.api_base}/projects", params=params,
            headers=self._headers(token),
        )
        resp.raise_for_status()
        items = [self._normalize_repo(p) for p in resp.json()]
        total = int(resp.headers.get("x-total", "0"))
        total_pages = int(resp.headers.get("x-total-pages", "1"))
        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        }

    async def get_repo(
        self, client: httpx.AsyncClient, token: str, owner: str, name: str
    ) -> dict:
        proj_id = self._project_id(owner, name)
        resp = await client.get(
            f"{self.api_base}/projects/{proj_id}", headers=self._headers(token)
        )
        resp.raise_for_status()
        return self._normalize_repo(resp.json())

    async def list_pulls(
        self, client: httpx.AsyncClient, token: str, owner: str, repo: str,
        *, per_page: int = 30,
    ) -> list[dict]:
        proj_id = self._project_id(owner, repo)
        resp = await client.get(
            f"{self.api_base}/projects/{proj_id}/merge_requests",
            params={"state": "opened", "per_page": str(per_page)},
            headers=self._headers(token),
        )
        resp.raise_for_status()
        return [self._normalize_pull(mr) for mr in resp.json()]

    async def get_pull(
        self, client: httpx.AsyncClient, token: str, owner: str, repo: str, number: int
    ) -> dict:
        proj_id = self._project_id(owner, repo)
        resp = await client.get(
            f"{self.api_base}/projects/{proj_id}/merge_requests/{number}",
            headers=self._headers(token),
        )
        resp.raise_for_status()
        return self._normalize_pull(resp.json())

    async def list_pull_files(
        self, client: httpx.AsyncClient, token: str, owner: str, repo: str, number: int
    ) -> list[dict]:
        proj_id = self._project_id(owner, repo)
        resp = await client.get(
            f"{self.api_base}/projects/{proj_id}/merge_requests/{number}/diffs",
            params={"per_page": "100"},
            headers=self._headers(token),
        )
        resp.raise_for_status()
        result = []
        for d in resp.json():
            diff_text = d.get("diff", "")
            additions, deletions = _count_diff_stats(diff_text)
            # Determine file status
            if d.get("new_file"):
                status = "added"
            elif d.get("deleted_file"):
                status = "removed"
            elif d.get("renamed_file"):
                status = "renamed"
            else:
                status = "modified"
            result.append({
                "filename": d.get("new_path", d.get("old_path", "")),
                "status": status,
                "additions": additions,
                "deletions": deletions,
                "changes": additions + deletions,
                "patch": diff_text,
            })
        return result

    async def get_file_content(
        self,
        client: httpx.AsyncClient,
        token: str,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> bytes:
        proj_id = self._project_id(owner, repo)
        encoded_path = quote(path, safe="")
        resp = await client.get(
            f"{self.api_base}/projects/{proj_id}/repository/files/{encoded_path}",
            params={"ref": ref},
            headers=self._headers(token),
        )
        if resp.status_code == 404:
            raise ForgeNotFound(f"{owner}/{repo}/{path}@{ref}")
        resp.raise_for_status()
        data = resp.json()
        return base64.b64decode(data["content"])

    async def list_tree(
        self,
        client: httpx.AsyncClient,
        token: str,
        owner: str,
        repo: str,
        sha: str,
    ) -> list[dict]:
        proj_id = self._project_id(owner, repo)
        entries: list[dict] = []
        url: str | None = (
            f"{self.api_base}/projects/{proj_id}/repository/tree"
            f"?recursive=true&ref={sha}&per_page=100"
        )
        while url:
            resp = await client.get(url, headers=self._headers(token))
            resp.raise_for_status()
            for e in resp.json():
                entries.append({
                    "path": e["path"],
                    "type": "blob" if e["type"] == "blob" else "tree",
                })
            url = _gitlab_next_url(resp)
        return entries

    def clone_url(self, owner: str, repo: str, token: str) -> str:
        host = self.base_url.replace("https://", "").replace("http://", "")
        return f"https://oauth2:{token}@{host}/{owner}/{repo}.git"

    # --- Normalization helpers ---

    @staticmethod
    def _normalize_repo(p: dict) -> dict:
        return {
            "id": p["id"],
            "owner": p["path_with_namespace"].rsplit("/", 1)[0],
            "name": p["path"],
            "full_name": p["path_with_namespace"],
            "private": p.get("visibility") == "private",
        }

    @staticmethod
    def _normalize_pull(mr: dict) -> dict:
        return {
            "number": mr["iid"],
            "title": mr["title"],
            "state": mr["state"],
            "head_branch": mr["source_branch"],
            "base_branch": mr["target_branch"],
            "head_sha": mr.get("sha") or "",
            "author_login": mr.get("author", {}).get("username", ""),
        }

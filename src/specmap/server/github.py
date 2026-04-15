"""GitHub forge provider — implements ForgeProvider protocol."""

from __future__ import annotations

import base64
import secrets
from urllib.parse import urlencode

import httpx

from specmap.server.forge import ForgeNotFound

API_BASE = "https://api.github.com"
GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_HEADERS = {"Accept": "application/vnd.github+json"}


import math
import re as _re


def _parse_link_page(resp: httpx.Response, rel: str) -> int | None:
    """Extract page number for a given rel from the Link header."""
    link = resp.headers.get("link", "")
    for part in link.split(","):
        if f'rel="{rel}"' in part:
            m = _re.search(r"[?&]page=(\d+)", part)
            if m:
                return int(m.group(1))
    return None


def _next_link(resp: httpx.Response) -> str | None:
    link = resp.headers.get("link", "")
    for part in link.split(","):
        if 'rel="next"' in part:
            url = part.split(";")[0].strip().strip("<>")
            return url
    return None


class GitHubProvider:
    """GitHub API provider with normalized responses."""

    name: str = "github"

    def __init__(self, base_url: str = API_BASE) -> None:
        self.base_url = base_url

    def _headers(self, token: str) -> dict[str, str]:
        return {**GITHUB_HEADERS, "Authorization": f"Bearer {token}"}

    # --- OAuth ---

    def oauth_authorize_url(
        self, base_url: str, client_id: str, redirect_uri: str
    ) -> tuple[str, str]:
        state = secrets.token_urlsafe(32)
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "repo",
            "state": state,
        }
        return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}", state

    async def oauth_exchange_code(
        self,
        client: httpx.AsyncClient,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
    ) -> dict:
        resp = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()

    # --- Data ---

    async def get_user(self, client: httpx.AsyncClient, token: str) -> dict:
        resp = await client.get(f"{self.base_url}/user", headers=self._headers(token))
        resp.raise_for_status()
        u = resp.json()
        return {
            "id": u["id"],
            "login": u["login"],
            "name": u.get("name") or "",
            "avatar_url": u.get("avatar_url") or "",
        }

    async def list_repos(self, client: httpx.AsyncClient, token: str) -> list[dict]:
        repos: list[dict] = []
        url = f"{self.base_url}/user/repos?per_page=100&sort=updated"
        while url:
            resp = await client.get(url, headers=self._headers(token))
            resp.raise_for_status()
            for r in resp.json():
                repos.append(self._normalize_repo(r))
            url = _next_link(resp)
        return repos

    async def list_repos_page(
        self, client: httpx.AsyncClient, token: str,
        *, page: int = 1, per_page: int = 20, search: str = "",
        login: str = "",
    ) -> dict:
        if search:
            # GitHub /user/repos has no search — use search API
            q = f"{search} user:{login}" if login else search
            resp = await client.get(
                f"{self.base_url}/search/repositories",
                params={"q": q, "sort": "updated", "per_page": str(per_page), "page": str(page)},
                headers=self._headers(token),
            )
            resp.raise_for_status()
            data = resp.json()
            total = min(data.get("total_count", 0), 1000)  # GitHub caps at 1000
            items = [self._normalize_repo(r) for r in data.get("items", [])]
            return {
                "items": items,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": max(1, math.ceil(total / per_page)),
            }
        else:
            resp = await client.get(
                f"{self.base_url}/user/repos",
                params={"per_page": str(per_page), "page": str(page), "sort": "updated"},
                headers=self._headers(token),
            )
            resp.raise_for_status()
            items = [self._normalize_repo(r) for r in resp.json()]
            last_page = _parse_link_page(resp, "last")
            if last_page is not None:
                total_pages = last_page
                total = total_pages * per_page  # approximate
            elif len(items) < per_page:
                # We're on the last (or only) page
                total_pages = page
                total = (page - 1) * per_page + len(items)
            else:
                # No Link header but full page — assume there's more
                total_pages = page + 1
                total = total_pages * per_page
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
        resp = await client.get(
            f"{self.base_url}/repos/{owner}/{name}", headers=self._headers(token)
        )
        resp.raise_for_status()
        return self._normalize_repo(resp.json())

    async def list_pulls(
        self, client: httpx.AsyncClient, token: str, owner: str, repo: str,
        *, per_page: int = 30,
    ) -> list[dict]:
        resp = await client.get(
            f"{self.base_url}/repos/{owner}/{repo}/pulls",
            params={"state": "open", "per_page": str(per_page)},
            headers=self._headers(token),
        )
        resp.raise_for_status()
        return [self._normalize_pull(p) for p in resp.json()]

    async def get_pull(
        self, client: httpx.AsyncClient, token: str, owner: str, repo: str, number: int
    ) -> dict:
        resp = await client.get(
            f"{self.base_url}/repos/{owner}/{repo}/pulls/{number}",
            headers=self._headers(token),
        )
        resp.raise_for_status()
        return self._normalize_pull(resp.json())

    async def list_pull_files(
        self, client: httpx.AsyncClient, token: str, owner: str, repo: str, number: int
    ) -> list[dict]:
        resp = await client.get(
            f"{self.base_url}/repos/{owner}/{repo}/pulls/{number}/files",
            params={"per_page": "100"},
            headers=self._headers(token),
        )
        resp.raise_for_status()
        return [
            {
                "filename": f["filename"],
                "status": f["status"],
                "additions": f["additions"],
                "deletions": f["deletions"],
                "changes": f["changes"],
                "patch": f.get("patch", ""),
            }
            for f in resp.json()
        ]

    async def get_file_content(
        self,
        client: httpx.AsyncClient,
        token: str,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> bytes:
        resp = await client.get(
            f"{self.base_url}/repos/{owner}/{repo}/contents/{path}",
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
        resp = await client.get(
            f"{self.base_url}/repos/{owner}/{repo}/git/trees/{sha}",
            params={"recursive": "1"},
            headers=self._headers(token),
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("truncated"):
            import logging
            logging.getLogger("specmap.server").warning(
                "GitHub tree listing truncated for %s/%s@%s", owner, repo, sha
            )
        return [{"path": e["path"], "type": e["type"]} for e in data.get("tree", [])]

    def clone_url(self, owner: str, repo: str, token: str) -> str:
        # Derive host: api.github.com → github.com, {host}/api/v3 → {host}
        if self.base_url == API_BASE:
            host = "github.com"
        elif self.base_url.endswith("/api/v3"):
            host = self.base_url[len("https://"):-len("/api/v3")]
        else:
            host = self.base_url.replace("https://", "").replace("http://", "")
        return f"https://x-access-token:{token}@{host}/{owner}/{repo}.git"

    # --- Normalization helpers ---

    @staticmethod
    def _normalize_repo(r: dict) -> dict:
        return {
            "id": r["id"],
            "owner": r["owner"]["login"],
            "name": r["name"],
            "full_name": r["full_name"],
            "private": r["private"],
        }

    @staticmethod
    def _normalize_pull(p: dict) -> dict:
        return {
            "number": p["number"],
            "title": p["title"],
            "state": p["state"],
            "head_branch": p["head"]["ref"],
            "base_branch": p["base"]["ref"],
            "head_sha": p["head"]["sha"],
            "author_login": p.get("user", {}).get("login", ""),
        }

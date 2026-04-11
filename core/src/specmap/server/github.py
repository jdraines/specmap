"""GitHub API client using httpx."""

from __future__ import annotations

import base64

import httpx

API_BASE = "https://api.github.com"
GITHUB_HEADERS = {"Accept": "application/vnd.github+json"}


class GitHubNotFound(Exception):
    pass


def _headers(token: str) -> dict[str, str]:
    return {**GITHUB_HEADERS, "Authorization": f"Bearer {token}"}


async def exchange_code(
    client: httpx.AsyncClient, client_id: str, client_secret: str, code: str
) -> dict:
    resp = await client.post(
        "https://github.com/login/oauth/access_token",
        data={"client_id": client_id, "client_secret": client_secret, "code": code},
        headers={"Accept": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()


async def get_user(client: httpx.AsyncClient, token: str) -> dict:
    resp = await client.get(f"{API_BASE}/user", headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


async def list_repos(client: httpx.AsyncClient, token: str) -> list[dict]:
    """List all repos accessible to the authenticated user via OAuth."""
    repos: list[dict] = []
    url = f"{API_BASE}/user/repos?per_page=100&sort=updated"
    while url:
        resp = await client.get(url, headers=_headers(token))
        resp.raise_for_status()
        repos.extend(resp.json())
        # Follow pagination
        url = _next_link(resp)
    return repos


async def get_repo(client: httpx.AsyncClient, token: str, owner: str, name: str) -> dict:
    resp = await client.get(f"{API_BASE}/repos/{owner}/{name}", headers=_headers(token))
    resp.raise_for_status()
    return resp.json()


async def list_pulls(
    client: httpx.AsyncClient, token: str, owner: str, repo: str
) -> list[dict]:
    resp = await client.get(
        f"{API_BASE}/repos/{owner}/{repo}/pulls",
        params={"state": "open", "per_page": "30"},
        headers=_headers(token),
    )
    resp.raise_for_status()
    return resp.json()


async def get_pull(
    client: httpx.AsyncClient, token: str, owner: str, repo: str, number: int
) -> dict:
    resp = await client.get(
        f"{API_BASE}/repos/{owner}/{repo}/pulls/{number}", headers=_headers(token)
    )
    resp.raise_for_status()
    return resp.json()


async def list_pull_files(
    client: httpx.AsyncClient, token: str, owner: str, repo: str, number: int
) -> list[dict]:
    resp = await client.get(
        f"{API_BASE}/repos/{owner}/{repo}/pulls/{number}/files",
        params={"per_page": "100"},
        headers=_headers(token),
    )
    resp.raise_for_status()
    return resp.json()


async def get_file_content(
    client: httpx.AsyncClient, token: str, owner: str, repo: str, path: str, ref: str
) -> bytes:
    resp = await client.get(
        f"{API_BASE}/repos/{owner}/{repo}/contents/{path}",
        params={"ref": ref},
        headers=_headers(token),
    )
    if resp.status_code == 404:
        raise GitHubNotFound(f"{owner}/{repo}/{path}@{ref}")
    resp.raise_for_status()
    data = resp.json()
    return base64.b64decode(data["content"])


def _next_link(resp: httpx.Response) -> str | None:
    link = resp.headers.get("link", "")
    for part in link.split(","):
        if 'rel="next"' in part:
            url = part.split(";")[0].strip().strip("<>")
            return url
    return None

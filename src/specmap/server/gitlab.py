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
        truncated_files: list[dict] = []
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
            entry = {
                "filename": d.get("new_path", d.get("old_path", "")),
                "status": status,
                "additions": additions,
                "deletions": deletions,
                "changes": additions + deletions,
                "patch": diff_text,
            }
            result.append(entry)
            # GitLab truncates large diffs — diff is empty but file is not binary
            if not diff_text and status != "removed" and not d.get("generated_file"):
                truncated_files.append(entry)

        # Fetch content for truncated diffs and synthesize patches
        if truncated_files:
            # Get MR head SHA for content fetching
            mr_resp = await client.get(
                f"{self.api_base}/projects/{proj_id}/merge_requests/{number}",
                headers=self._headers(token),
            )
            mr_resp.raise_for_status()
            head_sha = mr_resp.json().get("sha", "")

            for entry in truncated_files:
                try:
                    content = await self.get_file_content(
                        client, token, owner, repo, entry["filename"], head_sha,
                    )
                    text = content.decode("utf-8", errors="replace")
                    lines = text.splitlines()
                    if not lines:
                        continue
                    # Synthesize a unified diff patch
                    if entry["status"] == "added":
                        hunk_header = f"@@ -0,0 +1,{len(lines)} @@"
                        patch_lines = [hunk_header] + [f"+{line}" for line in lines]
                    else:
                        # For modified files we can only show the new content
                        hunk_header = f"@@ -1,0 +1,{len(lines)} @@"
                        patch_lines = [hunk_header] + [f" {line}" for line in lines]
                    entry["patch"] = "\n".join(patch_lines)
                    entry["additions"] = len(lines) if entry["status"] == "added" else 0
                    entry["changes"] = entry["additions"] + entry["deletions"]
                except (ForgeNotFound, Exception):
                    pass

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

    async def list_pull_comments(
        self, client: httpx.AsyncClient, token: str, owner: str, repo: str, number: int,
    ) -> dict:
        proj_id = self._project_id(owner, repo)
        discussions: list[dict] = []
        url: str | None = (
            f"{self.api_base}/projects/{proj_id}/merge_requests/{number}/discussions?per_page=100"
        )
        while url:
            resp = await client.get(url, headers=self._headers(token))
            resp.raise_for_status()
            discussions.extend(resp.json())
            url = _gitlab_next_url(resp)

        threads = []
        general_comments = []
        for disc in discussions:
            notes = disc.get("notes", [])
            if not notes:
                continue
            # Check if any note has a line-level position
            first_note = notes[0]
            position = first_note.get("position")
            is_line_level = position is not None and position.get("new_line") is not None

            comments = [self._normalize_comment(n) for n in notes]
            thread = {
                "thread_id": disc["id"],
                "path": position.get("new_path") if position else None,
                "line": position.get("new_line") if position else None,
                "side": "RIGHT" if is_line_level else None,
                "is_resolved": bool(notes[-1].get("resolved", False)) if disc.get("notes") else False,
                "is_outdated": bool(position.get("line_range") is None and position.get("new_line") is None) if position else False,
                "comments": comments,
                "comment_count": len(comments),
                "latest_updated_at": max(n.get("updated_at", "") for n in notes),
            }
            if is_line_level:
                threads.append(thread)
            else:
                general_comments.append(thread)

        return {"threads": threads, "general_comments": general_comments}

    async def post_pull_comment(
        self, client: httpx.AsyncClient, token: str, owner: str, repo: str, number: int,
        body: str, *,
        thread_id: str | None = None,
        path: str | None = None,
        line: int | None = None,
        side: str | None = None,
        head_sha: str | None = None,
    ) -> dict:
        proj_id = self._project_id(owner, repo)
        if thread_id:
            # Reply to existing discussion
            resp = await client.post(
                f"{self.api_base}/projects/{proj_id}/merge_requests/{number}/discussions/{thread_id}/notes",
                json={"body": body},
                headers=self._headers(token),
            )
        elif path and line is not None:
            # New line-level discussion — need diff_refs from the MR
            mr_resp = await client.get(
                f"{self.api_base}/projects/{proj_id}/merge_requests/{number}",
                headers=self._headers(token),
            )
            mr_resp.raise_for_status()
            diff_refs = mr_resp.json().get("diff_refs", {})
            resp = await client.post(
                f"{self.api_base}/projects/{proj_id}/merge_requests/{number}/discussions",
                json={
                    "body": body,
                    "position": {
                        "position_type": "text",
                        "base_sha": diff_refs.get("base_sha", ""),
                        "head_sha": diff_refs.get("head_sha", ""),
                        "start_sha": diff_refs.get("start_sha", ""),
                        "new_path": path,
                        "new_line": line,
                    },
                },
                headers=self._headers(token),
            )
        else:
            # General MR note
            resp = await client.post(
                f"{self.api_base}/projects/{proj_id}/merge_requests/{number}/notes",
                json={"body": body},
                headers=self._headers(token),
            )
        resp.raise_for_status()
        data = resp.json()
        # For discussions, the response is the discussion object; extract the note
        if "notes" in data:
            return self._normalize_comment(data["notes"][-1])
        return self._normalize_comment(data)

    @staticmethod
    def _normalize_comment(note: dict) -> dict:
        author = note.get("author") or {}
        return {
            "id": str(note["id"]),
            "author_login": author.get("username", ""),
            "author_avatar": author.get("avatar_url", ""),
            "body": note.get("body", ""),
            "created_at": note.get("created_at", ""),
            "updated_at": note.get("updated_at", ""),
            "reactions": [],  # GitLab doesn't include inline; skip for v1
        }

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

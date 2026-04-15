"""Forge provider abstraction, token resolution, and remote detection."""

from __future__ import annotations

import logging
import os
import re
import subprocess
from typing import Protocol, runtime_checkable

import httpx

logger = logging.getLogger("specmap.server")


class ForgeNotFound(Exception):
    """Resource not found on the forge."""


@runtime_checkable
class ForgeProvider(Protocol):
    """Contract for all forge providers (GitHub, GitLab, etc.)."""

    name: str  # "github" or "gitlab"

    # --- OAuth (used only in OAuth mode) ---

    def oauth_authorize_url(
        self, base_url: str, client_id: str, redirect_uri: str
    ) -> tuple[str, str]:
        """Return (authorize_url, state_value)."""
        ...

    async def oauth_exchange_code(
        self,
        client: httpx.AsyncClient,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
    ) -> dict:
        """Exchange OAuth code for token data. Returns dict with access_token, etc."""
        ...

    # --- Data (used by both modes) ---

    async def get_user(self, client: httpx.AsyncClient, token: str) -> dict:
        """Return normalized user: {id, login, name, avatar_url}."""
        ...

    async def list_repos(self, client: httpx.AsyncClient, token: str) -> list[dict]:
        """Return normalized repos: [{id, owner, name, full_name, private}, ...]."""
        ...

    async def list_repos_page(
        self, client: httpx.AsyncClient, token: str,
        *, page: int = 1, per_page: int = 20, search: str = "",
        login: str = "",
    ) -> dict:
        """Return {items: [...], total: int, page: int, per_page: int, total_pages: int}."""
        ...

    async def get_repo(
        self, client: httpx.AsyncClient, token: str, owner: str, name: str
    ) -> dict:
        """Return normalized repo: {id, owner, name, full_name, private}."""
        ...

    async def list_pulls(
        self, client: httpx.AsyncClient, token: str, owner: str, repo: str,
        *, per_page: int = 30,
    ) -> list[dict]:
        """Return normalized pulls: [{number, title, state, head_branch, base_branch, head_sha, author_login}, ...]."""
        ...

    async def get_pull(
        self, client: httpx.AsyncClient, token: str, owner: str, repo: str, number: int
    ) -> dict:
        """Return normalized pull: {number, title, state, head_branch, base_branch, head_sha, author_login}."""
        ...

    async def list_pull_files(
        self, client: httpx.AsyncClient, token: str, owner: str, repo: str, number: int
    ) -> list[dict]:
        """Return normalized files: [{filename, status, additions, deletions, changes, patch}, ...]."""
        ...

    async def get_file_content(
        self,
        client: httpx.AsyncClient,
        token: str,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> bytes:
        """Return raw file content. Raises ForgeNotFound on 404."""
        ...

    async def list_tree(
        self,
        client: httpx.AsyncClient,
        token: str,
        owner: str,
        repo: str,
        sha: str,
    ) -> list[dict]:
        """Return recursive file listing: [{path, type}, ...].

        type is 'blob' for files, 'tree' for directories.
        """
        ...

    def clone_url(self, owner: str, repo: str, token: str) -> str:
        """Return HTTPS clone URL with embedded auth token."""
        ...


def resolve_token(provider_name: str) -> str | None:
    """Resolve a PAT for the given provider from env vars or CLI tools.

    Checks in order:
    1. Environment variables (GITHUB_TOKEN/GH_TOKEN or GITLAB_TOKEN)
    2. CLI tool fallback (gh auth token or glab config get token)
    Returns the token string or None.
    """
    if provider_name == "github":
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if token:
            return token
        # Fallback: gh CLI
        try:
            result = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    elif provider_name == "gitlab":
        token = os.environ.get("GITLAB_TOKEN")
        if token:
            return token
        # Fallback: glab CLI — try multiple methods
        for cmd in [
            ["glab", "config", "get", "token"],
            ["glab", "auth", "status", "-t"],
        ]:
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    tok = _parse_glab_token(result.stdout, result.stderr)
                    if tok:
                        return tok
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
    return None


def _parse_glab_token(stdout: str, stderr: str) -> str | None:
    """Extract a token from glab output.

    `glab config get token` prints the raw token on stdout.
    `glab auth status -t` prints "Token: glpat-..." on stderr (or stdout).
    """
    # Direct token output (glab config get token)
    if stdout.strip() and "\n" not in stdout.strip():
        candidate = stdout.strip()
        if candidate.startswith("glpat-") or len(candidate) > 20:
            return candidate

    # Parse "Token: <value>" from auth status output (may be on stderr)
    for line in (stderr + "\n" + stdout).splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("token:"):
            tok = stripped.split(":", 1)[1].strip()
            if tok:
                return tok
    return None


_SSH_REMOTE_RE = re.compile(r"^[\w.-]+@([\w.-]+):(.+?)(?:\.git)?$")
_HTTPS_REMOTE_RE = re.compile(r"^https?://([\w.-]+)/(.+?)(?:\.git)?$")


def detect_forge(repo_root: str | None = None) -> tuple[str, str]:
    """Auto-detect forge provider from git remote origin.

    Returns (provider_name, base_api_url).
    Respects SPECMAP_FORGE and SPECMAP_FORGE_URL env overrides.
    """
    # Check env override first
    override = os.environ.get("SPECMAP_FORGE", "").lower()
    override_url = os.environ.get("SPECMAP_FORGE_URL", "")
    if override in ("github", "gitlab"):
        if override == "github":
            return ("github", override_url or "https://api.github.com")
        else:
            return ("gitlab", override_url or "https://gitlab.com")

    # Parse git remote
    hostname = _get_remote_hostname(repo_root)
    if not hostname:
        # Default to github if we can't detect
        logger.warning("Could not detect git remote origin, defaulting to github")
        return ("github", "https://api.github.com")

    if hostname == "github.com":
        return ("github", "https://api.github.com")
    if hostname == "gitlab.com":
        return ("gitlab", "https://gitlab.com")

    # Unknown host — probe for GitLab, else assume GitHub Enterprise
    base = override_url or f"https://{hostname}"
    if _probe_gitlab(base):
        return ("gitlab", base)
    else:
        # GitHub Enterprise: API is at /api/v3
        return ("github", f"{base}/api/v3")


def _get_remote_hostname(repo_root: str | None) -> str | None:
    """Extract hostname from git remote get-url origin."""
    try:
        cmd = ["git", "remote", "get-url", "origin"]
        kwargs: dict = {"capture_output": True, "text": True, "timeout": 5}
        if repo_root:
            kwargs["cwd"] = repo_root
        result = subprocess.run(cmd, **kwargs)
        if result.returncode != 0:
            return None
        url = result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    # SSH: git@github.com:user/repo.git
    m = _SSH_REMOTE_RE.match(url)
    if m:
        return m.group(1)
    # HTTPS: https://github.com/user/repo.git
    m = _HTTPS_REMOTE_RE.match(url)
    if m:
        return m.group(1)
    return None


def _probe_gitlab(base_url: str) -> bool:
    """Check if a host is a GitLab instance by hitting /api/v4/version (no auth needed)."""
    try:
        resp = httpx.get(f"{base_url}/api/v4/version", timeout=5)
        # GitLab returns 401 (needs auth) or 200; either confirms it's GitLab
        return resp.status_code in (200, 401)
    except Exception:
        return False


def detect_auth_mode(config: object, provider_name: str) -> str:
    """Determine auth mode based on config.

    Returns "oauth" if OAuth client credentials are configured for the provider,
    otherwise "pat".
    """
    if provider_name == "github":
        client_id = getattr(config, "github_client_id", "")
        client_secret = getattr(config, "github_client_secret", "")
        if client_id and client_secret:
            return "oauth"
    elif provider_name == "gitlab":
        client_id = getattr(config, "gitlab_client_id", "")
        client_secret = getattr(config, "gitlab_client_secret", "")
        if client_id and client_secret:
            return "oauth"
    return "pat"

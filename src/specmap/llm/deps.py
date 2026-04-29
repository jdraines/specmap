"""Shared dependencies for pydantic-ai agents."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from specmap.server.forge import ForgeProvider


@dataclass
class ChatDeps:
    """Dependencies injected into every tool call."""

    provider: ForgeProvider
    http_client: httpx.AsyncClient
    token: str
    owner: str
    repo: str
    head_sha: str
    annotations: list[dict]
    changed_files: list[str] = field(default_factory=list)
    file_patches: dict[str, str] = field(default_factory=dict)  # filename → patch
    prompt_files: set[str] = field(default_factory=set)  # files whose content is in the prompt
    _file_tree: list[dict] | None = None
    _tool_cache: dict[str, str] = field(default_factory=dict)

    async def get_file_tree(self) -> list[dict]:
        """Lazily fetch and cache the full repo file tree."""
        if self._file_tree is None:
            self._file_tree = await self.provider.list_tree(
                self.http_client, self.token, self.owner, self.repo, self.head_sha
            )
        return self._file_tree

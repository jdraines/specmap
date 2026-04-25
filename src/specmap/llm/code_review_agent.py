"""Pydantic AI agent for code review generation."""

from __future__ import annotations

import fnmatch
import re

from pydantic_ai import Agent, RunContext

from specmap.llm.chat_agent import ChatDeps
from specmap.llm.code_review_prompts import _CODE_REVIEW_SYSTEM
from specmap.llm.code_review_schemas import CodeReviewResponse
from specmap.server.forge import ForgeNotFound

# Reuse ChatDeps — the review agent needs the same tools and context
CodeReviewDeps = ChatDeps

code_review_agent = Agent(
    deps_type=CodeReviewDeps,
    system_prompt=_CODE_REVIEW_SYSTEM,
    output_type=CodeReviewResponse,
    retries=2,
)


@code_review_agent.tool
async def search_annotations(
    ctx: RunContext[CodeReviewDeps],
    query: str,
    file_pattern: str | None = None,
) -> str:
    """Search PR annotations by keyword and optional file pattern.

    Args:
        query: Text to search for in annotation descriptions.
        file_pattern: Optional glob pattern to filter by file path.
    """
    results = []
    query_lower = query.lower()
    for ann in ctx.deps.annotations:
        if file_pattern and not fnmatch.fnmatch(ann.get("file", ""), file_pattern):
            continue
        desc = ann.get("description", "")
        if query_lower in desc.lower():
            refs_str = ""
            if ann.get("refs"):
                ref_parts = []
                for ref in ann["refs"]:
                    ref_parts.append(
                        f"[{ref.get('id', '?')}] {ref.get('spec_file', '')} > "
                        f"{ref.get('heading', '')}"
                    )
                refs_str = "\n    Refs: " + ", ".join(ref_parts)
            results.append(
                f"- {ann['file']} (lines {ann.get('start_line', '?')}-"
                f"{ann.get('end_line', '?')}): {desc}{refs_str}"
            )
    if not results:
        return f"No annotations matching '{query}'" + (
            f" in files matching '{file_pattern}'" if file_pattern else ""
        )
    return f"Found {len(results)} annotation(s):\n" + "\n".join(results[:20])


@code_review_agent.tool
async def grep_codebase(
    ctx: RunContext[CodeReviewDeps],
    pattern: str,
    file_glob: str | None = None,
    max_results: int = 20,
) -> str:
    """Grep-like regex search across repo files at PR HEAD.

    Args:
        pattern: Regex pattern to search for.
        file_glob: Optional glob to filter files.
        max_results: Maximum number of matching lines to return.
    """
    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"Invalid regex pattern: {e}"

    if file_glob:
        tree = await ctx.deps.get_file_tree()
        paths = [
            e["path"] for e in tree
            if e["type"] == "blob" and fnmatch.fnmatch(e["path"], file_glob)
        ]
    elif ctx.deps.changed_files:
        paths = list(ctx.deps.changed_files)
    else:
        tree = await ctx.deps.get_file_tree()
        paths = [e["path"] for e in tree if e["type"] == "blob"]

    paths = paths[:50]
    changed_set = set(ctx.deps.changed_files)
    matches: list[str] = []

    for path in paths:
        if len(matches) >= max_results:
            break
        try:
            raw = await ctx.deps.provider.get_file_content(
                ctx.deps.http_client, ctx.deps.token,
                ctx.deps.owner, ctx.deps.repo, path, ctx.deps.head_sha,
            )
            content = raw.decode("utf-8", errors="replace")
        except (ForgeNotFound, Exception):
            continue
        changed_marker = " [CHANGED IN PR]" if path in changed_set else ""
        for i, line in enumerate(content.splitlines(), 1):
            if compiled.search(line):
                matches.append(f"{path}:{i}{changed_marker}: {line.rstrip()}")
                if len(matches) >= max_results:
                    break

    if not matches:
        return f"No matches for pattern '{pattern}'" + (
            f" in files matching '{file_glob}'" if file_glob else ""
        )
    header = f"Found {len(matches)} match(es)"
    if len(matches) >= max_results:
        header += f" (capped at {max_results})"
    return header + ":\n" + "\n".join(matches)


@code_review_agent.tool
async def list_files(
    ctx: RunContext[CodeReviewDeps],
    path_prefix: str | None = None,
    glob: str | None = None,
) -> str:
    """List files in the repository tree.

    Args:
        path_prefix: Filter to files under this directory prefix.
        glob: Filter by glob pattern.
    """
    tree = await ctx.deps.get_file_tree()
    changed_set = set(ctx.deps.changed_files)
    paths = []
    for entry in tree:
        if entry["type"] != "blob":
            continue
        p = entry["path"]
        if path_prefix and not p.startswith(path_prefix):
            continue
        if glob and not fnmatch.fnmatch(p, glob):
            continue
        marker = " [CHANGED]" if p in changed_set else ""
        paths.append(f"{p}{marker}")

    if not paths:
        return "No files found" + (
            f" under '{path_prefix}'" if path_prefix else ""
        ) + (f" matching '{glob}'" if glob else "")

    truncated = ""
    if len(paths) > 100:
        truncated = f"\n... and {len(paths) - 100} more files"
        paths = paths[:100]
    return f"{len(paths)} file(s):\n" + "\n".join(paths) + truncated


@code_review_agent.tool
async def read_file(
    ctx: RunContext[CodeReviewDeps],
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    """Read a file's content from the repository at PR HEAD.

    If the file was changed in this PR, the diff is included.

    Args:
        path: File path relative to repo root.
        start_line: Optional 1-indexed start line.
        end_line: Optional 1-indexed end line (inclusive).
    """
    try:
        raw = await ctx.deps.provider.get_file_content(
            ctx.deps.http_client, ctx.deps.token,
            ctx.deps.owner, ctx.deps.repo, path, ctx.deps.head_sha,
        )
    except ForgeNotFound:
        return f"File not found: {path}"

    content = raw.decode("utf-8", errors="replace")
    lines = content.splitlines()

    if start_line or end_line:
        s = max((start_line or 1) - 1, 0)
        e = min(end_line or len(lines), len(lines))
        selected = lines[s:e]
        numbered = [f"{i}: {line}" for i, line in enumerate(selected, s + 1)]
        result = f"{path} (lines {s+1}-{e}):\n" + "\n".join(numbered)
    elif len(lines) > 500:
        numbered = [f"{i}: {line}" for i, line in enumerate(lines[:500], 1)]
        result = f"{path} ({len(lines)} lines, showing first 500):\n" + "\n".join(numbered)
    else:
        numbered = [f"{i}: {line}" for i, line in enumerate(lines, 1)]
        result = f"{path} ({len(lines)} lines):\n" + "\n".join(numbered)

    patch = ctx.deps.file_patches.get(path)
    if patch:
        result += f"\n\n--- PR diff for {path} ---\n```diff\n{patch}\n```"

    return result

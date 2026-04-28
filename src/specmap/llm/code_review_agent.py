"""Pydantic AI agents for code review generation.

Three agents form the review pipeline:
- review_agent: Toolless, single-call review (Phase 1)
- cross_boundary_agent: Targeted tool use for wiring issues (Phase 2)
- consolidation_agent: Toolless dedup/validation (Phase 3)
"""

from __future__ import annotations

import fnmatch
import re

from pydantic_ai import Agent, RunContext

from specmap.llm.chat_agent import ChatDeps, _read_single_file
from specmap.llm.code_review_prompts import (
    _CODE_REVIEW_SYSTEM,
    _CONSOLIDATION_SYSTEM,
    _CROSS_BOUNDARY_SYSTEM,
)
from specmap.llm.code_review_schemas import CodeReviewResponse
from specmap.server.forge import ForgeNotFound

# Reuse ChatDeps for agents that need tools
CodeReviewDeps = ChatDeps

# Phase 1: Toolless review — single LLM call, no agentic loop
review_agent = Agent(
    system_prompt=_CODE_REVIEW_SYSTEM,
    output_type=CodeReviewResponse,
    retries=2,
)

# Phase 2: Cross-boundary verification — targeted tool use with strict budget
cross_boundary_agent = Agent(
    deps_type=CodeReviewDeps,
    system_prompt=_CROSS_BOUNDARY_SYSTEM,
    output_type=CodeReviewResponse,
    retries=2,
)

# Phase 3: Consolidation — toolless dedup/validation
consolidation_agent = Agent(
    system_prompt=_CONSOLIDATION_SYSTEM,
    output_type=CodeReviewResponse,
    retries=2,
)


# --- Tools for cross_boundary_agent only ---


@cross_boundary_agent.tool
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


@cross_boundary_agent.tool
async def grep_codebase(
    ctx: RunContext[CodeReviewDeps],
    pattern: str,
    file_glob: str | None = None,
    max_results: int = 50,
) -> str:
    """Grep-like regex search across repo files at PR HEAD.

    Args:
        pattern: Regex pattern to search for.
        file_glob: Optional glob to filter files.
        max_results: Maximum number of matching lines to return (default 50).
    """
    cache_key = f"grep:{pattern}:{file_glob}:{max_results}"
    if cache_key in ctx.deps._tool_cache:
        return ctx.deps._tool_cache[cache_key]

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
        result = f"No matches for pattern '{pattern}'" + (
            f" in files matching '{file_glob}'" if file_glob else ""
        )
    else:
        header = f"Found {len(matches)} match(es)"
        if len(matches) >= max_results:
            header += f" (capped at {max_results})"
        result = header + ":\n" + "\n".join(matches)
    ctx.deps._tool_cache[cache_key] = result
    return result


@cross_boundary_agent.tool
async def list_files(
    ctx: RunContext[CodeReviewDeps],
    path_prefix: str | None = None,
    glob: str | None = None,
    offset: int = 0,
    limit: int = 200,
) -> str:
    """List files in the repository tree.

    Args:
        path_prefix: Filter to files under this directory prefix.
        glob: Filter by glob pattern.
        offset: Skip this many results (for pagination).
        limit: Maximum number of paths to return (default 200).
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

    total = len(paths)
    if not paths:
        return "No files found" + (
            f" under '{path_prefix}'" if path_prefix else ""
        ) + (f" matching '{glob}'" if glob else "")

    paths = paths[offset:offset + limit]
    truncated = ""
    remaining = total - offset - len(paths)
    if remaining > 0:
        truncated = f"\n... and {remaining} more files (use offset={offset + limit} to see next page)"
    return f"{len(paths)} file(s) (of {total} total):\n" + "\n".join(paths) + truncated


@cross_boundary_agent.tool
async def read_file(
    ctx: RunContext[CodeReviewDeps],
    path: str,
    paths: list[str] | None = None,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    """Read file content from the repository at PR HEAD.

    Can read multiple files in one call via the paths parameter.

    Args:
        path: File path relative to repo root (for single file).
        paths: List of file paths to read in one call (for multiple files).
        start_line: Optional 1-indexed start line (only for single file).
        end_line: Optional 1-indexed end line inclusive (only for single file).
    """
    all_paths = paths or [path]
    if len(all_paths) == 1:
        return await _read_single_file(ctx, all_paths[0], start_line, end_line)

    results = []
    for p in all_paths:
        results.append(await _read_single_file(ctx, p))
    return "\n\n---\n\n".join(results)

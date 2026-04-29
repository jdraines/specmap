"""Shared codebase tools for pydantic-ai agents.

Defines tool functions and a CODEBASE_TOOLS list of Tool objects that can be
passed to any Agent(tools=CODEBASE_TOOLS) that uses ChatDeps.
"""

from __future__ import annotations

import fnmatch
import re

from pydantic_ai import RunContext, Tool

from specmap.llm.deps import ChatDeps
from specmap.server.forge import ForgeNotFound


async def search_annotations(
    ctx: RunContext[ChatDeps],
    query: str,
    file_pattern: str | None = None,
) -> str:
    """Search PR annotations by keyword and optional file pattern.

    Args:
        query: Text to search for in annotation descriptions.
        file_pattern: Optional glob pattern to filter by file path (e.g. "src/auth/*.py").
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


async def grep_codebase(
    ctx: RunContext[ChatDeps],
    pattern: str,
    file_glob: str | None = None,
    max_results: int = 50,
) -> str:
    """Grep-like regex search across repo files at PR HEAD.

    Results indicate which files were changed in this PR.

    Args:
        pattern: Regex pattern to search for.
        file_glob: Optional glob to filter files (e.g. "*.py", "src/**/*.ts").
        max_results: Maximum number of matching lines to return (default 50).
    """
    deps = ctx.deps
    cache_key = f"grep:{pattern}:{file_glob}:{max_results}"
    if cache_key in deps._tool_cache:
        return deps._tool_cache[cache_key]
    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"Invalid regex pattern: {e}"

    if file_glob:
        tree = await deps.get_file_tree()
        paths = [
            e["path"] for e in tree
            if e["type"] == "blob" and fnmatch.fnmatch(e["path"], file_glob)
        ]
    elif deps.changed_files:
        paths = list(deps.changed_files)
    else:
        tree = await deps.get_file_tree()
        paths = [e["path"] for e in tree if e["type"] == "blob"]

    changed_set = set(deps.changed_files)

    matches: list[str] = []
    for path in paths:
        if len(matches) >= max_results:
            break
        try:
            raw = await deps.provider.get_file_content(
                deps.http_client, deps.token,
                deps.owner, deps.repo, path, deps.head_sha,
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
    deps._tool_cache[cache_key] = result
    return result


async def list_files(
    ctx: RunContext[ChatDeps],
    path_prefix: str | None = None,
    glob: str | None = None,
    offset: int = 0,
    limit: int = 200,
) -> str:
    """List files in the repository tree.

    Files changed in this PR are marked with [CHANGED].

    Args:
        path_prefix: Filter to files under this directory prefix (e.g. "src/auth").
        glob: Filter by glob pattern (e.g. "*.py", "src/**/*.ts").
        offset: Skip this many results (for pagination if repo has many files).
        limit: Maximum number of paths to return (default 200).
    """
    deps = ctx.deps
    tree = await deps.get_file_tree()
    changed_set = set(deps.changed_files)
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
    return f"{len(paths)} file(s):\n" + "\n".join(paths) + truncated


async def _read_single_file(
    deps: ChatDeps,
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    """Read a single file, with caching, prompt-file short-circuit, and diff appending."""
    if path in deps.prompt_files and not start_line and not end_line:
        return f"{path}: This file's full content is already included in your prompt context above. Refer to it there."

    cache_key = f"read:{path}:{start_line}:{end_line}"
    if cache_key in deps._tool_cache:
        return deps._tool_cache[cache_key]

    try:
        raw = await deps.provider.get_file_content(
            deps.http_client, deps.token,
            deps.owner, deps.repo, path, deps.head_sha,
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

    patch = deps.file_patches.get(path)
    if patch:
        result += f"\n\n--- PR diff for {path} ---\n```diff\n{patch}\n```"

    deps._tool_cache[cache_key] = result
    return result


async def read_file(
    ctx: RunContext[ChatDeps],
    path: str,
    paths: list[str] | None = None,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    """Read file content from the repository at PR HEAD.

    Can read a single file or multiple files in one call. When you need to
    check several files, pass them all at once via the paths parameter to
    save tool calls.

    Args:
        path: File path relative to repo root (for single file).
        paths: List of file paths to read in one call (for multiple files).
        start_line: Optional 1-indexed start line (only for single file).
        end_line: Optional 1-indexed end line inclusive (only for single file).
    """
    all_paths = paths or [path]
    if len(all_paths) == 1:
        return await _read_single_file(ctx.deps, all_paths[0], start_line, end_line)

    results = []
    for p in all_paths:
        results.append(await _read_single_file(ctx.deps, p))
    return "\n\n---\n\n".join(results)


CODEBASE_TOOLS: list[Tool] = [
    Tool(search_annotations),
    Tool(grep_codebase),
    Tool(list_files),
    Tool(read_file),
]

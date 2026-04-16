"""Server-side annotation generation — lite (forge API) and full (clone) modes."""

from __future__ import annotations

import asyncio
import fnmatch
import json
import logging
import subprocess
import tempfile
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from specmap.config import (
    SPEC_EXCLUDE_DIRS,
    SPEC_EXCLUDE_FILENAMES,
    CoreConfig,
)
from specmap.indexer.code_analyzer import CodeChange
from specmap.indexer.mapper import Mapper
from specmap.llm.client import LLMClient

logger = logging.getLogger("specmap.server")

_DEFAULT_SPEC_PATTERNS = ["**/*.md"]
_MAX_SPEC_FILES = 20
_MAX_CHANGED_FILES = 50
_MAX_FILE_SIZE = 100_000  # 100KB
_CLONE_TIMEOUT = 60
_ANNOTATE_TIMEOUT = 300


async def generate_lite(
    provider,
    client,
    token: str,
    owner: str,
    repo: str,
    pr_files: list[dict],
    head_sha: str,
    head_branch: str,
    base_branch: str,
    config: CoreConfig,
    annotate_timeout: int = _ANNOTATE_TIMEOUT,
    on_progress: Callable[[dict], Awaitable[None]] | None = None,
    exclude_files: set[str] | None = None,
    concurrency: int = 1,
) -> dict:
    """Generate annotations using forge APIs + LLM (no git clone)."""
    from specmap.server.forge import ForgeNotFound

    # 1. Load remote config for spec/ignore patterns
    spec_patterns = list(_DEFAULT_SPEC_PATTERNS)
    ignore_patterns: list[str] = []
    try:
        config_raw = await provider.get_file_content(
            client, token, owner, repo, ".specmap/config.json", head_sha
        )
        config_data = json.loads(config_raw)
        if isinstance(config_data.get("spec_patterns"), list):
            spec_patterns = config_data["spec_patterns"]
        if isinstance(config_data.get("ignore_patterns"), list):
            ignore_patterns = config_data["ignore_patterns"]
    except (ForgeNotFound, json.JSONDecodeError, UnicodeDecodeError):
        pass

    # 2. Discover spec files via tree listing
    tree = await provider.list_tree(client, token, owner, repo, head_sha)
    spec_paths = _filter_spec_paths(tree, spec_patterns, ignore_patterns)
    spec_paths = spec_paths[:_MAX_SPEC_FILES]

    if not spec_paths:
        return _build_result(head_branch, base_branch, head_sha, [])

    # 3. Fetch spec contents
    spec_contents: dict[str, str] = {}
    for sp in spec_paths:
        try:
            raw = await provider.get_file_content(
                client, token, owner, repo, sp, head_sha
            )
            spec_contents[sp] = raw.decode("utf-8", errors="replace")
        except (ForgeNotFound, Exception):
            pass

    if not spec_contents:
        return _build_result(head_branch, base_branch, head_sha, [])

    # 4. Build code changes from PR files
    changes: list[CodeChange] = []
    for f in pr_files[:_MAX_CHANGED_FILES]:
        if f["status"] == "removed":
            continue
        if _is_ignored(f["filename"], ignore_patterns):
            continue
        try:
            raw = await provider.get_file_content(
                client, token, owner, repo, f["filename"], head_sha
            )
            if len(raw) > _MAX_FILE_SIZE:
                continue
            text = raw.decode("utf-8", errors="replace")
            lines = text.splitlines()
            changes.append(CodeChange(
                file_path=f["filename"],
                start_line=1,
                end_line=len(lines),
                change_type=f["status"],
                content=text,
            ))
        except Exception:
            continue

    # Filter out files already annotated (resume support)
    if exclude_files:
        changes = [c for c in changes if c.file_path not in exclude_files]

    if not changes:
        return _build_result(head_branch, base_branch, head_sha, [])

    # 5. Call Mapper
    if on_progress:
        await on_progress({"phase": "annotating", "detail": "Annotating code changes..."})

    async def _batch_progress(batch: int, total: int) -> None:
        if on_progress:
            await on_progress({"phase": "annotating", "batch": batch, "total_batches": total})

    llm_client = LLMClient(config)
    mapper = Mapper(llm_client, repo_root="")
    deadline = time.monotonic() + annotate_timeout
    annotations = await mapper.annotate_changes(
        changes, spec_contents, batch_token_budget=8000,
        on_progress=_batch_progress,
        deadline=deadline,
        concurrency=concurrency,
    )

    # 6. Build result
    ann_dicts = _annotations_to_dicts(annotations)
    result = _build_result(head_branch, base_branch, head_sha, ann_dicts)

    # Detect partial completion
    if mapper.completed_batches < mapper.total_batches:
        if not annotations:
            raise TimeoutError("Annotation generation timed out with no completed batches")
        result["partial"] = True
        result["completed_batches"] = mapper.completed_batches
        result["total_batches"] = mapper.total_batches

    return result


async def generate_full(
    provider,
    client,
    token: str,
    owner: str,
    repo: str,
    pr_files: list[dict],
    head_sha: str,
    head_branch: str,
    base_branch: str,
    config: CoreConfig,
    pr_title: str = "",
    annotate_timeout: int = _ANNOTATE_TIMEOUT,
    on_progress: Callable[[dict], Awaitable[None]] | None = None,
    exclude_files: set[str] | None = None,
    concurrency: int = 1,
) -> dict:
    """Generate annotations by cloning repo and running the full annotate() pipeline."""
    clone = provider.clone_url(owner, repo, token)

    with tempfile.TemporaryDirectory(prefix="specmap-gen-") as tmpdir:
        # 1. Shallow clone
        if on_progress:
            await on_progress({"phase": "cloning", "detail": "Cloning repository..."})
        await asyncio.wait_for(
            asyncio.to_thread(
                _clone_repo, clone, head_branch, tmpdir
            ),
            timeout=_CLONE_TIMEOUT,
        )

        # 2. LLM context pre-pass
        if on_progress:
            await on_progress({"phase": "context", "detail": "Analyzing PR context..."})
        context = await _generate_context(
            LLMClient(config), pr_title, head_branch, base_branch, pr_files
        )

        # 3. Extract changed filenames (only existing files, skip removed)
        changed_files = [
            f["filename"]
            for f in pr_files[:_MAX_CHANGED_FILES]
            if f["status"] != "removed"
        ]

        # 4. Call annotate() with timeout
        from specmap.tools.annotate import annotate

        if on_progress:
            await on_progress({"phase": "annotating", "detail": "Annotating code changes..."})

        async def _batch_progress(batch: int, total: int) -> None:
            if on_progress:
                await on_progress({"phase": "annotating", "batch": batch, "total_batches": total})

        deadline = time.monotonic() + annotate_timeout
        ann_result = await annotate(
            repo_root=tmpdir,
            code_changes=changed_files if changed_files else None,
            branch=head_branch,
            context=context,
            on_progress=_batch_progress,
            deadline=deadline,
            exclude_files=exclude_files,
            concurrency=concurrency,
            config=config,
        )

        # 5. Read result
        from specmap.state.specmap_file import SpecmapFileManager

        file_mgr = SpecmapFileManager(tmpdir)
        specmap = file_mgr.load(head_branch)

        # 6. Serialize
        data = json.loads(specmap.model_dump_json())
        data["updated_by"] = "server:generate"

        # Propagate partial flags from annotate result
        if ann_result.get("partial"):
            data["partial"] = True
            data["completed_batches"] = ann_result["completed_batches"]
            data["total_batches"] = ann_result["total_batches"]

        return data


async def _generate_context(
    llm_client: LLMClient,
    pr_title: str,
    head_branch: str,
    base_branch: str,
    pr_files: list[dict],
) -> str:
    """LLM pre-pass to generate a context summary for the PR."""
    file_summaries = []
    for f in pr_files[:30]:
        patch = f.get("patch", "")
        # Truncate patch to first 50 lines
        patch_lines = patch.splitlines()[:50]
        snippet = "\n".join(patch_lines)
        file_summaries.append(f"### {f['filename']} ({f['status']})\n```\n{snippet}\n```")

    files_text = "\n\n".join(file_summaries)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a code reviewer. Summarize the intent and key design decisions "
                "in a pull request. Be concise: 2-4 paragraphs."
            ),
        },
        {
            "role": "user",
            "content": (
                f"PR Title: {pr_title}\n"
                f"Branch: {head_branch} → {base_branch}\n\n"
                f"Changed files:\n\n{files_text}"
            ),
        },
    ]

    try:
        result = await llm_client.complete(messages)
        return str(result)
    except Exception as e:
        logger.warning("Context pre-pass failed: %s", e)
        return ""


def _clone_repo(clone_url: str, branch: str, dest: str) -> None:
    """Shallow clone a repo branch into dest."""
    result = subprocess.run(
        ["git", "clone", "--depth=1", f"--branch={branch}", clone_url, dest],
        capture_output=True,
        text=True,
        timeout=_CLONE_TIMEOUT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git clone failed: {result.stderr.strip()}")


def _filter_spec_paths(
    tree: list[dict],
    spec_patterns: list[str],
    ignore_patterns: list[str],
) -> list[str]:
    """Filter tree entries to find spec files."""
    result: list[str] = []
    for entry in tree:
        if entry["type"] != "blob":
            continue
        path = entry["path"]
        # Check against spec patterns
        if not any(fnmatch.fnmatch(path, pat) for pat in spec_patterns):
            continue
        # Exclude dirs
        parts = path.split("/")
        if any(part in SPEC_EXCLUDE_DIRS for part in parts[:-1]):
            continue
        # Exclude filenames
        filename = parts[-1]
        if filename in SPEC_EXCLUDE_FILENAMES:
            continue
        # Ignore patterns
        if _is_ignored(path, ignore_patterns):
            continue
        result.append(path)
    return result


def _is_ignored(file_path: str, ignore_patterns: list[str]) -> bool:
    """Check if a file path matches any ignore pattern."""
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(file_path, pattern):
            return True
    return False


def _annotations_to_dicts(annotations) -> list[dict]:
    """Convert Annotation models to dicts for JSON response."""
    result = []
    for ann in annotations:
        refs = []
        for ref in ann.refs:
            refs.append({
                "id": ref.id,
                "spec_file": ref.spec_file,
                "heading": ref.heading,
                "start_line": ref.start_line,
                "excerpt": ref.excerpt,
            })
        result.append({
            "id": ann.id,
            "file": ann.file,
            "start_line": ann.start_line,
            "end_line": ann.end_line,
            "description": ann.description,
            "refs": refs,
            "created_at": ann.created_at.isoformat() if hasattr(ann.created_at, "isoformat") else str(ann.created_at),
            "code_hash": ann.code_hash,
        })
    return result


def _build_result(
    branch: str, base_branch: str, head_sha: str, annotations: list[dict]
) -> dict:
    """Build a specmap-format response dict."""
    return {
        "version": 2,
        "branch": branch,
        "base_branch": base_branch,
        "head_sha": head_sha,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "updated_by": "server:generate",
        "annotations": annotations,
        "ignore_patterns": [],
    }

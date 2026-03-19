"""Core mapping tool: map code changes to spec documents."""

from __future__ import annotations

import fnmatch
import sys
from pathlib import Path

from specmap.config import SpecmapConfig, SPEC_EXCLUDE_FILENAMES, SPEC_EXCLUDE_DIRS
from specmap.indexer.code_analyzer import CodeAnalyzer
from specmap.indexer.mapper import Mapper
from specmap.indexer.spec_parser import SpecParser
from specmap.llm.client import LLMClient
from specmap.state.models import SpecmapFile
from specmap.state.specmap_file import SpecmapFileManager


async def map_code_to_spec(
    repo_root: str,
    code_changes: list[str] | None = None,
    spec_files: list[str] | None = None,
    branch: str | None = None,
) -> dict:
    """Map code changes to spec documents.

    Args:
        repo_root: Path to the repository root
        code_changes: Specific file paths to analyze (None = auto-detect from git diff)
        spec_files: Specific spec files to use (None = auto-discover)
        branch: Branch name (None = auto-detect)

    Returns:
        Summary dict with mappings created/updated and coverage info
    """
    config = SpecmapConfig.load(repo_root)
    file_mgr = SpecmapFileManager(repo_root)
    analyzer = CodeAnalyzer()
    parser = SpecParser()

    # 1. Load or create SpecmapFile
    if branch is None:
        branch = file_mgr.get_branch()
    specmap = file_mgr.load(branch)
    specmap.branch = branch
    specmap.base_branch = file_mgr.get_base_branch()
    specmap.ignore_patterns = config.ignore_patterns

    # 2. Auto-discover spec files if not provided
    if spec_files is None:
        spec_files = _discover_spec_files(repo_root, config)

    if not spec_files:
        return {"status": "no_specs", "message": "No spec files found", "mappings_created": 0}

    # 3. Parse all spec documents
    spec_docs = {}
    spec_contents = {}
    for sf in spec_files:
        content = _read_file(repo_root, sf)
        if content is not None:
            spec_contents[sf] = content
            spec_docs[sf] = parser.parse(content, sf)

    # Update spec_documents in specmap
    specmap.spec_documents = spec_docs

    # 4. Get code changes
    if code_changes is not None:
        # Get diff for specific files
        changes = []
        for fp in code_changes:
            file_content = analyzer.get_file_content(repo_root, fp)
            if file_content:
                from specmap.indexer.code_analyzer import CodeChange

                changes.append(CodeChange(
                    file_path=fp,
                    start_line=1,
                    end_line=len(file_content.splitlines()),
                    change_type="modified",
                    content=file_content,
                ))
    else:
        changes = analyzer.get_changed_files(repo_root, specmap.base_branch)

    # Filter out ignored files
    changes = [c for c in changes if not _is_ignored(c.file_path, config.ignore_patterns)]

    if not changes:
        file_mgr.save(specmap)
        return {
            "status": "no_changes",
            "message": "No code changes to map",
            "mappings_created": 0,
            "spec_files": len(spec_files),
        }

    # 5. Call Mapper
    llm_client = LLMClient(config)
    mapper = Mapper(llm_client, repo_root)
    new_mappings = await mapper.map_changes_to_specs(changes, spec_docs, spec_contents)

    # 6. Merge new mappings with existing
    existing_count = len(specmap.mappings)
    _merge_mappings(specmap, new_mappings)
    created = len(specmap.mappings) - existing_count
    updated = len(new_mappings) - created

    # 7. Save
    file_mgr.save(specmap)

    # 8. Return summary
    usage = llm_client.get_usage()
    return {
        "status": "ok",
        "mappings_created": max(0, created),
        "mappings_updated": max(0, updated),
        "total_mappings": len(specmap.mappings),
        "spec_files_parsed": len(spec_docs),
        "code_changes_analyzed": len(changes),
        "llm_usage": usage,
        "branch": branch,
    }


def _discover_spec_files(repo_root: str, config: SpecmapConfig) -> list[str]:
    """Scan for spec files matching patterns, excluding common non-spec patterns."""
    found: list[str] = []
    root = Path(repo_root)

    for pattern in config.spec_patterns:
        for match in root.glob(pattern):
            if not match.is_file():
                continue

            rel_path = str(match.relative_to(root))

            # Skip excluded directories
            parts = match.relative_to(root).parts
            if any(part in SPEC_EXCLUDE_DIRS for part in parts):
                continue

            # Skip excluded filenames
            if match.name in SPEC_EXCLUDE_FILENAMES:
                continue

            # Skip ignored patterns
            if _is_ignored(rel_path, config.ignore_patterns):
                continue

            if rel_path not in found:
                found.append(rel_path)

    return sorted(found)


def _read_file(repo_root: str, file_path: str) -> str | None:
    """Read a file from the repo."""
    try:
        return (Path(repo_root) / file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _is_ignored(file_path: str, ignore_patterns: list[str]) -> bool:
    """Check if a file path matches any ignore pattern."""
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(file_path, pattern):
            return True
    return False


def _merge_mappings(specmap: SpecmapFile, new_mappings: list) -> None:
    """Merge new mappings with existing ones.

    Update if same code target file + lines, add if new.
    """
    existing_by_target: dict[str, int] = {}
    for i, m in enumerate(specmap.mappings):
        key = f"{m.code_target.file}:{m.code_target.start_line}-{m.code_target.end_line}"
        existing_by_target[key] = i

    for new_m in new_mappings:
        key = f"{new_m.code_target.file}:{new_m.code_target.start_line}-{new_m.code_target.end_line}"
        if key in existing_by_target:
            idx = existing_by_target[key]
            # Preserve original ID and creation time
            new_m = new_m.model_copy(update={
                "id": specmap.mappings[idx].id,
                "created_at": specmap.mappings[idx].created_at,
            })
            specmap.mappings[idx] = new_m
        else:
            specmap.mappings.append(new_m)

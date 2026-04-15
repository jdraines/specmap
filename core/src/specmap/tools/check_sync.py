"""Verify existing annotations are still valid (line ranges exist in code)."""

from __future__ import annotations

from pathlib import Path

from specmap.indexer.hasher import hash_code_lines
from specmap.state.specmap_file import SpecmapFileManager


async def check_sync(
    repo_root: str,
    branch: str | None = None,
    files: list[str] | None = None,
) -> dict:
    """Verify existing annotations are still valid.

    Checks that annotated line ranges still exist in the code files.
    Also computes per-annotation staleness based on code_hash.

    Args:
        repo_root: Path to the repository root
        branch: Branch name (None = auto-detect)
        files: Specific files to check (None = check all)

    Returns:
        Summary with valid/invalid counts and staleness breakdown
    """
    file_mgr = SpecmapFileManager(repo_root)

    if branch is None:
        branch = file_mgr.get_branch()
    specmap = file_mgr.load(branch)

    if not specmap.annotations:
        return {
            "status": "ok",
            "valid": 0,
            "invalid": 0,
            "total": 0,
            "message": "No annotations to check",
            "staleness": {"fresh": 0, "stale": 0, "unknown": 0, "missing": 0},
        }

    # Filter annotations to check
    annotations_to_check = specmap.annotations
    if files:
        annotations_to_check = [
            a for a in annotations_to_check if a.file in files
        ]

    valid_count = 0
    invalid_count = 0
    invalid_details: list[dict] = []

    # Cache file line counts and contents
    line_count_cache: dict[str, int | None] = {}
    file_content_cache: dict[str, str | None] = {}

    # Staleness counters
    staleness_counts = {"fresh": 0, "stale": 0, "unknown": 0, "missing": 0}

    for ann in annotations_to_check:
        line_count = _get_line_count(repo_root, ann.file, line_count_cache)

        if line_count is None:
            invalid_count += 1
            invalid_details.append({
                "annotation_id": ann.id,
                "file": ann.file,
                "lines": f"{ann.start_line}-{ann.end_line}",
                "reason": "file not found",
                "staleness": "missing",
            })
            staleness_counts["missing"] += 1
            ann.staleness = "missing"
            continue

        if ann.start_line < 1 or ann.end_line > line_count or ann.start_line > ann.end_line:
            invalid_count += 1
            invalid_details.append({
                "annotation_id": ann.id,
                "file": ann.file,
                "lines": f"{ann.start_line}-{ann.end_line}",
                "reason": f"line range out of bounds (file has {line_count} lines)",
                "staleness": "stale",
            })
            staleness_counts["stale"] += 1
            ann.staleness = "stale"
            continue

        valid_count += 1

        # Compute staleness from code_hash
        if not ann.code_hash:
            staleness_counts["unknown"] += 1
            ann.staleness = "unknown"
        else:
            content = _get_file_content(repo_root, ann.file, file_content_cache)
            if content is not None:
                try:
                    current_hash = hash_code_lines(content, ann.start_line, ann.end_line)
                    if current_hash == ann.code_hash:
                        staleness_counts["fresh"] += 1
                        ann.staleness = "fresh"
                    else:
                        staleness_counts["stale"] += 1
                        ann.staleness = "stale"
                except (IndexError, ValueError):
                    staleness_counts["stale"] += 1
                    ann.staleness = "stale"
            else:
                staleness_counts["missing"] += 1
                ann.staleness = "missing"

    return {
        "status": "ok",
        "valid": valid_count,
        "invalid": invalid_count,
        "total": len(annotations_to_check),
        "invalid_details": invalid_details,
        "staleness": staleness_counts,
    }


def _get_line_count(
    repo_root: str, file_path: str, cache: dict[str, int | None]
) -> int | None:
    """Get the number of lines in a file, with caching."""
    if file_path not in cache:
        full_path = Path(repo_root) / file_path
        try:
            content = full_path.read_text(encoding="utf-8")
            lines = content.split("\n")
            if lines and lines[-1] == "":
                lines = lines[:-1]
            cache[file_path] = len(lines)
        except (OSError, UnicodeDecodeError):
            cache[file_path] = None

    return cache[file_path]


def _get_file_content(
    repo_root: str, file_path: str, cache: dict[str, str | None]
) -> str | None:
    """Read file content with caching."""
    if file_path not in cache:
        full_path = Path(repo_root) / file_path
        try:
            cache[file_path] = full_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            cache[file_path] = None
    return cache[file_path]

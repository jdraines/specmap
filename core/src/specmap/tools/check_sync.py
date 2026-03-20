"""Verify existing annotations are still valid (line ranges exist in code)."""

from __future__ import annotations

from pathlib import Path

from specmap.state.specmap_file import SpecmapFileManager


async def check_sync(
    repo_root: str,
    branch: str | None = None,
    files: list[str] | None = None,
) -> dict:
    """Verify existing annotations are still valid.

    Checks that annotated line ranges still exist in the code files.
    No hash checks — just validates that the referenced lines are in bounds.

    Args:
        repo_root: Path to the repository root
        branch: Branch name (None = auto-detect)
        files: Specific files to check (None = check all)

    Returns:
        Summary with valid and invalid counts
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

    # Cache file line counts
    line_count_cache: dict[str, int | None] = {}

    for ann in annotations_to_check:
        line_count = _get_line_count(repo_root, ann.file, line_count_cache)

        if line_count is None:
            invalid_count += 1
            invalid_details.append({
                "annotation_id": ann.id,
                "file": ann.file,
                "lines": f"{ann.start_line}-{ann.end_line}",
                "reason": "file not found",
            })
            continue

        if ann.start_line < 1 or ann.end_line > line_count or ann.start_line > ann.end_line:
            invalid_count += 1
            invalid_details.append({
                "annotation_id": ann.id,
                "file": ann.file,
                "lines": f"{ann.start_line}-{ann.end_line}",
                "reason": f"line range out of bounds (file has {line_count} lines)",
            })
            continue

        valid_count += 1

    return {
        "status": "ok",
        "valid": valid_count,
        "invalid": invalid_count,
        "total": len(annotations_to_check),
        "invalid_details": invalid_details,
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

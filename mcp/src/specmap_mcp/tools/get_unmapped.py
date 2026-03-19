"""Find code changes without spec coverage."""

from __future__ import annotations

from specmap_mcp.config import SpecmapConfig
from specmap_mcp.indexer.code_analyzer import CodeAnalyzer
from specmap_mcp.state.specmap_file import SpecmapFileManager


async def get_unmapped_changes(
    repo_root: str,
    branch: str | None = None,
    base_branch: str | None = None,
    threshold: float | None = None,
) -> dict:
    """Find code changes without spec coverage.

    Args:
        repo_root: Path to the repository root
        branch: Branch name (None = auto-detect)
        base_branch: Base branch for diff (None = auto-detect)
        threshold: Minimum coverage ratio (0.0-1.0) to report (None = report all)

    Returns:
        Unmapped ranges, per-file and overall coverage percentages
    """
    config = SpecmapConfig.load(repo_root)
    file_mgr = SpecmapFileManager(repo_root)
    analyzer = CodeAnalyzer()

    if branch is None:
        branch = file_mgr.get_branch()
    specmap = file_mgr.load(branch)

    if base_branch is None:
        base_branch = specmap.base_branch or file_mgr.get_base_branch()

    # Get all changed lines from git diff
    changes = analyzer.get_changed_files(repo_root, base_branch)
    if not changes:
        return {
            "status": "ok",
            "overall_coverage": 1.0,
            "total_changed_lines": 0,
            "mapped_lines": 0,
            "unmapped_lines": 0,
            "files": {},
            "message": "No code changes found",
        }

    # Build a set of all changed lines per file
    changed_lines_per_file: dict[str, set[int]] = {}
    for change in changes:
        lines = changed_lines_per_file.setdefault(change.file_path, set())
        for line_no in range(change.start_line, change.end_line + 1):
            lines.add(line_no)

    # Build a set of all mapped lines per file
    mapped_lines_per_file: dict[str, set[int]] = {}
    for mapping in specmap.mappings:
        if mapping.stale:
            continue
        target = mapping.code_target
        lines = mapped_lines_per_file.setdefault(target.file, set())
        for line_no in range(target.start_line, target.end_line + 1):
            lines.add(line_no)

    # Calculate coverage per file
    file_results: dict[str, dict] = {}
    total_changed = 0
    total_mapped = 0

    for file_path, changed in changed_lines_per_file.items():
        mapped = mapped_lines_per_file.get(file_path, set())
        covered = changed & mapped
        uncovered = changed - mapped

        file_changed = len(changed)
        file_covered = len(covered)
        file_coverage = file_covered / file_changed if file_changed > 0 else 1.0

        total_changed += file_changed
        total_mapped += file_covered

        # Build unmapped ranges
        unmapped_ranges = _lines_to_ranges(sorted(uncovered))

        if threshold is not None and file_coverage >= threshold:
            continue

        file_results[file_path] = {
            "changed_lines": file_changed,
            "mapped_lines": file_covered,
            "unmapped_lines": len(uncovered),
            "coverage": round(file_coverage, 3),
            "unmapped_ranges": unmapped_ranges,
        }

    overall_coverage = total_mapped / total_changed if total_changed > 0 else 1.0

    return {
        "status": "ok",
        "overall_coverage": round(overall_coverage, 3),
        "total_changed_lines": total_changed,
        "mapped_lines": total_mapped,
        "unmapped_lines": total_changed - total_mapped,
        "files": file_results,
    }


def _lines_to_ranges(lines: list[int]) -> list[dict]:
    """Convert a sorted list of line numbers to ranges."""
    if not lines:
        return []

    ranges = []
    start = lines[0]
    end = lines[0]

    for line in lines[1:]:
        if line == end + 1:
            end = line
        else:
            ranges.append({"start": start, "end": end})
            start = line
            end = line

    ranges.append({"start": start, "end": end})
    return ranges

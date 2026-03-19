"""Verify existing mappings are still valid."""

from __future__ import annotations

from pathlib import Path

from specmap_mcp.config import SpecmapConfig
from specmap_mcp.indexer.hasher import hash_code_lines, hash_span
from specmap_mcp.state.models import Mapping
from specmap_mcp.state.relocator import Relocator
from specmap_mcp.state.specmap_file import SpecmapFileManager


async def check_sync(
    repo_root: str,
    branch: str | None = None,
    files: list[str] | None = None,
) -> dict:
    """Verify existing mappings are still valid.

    Args:
        repo_root: Path to the repository root
        branch: Branch name (None = auto-detect)
        files: Specific files to check (None = check all)

    Returns:
        Summary with valid, relocated, and stale counts
    """
    config = SpecmapConfig.load(repo_root)
    file_mgr = SpecmapFileManager(repo_root)
    relocator = Relocator()

    if branch is None:
        branch = file_mgr.get_branch()
    specmap = file_mgr.load(branch)

    if not specmap.mappings:
        return {
            "status": "ok",
            "valid": 0,
            "relocated": 0,
            "stale": 0,
            "total": 0,
            "message": "No mappings to check",
        }

    # Filter mappings to check
    mappings_to_check = specmap.mappings
    if files:
        mappings_to_check = [
            m for m in mappings_to_check if m.code_target.file in files
        ]

    valid_mappings: list[Mapping] = []
    needs_relocation: list[Mapping] = []
    stale_details: list[dict] = []

    # Cache file contents and spec contents
    file_cache: dict[str, str | None] = {}
    spec_cache: dict[str, str | None] = {}

    for mapping in mappings_to_check:
        code_valid = _check_code_hash(mapping, repo_root, file_cache)
        spec_valid = _check_spec_hashes(mapping, repo_root, spec_cache)

        if code_valid and spec_valid:
            valid_mappings.append(mapping)
        else:
            needs_relocation.append(mapping)

    # Try to relocate
    relocated: list[Mapping] = []
    stale: list[Mapping] = []

    if needs_relocation:
        # Build old and new content maps for spec files
        # For relocation, we use the stored hashes as "old" reference
        # and current file content as "new"
        old_contents: dict[str, str] = {}
        new_contents: dict[str, str] = {}

        for mapping in needs_relocation:
            for span in mapping.spec_spans:
                if span.spec_file not in new_contents:
                    content = _read_spec(repo_root, span.spec_file)
                    if content is not None:
                        new_contents[span.spec_file] = content
                        # For old_contents, we use the same content but the relocator
                        # will check if the span text can be found at the original offset
                        old_contents[span.spec_file] = content

        relocated, stale = relocator.relocate_mappings(
            needs_relocation, old_contents, new_contents
        )

        for s in stale:
            stale_details.append({
                "mapping_id": s.id,
                "code_file": s.code_target.file,
                "code_lines": f"{s.code_target.start_line}-{s.code_target.end_line}",
                "spec_spans": [
                    f"{sp.spec_file} ({' > '.join(sp.heading_path)})"
                    for sp in s.spec_spans
                ],
            })

    # Update specmap with results
    checked_ids = {m.id for m in mappings_to_check}
    unchecked = [m for m in specmap.mappings if m.id not in checked_ids]
    specmap.mappings = unchecked + valid_mappings + relocated + stale

    file_mgr.save(specmap)

    return {
        "status": "ok",
        "valid": len(valid_mappings),
        "relocated": len(relocated),
        "stale": len(stale),
        "total": len(mappings_to_check),
        "stale_details": stale_details,
    }


def _check_code_hash(
    mapping: Mapping, repo_root: str, cache: dict[str, str | None]
) -> bool:
    """Check if code target hash still matches."""
    file_path = mapping.code_target.file
    if file_path not in cache:
        full_path = Path(repo_root) / file_path
        try:
            cache[file_path] = full_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            cache[file_path] = None

    content = cache[file_path]
    if content is None:
        return False

    current_hash = hash_code_lines(
        content, mapping.code_target.start_line, mapping.code_target.end_line
    )
    return current_hash == mapping.code_target.content_hash


def _check_spec_hashes(
    mapping: Mapping, repo_root: str, cache: dict[str, str | None]
) -> bool:
    """Check if all spec span hashes still match."""
    for span in mapping.spec_spans:
        if span.spec_file not in cache:
            cache[span.spec_file] = _read_spec(repo_root, span.spec_file)

        content = cache[span.spec_file]
        if content is None:
            return False

        current_hash = hash_span(content, span.span_offset, span.span_length)
        if current_hash != span.span_hash:
            return False

    return True


def _read_spec(repo_root: str, spec_file: str) -> str | None:
    """Read a spec file."""
    try:
        return (Path(repo_root) / spec_file).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

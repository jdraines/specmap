"""Core annotation tool: generate annotations for code changes with spec references."""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path

from specmap.config import SPEC_EXCLUDE_DIRS, SPEC_EXCLUDE_FILENAMES, SpecmapConfig
from specmap.indexer.code_analyzer import CodeAnalyzer
from specmap.indexer.diff_optimizer import (
    classify_annotations,
    parse_incremental_diff,
    reclassify_for_spec_changes,
    shift_annotations,
)
from specmap.indexer.hasher import hash_content
from specmap.indexer.mapper import Mapper
from specmap.llm.client import LLMClient
from specmap.state.specmap_file import SpecmapFileManager


async def annotate(
    repo_root: str,
    code_changes: list[str] | None = None,
    spec_files: list[str] | None = None,
    branch: str | None = None,
    context: str | None = None,
) -> dict:
    """Generate annotations for code changes with spec references.

    Args:
        repo_root: Path to the repository root
        code_changes: Specific file paths to analyze (None = auto-detect from git diff)
        spec_files: Specific spec files to use (None = auto-discover)
        branch: Branch name (None = auto-detect)
        context: Optional freeform context from the development session

    Returns:
        Summary dict with annotations created and coverage info
    """
    config = SpecmapConfig.load(repo_root)
    file_mgr = SpecmapFileManager(repo_root)
    analyzer = CodeAnalyzer()

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
        return {"status": "no_specs", "message": "No spec files found", "annotations_created": 0}

    # 3. Read spec contents
    spec_contents: dict[str, str] = {}
    for sf in spec_files:
        content = _read_file(repo_root, sf)
        if content is not None:
            spec_contents[sf] = content

    # 4. Check for incremental diff optimization
    current_head = _get_head_sha(repo_root)
    previous_head = specmap.head_sha

    if previous_head and specmap.annotations and code_changes is None:
        # Incremental mode: diff from previous head
        result = await _incremental_annotate(
            repo_root, config, specmap, analyzer, spec_contents,
            previous_head, current_head, file_mgr, context=context,
        )
        if result is not None:
            return result

    # 5. Full annotation mode (first push or no cache)
    if code_changes is not None:
        # Get changes for specific files
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
        specmap.head_sha = current_head
        file_mgr.save(specmap)
        return {
            "status": "no_changes",
            "message": "No code changes to annotate",
            "annotations_created": 0,
            "spec_files": len(spec_files),
        }

    # 6. Call Mapper
    llm_client = LLMClient(config)
    mapper = Mapper(llm_client, repo_root)
    new_annotations = await mapper.annotate_changes(changes, spec_contents, context=context)

    # 7. Merge new annotations with existing
    # Remove old annotations for files being re-annotated
    analyzed_files = {c.file_path for c in changes}
    existing_count = len(specmap.annotations)
    specmap.annotations = [
        a for a in specmap.annotations if a.file not in analyzed_files
    ]
    removed = existing_count - len(specmap.annotations)
    specmap.annotations.extend(new_annotations)
    created = len(new_annotations)
    updated = min(removed, created)

    # 8. Update head_sha and save
    specmap.head_sha = current_head
    file_mgr.save(specmap)

    # 9. Return summary
    usage = llm_client.get_usage()
    return {
        "status": "ok",
        "annotations_created": max(0, created),
        "annotations_updated": max(0, updated),
        "total_annotations": len(specmap.annotations),
        "spec_files_used": len(spec_contents),
        "code_changes_analyzed": len(changes),
        "llm_usage": usage,
        "branch": branch,
    }


async def _incremental_annotate(
    repo_root: str,
    config: SpecmapConfig,
    specmap,
    analyzer: CodeAnalyzer,
    spec_contents: dict[str, str],
    previous_head: str,
    current_head: str,
    file_mgr: SpecmapFileManager,
    context: str | None = None,
) -> dict | None:
    """Try incremental annotation using diff from previous head.

    Returns result dict on success, None if incremental mode is not possible.
    """
    diff_text = _get_incremental_diff(repo_root, previous_head, current_head)
    if diff_text is None:
        return None

    file_hunks = parse_incremental_diff(diff_text)

    if not file_hunks:
        # No changes since last annotation
        specmap.head_sha = current_head
        file_mgr.save(specmap)
        return {
            "status": "ok",
            "annotations_created": 0,
            "annotations_updated": 0,
            "total_annotations": len(specmap.annotations),
            "spec_files_used": len(spec_contents),
            "code_changes_analyzed": 0,
            "incremental": True,
            "branch": specmap.branch,
        }

    # Classify existing annotations
    classified = classify_annotations(specmap.annotations, file_hunks)

    # Detect spec files that changed between pushes — annotations citing
    # changed specs need regeneration even if their code didn't change.
    changed_specs = _detect_changed_specs(repo_root, previous_head, spec_contents)
    if changed_specs:
        classified = reclassify_for_spec_changes(classified, changed_specs)

    # Shift non-overlapping annotations mechanically
    shifted = shift_annotations(classified.shift, file_hunks)

    # Get changes for files that need regeneration
    changed_files = set()
    for ann in classified.regenerate:
        changed_files.add(ann.file)
    # Also include files with hunks but no existing annotations
    for fp in file_hunks:
        if not _is_ignored(fp, config.ignore_patterns):
            changed_files.add(fp)

    changes = []
    for fp in changed_files:
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

    # Filter ignored
    changes = [c for c in changes if not _is_ignored(c.file_path, config.ignore_patterns)]

    # Generate new annotations for changed files
    new_annotations: list = []
    llm_usage = {"total_input_tokens": 0, "total_output_tokens": 0, "total_calls": 0}
    if changes:
        llm_client = LLMClient(config)
        mapper = Mapper(llm_client, repo_root)
        new_annotations = await mapper.annotate_changes(changes, spec_contents, context=context)
        llm_usage = llm_client.get_usage()

    # Merge: keep + shifted + new (replacing regenerated)
    # Remove old annotations for files that were regenerated
    regenerated_files = {ann.file for ann in classified.regenerate}
    kept = [a for a in classified.keep if a.file not in regenerated_files]

    specmap.annotations = kept + shifted + new_annotations
    specmap.head_sha = current_head
    file_mgr.save(specmap)

    result = {
        "status": "ok",
        "annotations_created": len(new_annotations),
        "annotations_updated": 0,
        "annotations_kept": len(kept),
        "annotations_shifted": len(shifted),
        "annotations_regenerated": len(classified.regenerate),
        "total_annotations": len(specmap.annotations),
        "spec_files_used": len(spec_contents),
        "code_changes_analyzed": len(changes),
        "incremental": True,
        "llm_usage": llm_usage,
        "branch": specmap.branch,
    }
    if changed_specs:
        result["specs_changed"] = sorted(changed_specs)
    return result


def _get_head_sha(repo_root: str) -> str:
    """Get the current HEAD SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return ""


def _get_incremental_diff(repo_root: str, old_sha: str, new_sha: str) -> str | None:
    """Get diff between two commits. Returns None if git fails."""
    try:
        result = subprocess.run(
            ["git", "diff", f"{old_sha}..{new_sha}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout
    except FileNotFoundError:
        pass
    return None


def _detect_changed_specs(
    repo_root: str,
    previous_head: str,
    current_spec_contents: dict[str, str],
) -> set[str]:
    """Detect spec files that changed between previous_head and current working tree.

    Compares the hash of each spec file at previous_head (via git show) with its
    current content. Returns the set of spec file paths that differ.
    """
    changed: set[str] = set()

    for spec_file, current_content in current_spec_contents.items():
        old_content = _git_show_file(repo_root, previous_head, spec_file)
        if old_content is None:
            # File didn't exist at previous_head — it's new, but annotations
            # can't have refs to a spec that didn't exist, so skip.
            continue

        if hash_content(old_content) != hash_content(current_content):
            changed.add(spec_file)

    return changed


def _git_show_file(repo_root: str, commit: str, file_path: str) -> str | None:
    """Get file content at a specific commit via git show. Returns None on failure."""
    try:
        result = subprocess.run(
            ["git", "show", f"{commit}:{file_path}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout
    except FileNotFoundError:
        pass
    return None


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


def _merge_annotations(specmap, new_annotations: list) -> None:
    """Merge new annotations with existing ones.

    Update if same file + overlapping lines, add if new.
    """
    existing_by_target: dict[str, int] = {}
    for i, a in enumerate(specmap.annotations):
        key = f"{a.file}:{a.start_line}-{a.end_line}"
        existing_by_target[key] = i

    for new_a in new_annotations:
        key = f"{new_a.file}:{new_a.start_line}-{new_a.end_line}"
        if key in existing_by_target:
            idx = existing_by_target[key]
            # Preserve original ID and creation time
            new_a = new_a.model_copy(update={
                "id": specmap.annotations[idx].id,
                "created_at": specmap.annotations[idx].created_at,
            })
            specmap.annotations[idx] = new_a
        else:
            specmap.annotations.append(new_a)

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
from specmap.indexer.hasher import hash_code, hash_code_lines, hash_content
from specmap.indexer.mapper import Mapper
from specmap.llm.client import LLMClient
from specmap.state.models import Annotation
from specmap.state.specmap_file import SpecmapFileManager


async def annotate(
    repo_root: str,
    code_changes: list[str] | None = None,
    spec_files: list[str] | None = None,
    branch: str | None = None,
    context: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Generate annotations for code changes with spec references.

    Args:
        repo_root: Path to the repository root
        code_changes: Specific file paths to analyze (None = auto-detect from git diff)
        spec_files: Specific spec files to use (None = auto-discover)
        branch: Branch name (None = auto-detect)
        context: Optional freeform context from the development session
        dry_run: If True, run classification pipeline but skip LLM calls and saving

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
    specmap.base_branch = file_mgr.get_base_branch(config.base_branch)
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
            dry_run=dry_run,
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
        if not dry_run:
            specmap.head_sha = current_head
            file_mgr.save(specmap)
        return {
            "status": "no_changes",
            "message": "No code changes to annotate",
            "annotations_created": 0,
            "spec_files": len(spec_files),
        }

    # Dry-run: report what would be regenerated without calling LLM
    if dry_run:
        return {
            "dry_run": True,
            "would_regenerate": [c.file_path for c in changes],
            "would_keep": 0,
            "would_shift": 0,
            "files_analyzed": [c.file_path for c in changes],
            "spec_files_used": len(spec_contents),
            "branch": branch,
        }

    # 6. Call Mapper
    llm_client = LLMClient(config)
    mapper = Mapper(llm_client, repo_root)
    new_annotations = await mapper.annotate_changes(
        changes, spec_contents, context=context,
        batch_token_budget=config.batch_token_budget,
    )

    # Set staleness on newly generated annotations
    for ann in new_annotations:
        ann.staleness = "fresh"

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

    # 8. Backfill code hashes for legacy annotations, update head_sha, file hashes, and save
    _backfill_code_hashes(repo_root, specmap.annotations)
    specmap.head_sha = current_head
    specmap.file_hashes = _compute_file_hashes(repo_root, specmap.annotations)
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
    dry_run: bool = False,
) -> dict | None:
    """Try incremental annotation using diff from previous head.

    Returns result dict on success, None if incremental mode is not possible.
    """
    diff_text = _get_incremental_diff(repo_root, previous_head, current_head)
    if diff_text is None:
        return None

    file_hunks = parse_incremental_diff(diff_text)

    if not file_hunks:
        # No new commits — use working-tree diff for hunk-level optimization
        return await _working_tree_annotate(
            repo_root, config, specmap, analyzer, spec_contents,
            current_head, file_mgr, context=context, dry_run=dry_run,
        )

    # Classify existing annotations
    classified = classify_annotations(specmap.annotations, file_hunks)

    # Detect spec files that changed between pushes — annotations citing
    # changed specs need regeneration even if their code didn't change.
    changed_specs = _detect_changed_specs(repo_root, previous_head, spec_contents)
    if changed_specs:
        classified = reclassify_for_spec_changes(classified, changed_specs)

    # Further filter regenerate list using code_hash — if the annotation's
    # code region hash still matches current content, demote to keep
    classified = _filter_by_code_hash(repo_root, classified)

    # Shift non-overlapping annotations mechanically
    shifted = shift_annotations(classified.shift, file_hunks)

    # Set staleness on shifted annotations
    for ann in shifted:
        ann.staleness = "shifted"

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

    # Dry-run: report classification without calling LLM
    if dry_run:
        return {
            "dry_run": True,
            "would_keep": len(classified.keep),
            "would_shift": len(classified.shift),
            "would_regenerate": [
                {"id": a.id, "file": a.file, "lines": f"{a.start_line}-{a.end_line}"}
                for a in classified.regenerate
            ],
            "files_analyzed": sorted(changed_files),
            "spec_files_used": len(spec_contents),
            "incremental": True,
            "branch": specmap.branch,
        }

    # Generate new annotations for changed files
    new_annotations: list = []
    llm_usage = {"total_input_tokens": 0, "total_output_tokens": 0, "total_calls": 0}
    if changes:
        llm_client = LLMClient(config)
        mapper = Mapper(llm_client, repo_root)
        new_annotations = await mapper.annotate_changes(
            changes, spec_contents, context=context,
            batch_token_budget=config.batch_token_budget,
        )
        llm_usage = llm_client.get_usage()

    # Set staleness on newly generated annotations
    for ann in new_annotations:
        ann.staleness = "fresh"

    # Set staleness on kept annotations
    for ann in classified.keep:
        if ann.code_hash:
            ann.staleness = "fresh"

    # Merge: keep + shifted + new (replacing regenerated)
    # Remove old annotations for files that were regenerated
    regenerated_files = {ann.file for ann in classified.regenerate}
    kept = [a for a in classified.keep if a.file not in regenerated_files]

    specmap.annotations = kept + shifted + new_annotations
    _backfill_code_hashes(repo_root, specmap.annotations)
    specmap.head_sha = current_head
    specmap.file_hashes = _compute_file_hashes(repo_root, specmap.annotations)
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


async def _working_tree_annotate(
    repo_root: str,
    config: SpecmapConfig,
    specmap,
    analyzer: CodeAnalyzer,
    spec_contents: dict[str, str],
    current_head: str,
    file_mgr: SpecmapFileManager,
    context: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Handle working-tree changes using hunk-level optimization.

    When no new commits exist but files are dirty, use `git diff HEAD` to get
    uncommitted changes and feed them through the classify/shift/regenerate pipeline.
    Falls back to file-level dirty detection if git diff fails.
    """
    # Try hunk-level optimization via working-tree diff
    wt_diff = _get_working_tree_diff(repo_root, specmap)
    if wt_diff is not None:
        wt_hunks = parse_incremental_diff(wt_diff)
        if wt_hunks:
            # Classify against working-tree hunks
            classified = classify_annotations(specmap.annotations, wt_hunks)
            # Further filter using code_hash
            classified = _filter_by_code_hash(repo_root, classified)

            shifted = shift_annotations(classified.shift, wt_hunks)
            for ann in shifted:
                ann.staleness = "shifted"

            # Files needing regeneration
            changed_files = {ann.file for ann in classified.regenerate}
            for fp in wt_hunks:
                if not _is_ignored(fp, config.ignore_patterns):
                    changed_files.add(fp)

            if dry_run:
                return {
                    "dry_run": True,
                    "would_keep": len(classified.keep),
                    "would_shift": len(classified.shift),
                    "would_regenerate": [
                        {"id": a.id, "file": a.file, "lines": f"{a.start_line}-{a.end_line}"}
                        for a in classified.regenerate
                    ],
                    "files_analyzed": sorted(changed_files),
                    "spec_files_used": len(spec_contents),
                    "incremental": True,
                    "working_tree": True,
                    "branch": specmap.branch,
                }

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
            changes = [c for c in changes if not _is_ignored(c.file_path, config.ignore_patterns)]

            new_annotations: list = []
            llm_usage = {"total_input_tokens": 0, "total_output_tokens": 0, "total_calls": 0}
            if changes:
                llm_client = LLMClient(config)
                mapper = Mapper(llm_client, repo_root)
                new_annotations = await mapper.annotate_changes(
                    changes, spec_contents, context=context,
                    batch_token_budget=config.batch_token_budget,
                )
                llm_usage = llm_client.get_usage()

            for ann in new_annotations:
                ann.staleness = "fresh"
            for ann in classified.keep:
                if ann.code_hash:
                    ann.staleness = "fresh"

            regenerated_files = {ann.file for ann in classified.regenerate}
            kept = [a for a in classified.keep if a.file not in regenerated_files]

            specmap.annotations = kept + shifted + new_annotations
            _backfill_code_hashes(repo_root, specmap.annotations)
            specmap.head_sha = current_head
            specmap.file_hashes = _compute_file_hashes(repo_root, specmap.annotations)
            file_mgr.save(specmap)

            return {
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
                "working_tree": True,
                "llm_usage": llm_usage,
                "branch": specmap.branch,
            }

    # Fallback: file-level dirty detection via hashes
    stale = _find_stale_annotations(repo_root, specmap)
    if not stale:
        if not dry_run:
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

    # Collect files containing stale annotations
    stale_files = {ann.file for ann in stale}

    if dry_run:
        return {
            "dry_run": True,
            "would_keep": len(specmap.annotations) - len(stale),
            "would_shift": 0,
            "would_regenerate": [
                {"id": a.id, "file": a.file, "lines": f"{a.start_line}-{a.end_line}"}
                for a in stale
            ],
            "files_analyzed": sorted(stale_files),
            "spec_files_used": len(spec_contents),
            "incremental": True,
            "branch": specmap.branch,
        }

    dirty_changes = []
    for fp in stale_files:
        if _is_ignored(fp, config.ignore_patterns):
            continue
        file_content = analyzer.get_file_content(repo_root, fp)
        if file_content:
            from specmap.indexer.code_analyzer import CodeChange
            dirty_changes.append(CodeChange(
                file_path=fp,
                start_line=1,
                end_line=len(file_content.splitlines()),
                change_type="modified",
                content=file_content,
            ))

    if not dirty_changes:
        specmap.head_sha = current_head
        specmap.file_hashes = _compute_file_hashes(repo_root, specmap.annotations)
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

    # Generate new annotations for files with stale annotations
    llm_client = LLMClient(config)
    mapper = Mapper(llm_client, repo_root)
    new_annotations = await mapper.annotate_changes(
        dirty_changes, spec_contents, context=context,
        batch_token_budget=config.batch_token_budget,
    )

    for ann in new_annotations:
        ann.staleness = "fresh"

    # Merge: remove old annotations for dirty files, add new ones
    dirty_set = {c.file_path for c in dirty_changes}
    specmap.annotations = [a for a in specmap.annotations if a.file not in dirty_set]
    specmap.annotations.extend(new_annotations)

    _backfill_code_hashes(repo_root, specmap.annotations)
    specmap.head_sha = current_head
    specmap.file_hashes = _compute_file_hashes(repo_root, specmap.annotations)
    file_mgr.save(specmap)

    return {
        "status": "ok",
        "annotations_created": len(new_annotations),
        "annotations_updated": 0,
        "total_annotations": len(specmap.annotations),
        "spec_files_used": len(spec_contents),
        "code_changes_analyzed": len(dirty_changes),
        "incremental": True,
        "dirty_files": sorted(dirty_set),
        "llm_usage": llm_client.get_usage(),
        "branch": specmap.branch,
    }


def _compute_file_hashes(repo_root: str, annotations: list) -> dict[str, str]:
    """Hash current content of all files referenced by annotations."""
    hashes: dict[str, str] = {}
    for ann in annotations:
        if ann.file not in hashes:
            content = _read_file(repo_root, ann.file)
            if content is not None:
                hashes[ann.file] = hash_code(content)
    return hashes


def _find_stale_annotations(repo_root: str, specmap) -> list[Annotation]:
    """Return annotations whose code_hash doesn't match current file content.

    For annotations with code_hash="", falls back to file-level hash comparison.
    """
    stale: list[Annotation] = []
    file_content_cache: dict[str, str | None] = {}
    # Also check for file-level changes for files with all-legacy annotations
    dirty_files = _find_dirty_files(repo_root, specmap)

    for ann in specmap.annotations:
        if ann.code_hash:
            # Per-annotation hash check
            if ann.file not in file_content_cache:
                file_content_cache[ann.file] = _read_file(repo_root, ann.file)
            content = file_content_cache[ann.file]
            if content is None:
                stale.append(ann)
                continue
            try:
                current_hash = hash_code_lines(content, ann.start_line, ann.end_line)
            except (IndexError, ValueError):
                stale.append(ann)
                continue
            if current_hash != ann.code_hash:
                stale.append(ann)
        elif ann.file in dirty_files:
            # Legacy annotation in a dirty file — treat as stale
            stale.append(ann)

    return stale


def _find_dirty_files(repo_root: str, specmap) -> set[str]:
    """Compare stored file_hashes to current content. Return files that differ."""
    dirty: set[str] = set()
    for file_path, stored_hash in specmap.file_hashes.items():
        content = _read_file(repo_root, file_path)
        if content is None:
            dirty.add(file_path)  # file deleted
        elif hash_code(content) != stored_hash:
            dirty.add(file_path)
    return dirty


def _backfill_code_hashes(repo_root: str, annotations: list[Annotation]) -> None:
    """Fill code_hash on annotations that have code_hash=''.

    Called before every save to ensure all annotations have hashes.
    """
    file_content_cache: dict[str, str | None] = {}
    for ann in annotations:
        if ann.code_hash:
            continue
        if ann.file not in file_content_cache:
            file_content_cache[ann.file] = _read_file(repo_root, ann.file)
        content = file_content_cache[ann.file]
        if content is not None:
            try:
                ann.code_hash = hash_code_lines(content, ann.start_line, ann.end_line)
            except (IndexError, ValueError):
                pass


def _filter_by_code_hash(
    repo_root: str,
    classified,
):
    """Demote regenerate→keep for annotations whose code_hash still matches.

    If an annotation was classified as regenerate because it overlaps a hunk,
    but the actual code at [start_line:end_line] hasn't changed (hash matches),
    it can safely be kept.
    """
    from specmap.indexer.diff_optimizer import ClassifiedAnnotations

    file_content_cache: dict[str, str | None] = {}
    still_regenerate: list[Annotation] = []
    demoted_to_keep: list[Annotation] = []

    for ann in classified.regenerate:
        if not ann.code_hash:
            still_regenerate.append(ann)
            continue
        if ann.file not in file_content_cache:
            file_content_cache[ann.file] = _read_file(repo_root, ann.file)
        content = file_content_cache[ann.file]
        if content is None:
            still_regenerate.append(ann)
            continue
        try:
            current_hash = hash_code_lines(content, ann.start_line, ann.end_line)
        except (IndexError, ValueError):
            still_regenerate.append(ann)
            continue
        if current_hash == ann.code_hash:
            demoted_to_keep.append(ann)
        else:
            still_regenerate.append(ann)

    return ClassifiedAnnotations(
        keep=classified.keep + demoted_to_keep,
        shift=classified.shift,
        regenerate=still_regenerate,
    )


def _get_working_tree_diff(repo_root: str, specmap) -> str | None:
    """Get uncommitted changes as unified diff via `git diff HEAD`.

    Returns None if the command fails (e.g. untracked files only, initial commit).
    """
    # Get the list of annotated files to scope the diff
    annotated_files = list(specmap.file_hashes.keys())
    if not annotated_files:
        return None
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--"] + annotated_files,
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except FileNotFoundError:
        pass
    return None


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

"""specmap status — human-readable annotation summary."""

from __future__ import annotations

import typer

from specmap.cli import app
from specmap.cli.output import get_console
from specmap.indexer.hasher import hash_code_lines
from specmap.state.specmap_file import SpecmapFileManager


@app.command()
def status(ctx: typer.Context):
    """Show human-readable annotation summary."""
    repo_root = ctx.obj["repo_root"]
    branch = ctx.obj["branch"]
    no_color: bool = ctx.obj["no_color"]
    if not repo_root or not branch:
        typer.echo("Error: must be run inside a git repository", err=True)
        raise typer.Exit(code=1)
    console = get_console(no_color)

    mgr = SpecmapFileManager(repo_root)
    sf = mgr.load(branch)

    fpath = mgr._file_path(branch)
    if not fpath.exists():
        console.print(f"specmap: no specmap file found for branch {branch}", style="red")
        raise typer.Exit(code=1)

    console.print(f"specmap: status for {sf.branch} (base: {sf.base_branch})\n")

    if sf.head_sha:
        console.print(f"Head SHA: {sf.head_sha[:12]}")

    # Annotations summary
    total_annotations = len(sf.annotations)
    with_refs = sum(1 for a in sf.annotations if a.refs)
    without_refs = total_annotations - with_refs

    console.print(f"\nAnnotations: {total_annotations} total")
    if total_annotations > 0:
        console.print(f"  With spec refs: {with_refs}")
        console.print(f"  Without spec refs: {without_refs}")

    # Compute staleness on-the-fly
    if total_annotations > 0:
        staleness = _compute_staleness(repo_root, sf.annotations)
        parts = []
        if staleness["fresh"]:
            parts.append(f"Fresh: {staleness['fresh']}")
        if staleness["stale"]:
            parts.append(f"Stale: {staleness['stale']}")
        if staleness["unknown"]:
            parts.append(f"Unknown: {staleness['unknown']}")
        if staleness["missing"]:
            parts.append(f"Missing: {staleness['missing']}")
        if parts:
            console.print(f"  {' | '.join(parts)}")

    # Group by file
    by_file: dict[str, list] = {}
    for ann in sf.annotations:
        by_file.setdefault(ann.file, []).append(ann)

    if by_file:
        console.print(f"\nFiles ({len(by_file)}):")
        for file_path in sorted(by_file.keys()):
            anns = by_file[file_path]
            ref_count = sum(len(a.refs) for a in anns)
            console.print(
                f"  {file_path} ({len(anns)} annotations, {ref_count} spec refs)"
            )
            for ann in anns:
                desc = ann.description[:80] + "..." if len(ann.description) > 80 else ann.description
                console.print(f"    L{ann.start_line}-{ann.end_line}: {desc}")

    console.print("\nRun 'specmap validate' to verify annotation line ranges.")


def _compute_staleness(repo_root: str, annotations: list) -> dict[str, int]:
    """Compute staleness breakdown for annotations on-the-fly."""
    from pathlib import Path

    counts = {"fresh": 0, "stale": 0, "unknown": 0, "missing": 0}
    file_cache: dict[str, str | None] = {}

    for ann in annotations:
        if ann.file not in file_cache:
            try:
                file_cache[ann.file] = (
                    (Path(repo_root) / ann.file).read_text(encoding="utf-8")
                )
            except (OSError, UnicodeDecodeError):
                file_cache[ann.file] = None

        content = file_cache[ann.file]
        if content is None:
            counts["missing"] += 1
            continue

        if not ann.code_hash:
            counts["unknown"] += 1
            continue

        try:
            current_hash = hash_code_lines(content, ann.start_line, ann.end_line)
            if current_hash == ann.code_hash:
                counts["fresh"] += 1
            else:
                counts["stale"] += 1
        except (IndexError, ValueError):
            counts["stale"] += 1

    return counts

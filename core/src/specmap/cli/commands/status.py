"""specmap status — human-readable annotation summary."""

from __future__ import annotations

import typer

from specmap.cli import app
from specmap.cli.output import get_console
from specmap.state.specmap_file import SpecmapFileManager


@app.command()
def status(ctx: typer.Context):
    """Show human-readable annotation summary."""
    repo_root: str = ctx.obj["repo_root"]
    branch: str = ctx.obj["branch"]
    no_color: bool = ctx.obj["no_color"]
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

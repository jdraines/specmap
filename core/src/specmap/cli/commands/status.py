"""specmap status — human-readable mapping summary."""

from __future__ import annotations

import typer

from specmap.cli import app
from specmap.cli.output import get_console
from specmap.state.specmap_file import SpecmapFileManager


@app.command()
def status(ctx: typer.Context):
    """Show human-readable mapping summary."""
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

    # Spec Documents summary.
    console.print("Spec Documents:")
    for doc_path, doc in sf.spec_documents.items():
        section_count = len(doc.sections)
        mapping_count = 0
        for m in sf.mappings:
            for span in m.spec_spans:
                if span.spec_file == doc_path:
                    mapping_count += 1
                    break
        console.print(f"  {doc_path} ({section_count} sections, {mapping_count} mappings)")

    # Overall mapping stats.
    total_mappings = len(sf.mappings)
    stale_mappings = 0
    stale_details: list[dict] = []

    for m in sf.mappings:
        if m.stale:
            stale_mappings += 1
            heading = ""
            spec_file = ""
            if m.spec_spans:
                spec_file = m.spec_spans[0].spec_file
                heading = " > ".join(m.spec_spans[0].heading_path)
            stale_details.append({
                "file": m.code_target.file,
                "start_line": m.code_target.start_line,
                "end_line": m.code_target.end_line,
                "spec_file": spec_file,
                "heading": heading,
            })

    valid_mappings = total_mappings - stale_mappings
    console.print(
        f"\nMappings: {total_mappings} total "
        f"({valid_mappings} valid, {stale_mappings} stale)"
    )

    if stale_details:
        console.print("Stale:")
        for s in stale_details:
            target = f"{s['file']}:{s['start_line']}-{s['end_line']}"
            spec = s["spec_file"]
            if s["heading"]:
                spec += " > " + s["heading"]
            console.print(f"  {target} \u2192 {spec}")

    console.print("\nCoverage: see 'specmap check' for coverage details")

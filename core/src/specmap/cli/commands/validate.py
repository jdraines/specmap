"""specmap validate — check that annotated code regions still exist."""

from __future__ import annotations

import typer

from specmap.cli import app
from specmap.cli.output import check_mark, cross_mark, get_console
from specmap.indexer.validator import validate_specmap
from specmap.state.specmap_file import SpecmapFileManager


@app.command()
def validate(ctx: typer.Context):
    """Validate specmap file: check that annotated line ranges are in bounds."""
    repo_root: str = ctx.obj["repo_root"]
    branch: str = ctx.obj["branch"]
    no_color: bool = ctx.obj["no_color"]
    console = get_console(no_color)

    sanitized = branch.replace("/", "--")
    console.print(f"specmap: validating .specmap/{sanitized}.json")

    mgr = SpecmapFileManager(repo_root)
    sf = mgr.load(branch)

    # Check if file actually exists (load returns empty SpecmapFile if not found).
    fpath = mgr._file_path(branch)
    if not fpath.exists():
        console.print(f"{cross_mark(no_color)} Schema invalid: file not found")
        raise typer.Exit(code=1)

    console.print(f"{check_mark(no_color)} Schema valid (version {sf.version})")

    results = validate_specmap(sf, repo_root)

    valid = 0
    invalid = 0
    total = len(results)

    for r in results:
        if r.valid:
            indicator = check_mark(no_color)
            valid += 1
        else:
            indicator = cross_mark(no_color)
            invalid += 1

        loc = f"{r.file}:{r.lines}" if r.lines else r.file
        console.print(f"{indicator} {loc} ({r.message})")

    if invalid == 0:
        console.print(f"{check_mark(no_color)} {valid}/{total} annotations valid")
    else:
        console.print(
            f"{cross_mark(no_color)} {valid}/{total} annotations valid, "
            f"{invalid} invalid"
        )
        raise typer.Exit(code=1)

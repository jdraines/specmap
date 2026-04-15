"""specmap annotate — CLI command for generating annotations."""

from __future__ import annotations

import asyncio
import json

import typer

from specmap.cli import app
from specmap.cli.output import get_console


@app.command(name="annotate")
def annotate_cmd(
    ctx: typer.Context,
    files: list[str] = typer.Argument(None, help="Specific files to annotate"),
    context: str = typer.Option("", help="Freeform development context for better annotations"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be regenerated"),
    output_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Generate annotations for code changes with spec references."""
    repo_root = ctx.obj["repo_root"]
    branch = ctx.obj["branch"]
    no_color: bool = ctx.obj["no_color"]
    if not repo_root:
        typer.echo("Error: must be run inside a git repository", err=True)
        raise typer.Exit(code=1)

    from specmap.tools.annotate import annotate

    result = asyncio.run(annotate(
        repo_root=repo_root,
        code_changes=files or None,
        branch=branch or None,
        context=context or None,
        dry_run=dry_run,
    ))

    if output_json:
        typer.echo(json.dumps(result, default=str, indent=2))
        return

    if dry_run:
        _print_dry_run_result(result, no_color)
    else:
        _print_annotate_result(result, no_color)


def _print_annotate_result(result: dict, no_color: bool) -> None:
    """Print human-readable annotation result."""
    console = get_console(no_color)
    status = result.get("status", "unknown")

    if status == "no_specs":
        console.print("No spec files found in repository.", style="yellow")
        return

    if status == "no_changes":
        console.print("No code changes to annotate.", style="dim")
        return

    created = result.get("annotations_created", 0)
    total = result.get("total_annotations", 0)
    specs = result.get("spec_files_used", 0)
    changes = result.get("code_changes_analyzed", 0)

    console.print(f"Annotations: {created} created, {total} total")
    console.print(f"Spec files used: {specs}")
    console.print(f"Code changes analyzed: {changes}")

    if result.get("incremental"):
        kept = result.get("annotations_kept", 0)
        shifted = result.get("annotations_shifted", 0)
        regen = result.get("annotations_regenerated", 0)
        parts = []
        if kept:
            parts.append(f"{kept} kept")
        if shifted:
            parts.append(f"{shifted} shifted")
        if regen:
            parts.append(f"{regen} regenerated")
        if parts:
            console.print(f"Incremental: {', '.join(parts)}")

    if dirty := result.get("dirty_files"):
        console.print(f"Dirty files: {', '.join(dirty)}")

    usage = result.get("llm_usage", {})
    if usage.get("total_calls"):
        console.print(
            f"LLM: {usage['total_calls']} calls, "
            f"{usage.get('total_input_tokens', 0)} in / "
            f"{usage.get('total_output_tokens', 0)} out tokens"
        )


def _print_dry_run_result(result: dict, no_color: bool) -> None:
    """Print human-readable dry-run preview."""
    console = get_console(no_color)
    console.print("Dry run — no LLM calls or file changes made.\n", style="bold")

    keep = result.get("would_keep", 0)
    shift = result.get("would_shift", 0)
    regen = result.get("would_regenerate", [])

    console.print(f"Would keep:       {keep}")
    console.print(f"Would shift:      {shift}")
    console.print(f"Would regenerate: {len(regen) if isinstance(regen, list) else regen}")

    if isinstance(regen, list) and regen:
        console.print("\nAnnotations to regenerate:")
        for item in regen:
            if isinstance(item, dict):
                console.print(f"  {item['file']} L{item['lines']}  ({item['id']})")
            else:
                console.print(f"  {item}")

    if files := result.get("files_analyzed"):
        console.print(f"\nFiles: {', '.join(files)}")

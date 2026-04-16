"""Specmap CLI — Typer app definition and global callback."""

from __future__ import annotations

import subprocess
from pathlib import Path

import typer

from specmap import __version__

app = typer.Typer(
    name="specmap",
    help="Spec-to-code mapping validation and coverage",
    no_args_is_help=True,
)


def _detect_repo_root() -> str | None:
    """Walk up from cwd looking for .git/. Returns None if not in a repo."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists():
            return str(current)
        current = current.parent
    return None


def _detect_branch(repo_root: str) -> str | None:
    """Get current branch from git. Returns None on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            if branch and branch != "HEAD":
                return branch
    except FileNotFoundError:
        pass
    return None


def _version_callback(value: bool):
    if value:
        typer.echo(f"specmap {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    repo_root: str = typer.Option("", help="Repository root (default: auto-detect)"),
    branch: str = typer.Option("", help="Branch name (default: auto-detect)"),
    no_color: bool = typer.Option(False, help="Disable color output"),
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True, help="Show version and exit"),
):
    """Spec-to-code mapping validation and coverage."""
    ctx.ensure_object(dict)
    resolved_root = repo_root or _detect_repo_root()
    ctx.obj["repo_root"] = resolved_root
    ctx.obj["branch"] = branch or (_detect_branch(resolved_root) if resolved_root else None)
    ctx.obj["no_color"] = no_color


# Register subcommands by importing the command modules.
from specmap.cli.commands import validate, status, serve, annotate, hook, config_cmd  # noqa: E402, F401

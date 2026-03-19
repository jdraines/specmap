"""Specmap CLI — Typer app definition and global callback."""

from __future__ import annotations

import subprocess
from pathlib import Path

import typer

app = typer.Typer(
    name="specmap",
    help="Spec-to-code mapping validation and coverage",
    no_args_is_help=True,
)


def _detect_repo_root() -> str:
    """Walk up from cwd looking for .git/."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists():
            return str(current)
        current = current.parent
    raise typer.Exit(code=1)


def _detect_branch(repo_root: str) -> str:
    """Get current branch from git."""
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
    raise typer.Exit(code=1)


@app.callback()
def main(
    ctx: typer.Context,
    repo_root: str = typer.Option("", help="Repository root (default: auto-detect)"),
    branch: str = typer.Option("", help="Branch name (default: auto-detect)"),
    no_color: bool = typer.Option(False, help="Disable color output"),
):
    """Spec-to-code mapping validation and coverage."""
    ctx.ensure_object(dict)
    resolved_root = repo_root or _detect_repo_root()
    ctx.obj["repo_root"] = resolved_root
    ctx.obj["branch"] = branch or _detect_branch(resolved_root)
    ctx.obj["no_color"] = no_color


# Register subcommands by importing the command modules.
from specmap.cli.commands import validate, status, check  # noqa: E402, F401

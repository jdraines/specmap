"""Rich console helpers for CLI output."""

from __future__ import annotations

from rich.console import Console

_console: Console | None = None


def get_console(no_color: bool = False) -> Console:
    """Get or create a Rich Console with color settings."""
    global _console
    if _console is None or _console.no_color != no_color:
        _console = Console(no_color=no_color)
    return _console


def check_mark(no_color: bool = False) -> str:
    """Green check mark."""
    if no_color:
        return "\u2713"
    return "[green]\u2713[/green]"


def cross_mark(no_color: bool = False) -> str:
    """Red cross mark."""
    if no_color:
        return "\u2717"
    return "[red]\u2717[/red]"

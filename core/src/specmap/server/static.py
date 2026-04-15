"""Locate bundled frontend static files."""

from __future__ import annotations

from pathlib import Path


def get_bundled_static_dir() -> str | None:
    """Return path to bundled _static/ dir, or None if not present."""
    static = Path(__file__).resolve().parent.parent / "_static"
    if (static / "index.html").is_file():
        return str(static)
    return None

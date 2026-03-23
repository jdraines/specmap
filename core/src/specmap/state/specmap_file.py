"""Read/write .specmap/{branch}.json tracking files."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from specmap.state.models import SpecmapFile


class SpecmapFileManager:
    """Manages .specmap/{branch}.json files."""

    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root)

    def get_branch(self) -> str:
        """Get the current git branch name."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except FileNotFoundError:
            pass
        return "unknown"

    def get_base_branch(self, configured: str | None = None) -> str:
        """Detect the base branch (default: main, fallback: master).

        If *configured* is set, verify it exists as a git ref and return it.
        Falls back to auto-detect if the configured ref doesn't exist.
        """
        if configured:
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--verify", configured],
                    cwd=str(self.repo_root),
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    return configured
            except FileNotFoundError:
                pass
            print(
                f"[specmap] Warning: configured base_branch '{configured}' "
                f"not found as a git ref, falling back to auto-detect",
                file=sys.stderr,
            )

        for candidate in ("main", "master"):
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--verify", candidate],
                    cwd=str(self.repo_root),
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    return candidate
            except FileNotFoundError:
                break
        return "main"

    def _sanitize_branch(self, branch: str) -> str:
        """Convert branch name to safe filename: replace / with --."""
        return branch.replace("/", "--")

    def _specmap_dir(self) -> Path:
        """Get the .specmap/ directory path."""
        return self.repo_root / ".specmap"

    def _file_path(self, branch: str) -> Path:
        """Get the path for a branch's tracking file."""
        return self._specmap_dir() / f"{self._sanitize_branch(branch)}.json"

    def ensure_dir(self) -> None:
        """Create .specmap/ directory if needed."""
        self._specmap_dir().mkdir(parents=True, exist_ok=True)

    def load(self, branch: str | None = None) -> SpecmapFile:
        """Load from .specmap/{branch}.json. Returns empty SpecmapFile if not found."""
        if branch is None:
            branch = self.get_branch()

        path = self._file_path(branch)
        if not path.exists():
            return SpecmapFile(
                branch=branch,
                base_branch=self.get_base_branch(),
            )

        try:
            with open(path) as f:
                data = json.load(f)
            return SpecmapFile.model_validate(data)
        except (json.JSONDecodeError, OSError, ValueError) as e:
            print(f"[specmap] Warning: failed to load {path}: {e}", file=sys.stderr)
            return SpecmapFile(
                branch=branch,
                base_branch=self.get_base_branch(),
            )

    def save(self, data: SpecmapFile) -> Path:
        """Write to .specmap/{branch}.json with pretty JSON."""
        self.ensure_dir()
        data.updated_at = datetime.now(timezone.utc)

        path = self._file_path(data.branch)
        json_str = data.model_dump_json(indent=2)
        path.write_text(json_str, encoding="utf-8")
        return path

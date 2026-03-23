"""BYOK config loading for Specmap MCP server.

Loads from environment variables and optionally from .specmap/config.json in the repo root.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


_DEFAULT_SPEC_PATTERNS = ["**/*.md"]
_DEFAULT_IGNORE_PATTERNS = ["*.generated.go", "*.lock", "vendor/**"]
_DEFAULT_MODEL = "gpt-4o-mini"

# Patterns to exclude from spec auto-discovery
SPEC_EXCLUDE_FILENAMES = {
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE.md",
    "CODE_OF_CONDUCT.md",
}
SPEC_EXCLUDE_DIRS = {
    "node_modules",
    ".git",
    ".specmap",
    "vendor",
    "__pycache__",
    ".venv",
    "venv",
}


@dataclass
class SpecmapConfig:
    """Configuration for the Specmap MCP server."""

    model: str = _DEFAULT_MODEL
    api_key: str | None = None
    api_base: str | None = None
    spec_patterns: list[str] = field(default_factory=lambda: list(_DEFAULT_SPEC_PATTERNS))
    ignore_patterns: list[str] = field(default_factory=lambda: list(_DEFAULT_IGNORE_PATTERNS))
    base_branch: str | None = None
    repo_root: str | None = None

    @classmethod
    def load(cls, repo_root: str | None = None) -> SpecmapConfig:
        """Load config from environment variables and .specmap/config.json."""
        config = cls()

        # Detect repo root if not provided
        if repo_root is None:
            repo_root = _detect_repo_root()
        config.repo_root = repo_root

        # Load from config file if it exists
        if repo_root:
            config_path = Path(repo_root) / ".specmap" / "config.json"
            if config_path.exists():
                _load_config_file(config, config_path)
                _warn_if_tracked(config_path, repo_root)

        # Environment variables override config file
        if env_model := os.environ.get("SPECMAP_MODEL"):
            config.model = env_model
        if env_key := os.environ.get("SPECMAP_API_KEY"):
            config.api_key = env_key
        if env_base := os.environ.get("SPECMAP_API_BASE"):
            config.api_base = env_base
        if env_patterns := os.environ.get("SPECMAP_SPEC_PATTERNS"):
            config.spec_patterns = [p.strip() for p in env_patterns.split(",") if p.strip()]
        if env_ignore := os.environ.get("SPECMAP_IGNORE_PATTERNS"):
            config.ignore_patterns = [p.strip() for p in env_ignore.split(",") if p.strip()]
        if env_base_branch := os.environ.get("SPECMAP_BASE_BRANCH"):
            config.base_branch = env_base_branch

        return config


def _detect_repo_root() -> str | None:
    """Walk up from cwd looking for .git/."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists():
            return str(current)
        current = current.parent
    return None


def _load_config_file(config: SpecmapConfig, config_path: Path) -> None:
    """Load settings from a JSON config file."""
    try:
        with open(config_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[specmap] Warning: failed to read {config_path}: {e}", file=sys.stderr)
        return

    if model := data.get("model"):
        config.model = model
    if api_key := data.get("api_key"):
        config.api_key = api_key
    if api_base := data.get("api_base"):
        config.api_base = api_base
    if spec_patterns := data.get("spec_patterns"):
        if isinstance(spec_patterns, list):
            config.spec_patterns = spec_patterns
    if ignore_patterns := data.get("ignore_patterns"):
        if isinstance(ignore_patterns, list):
            config.ignore_patterns = ignore_patterns
    if base_branch := data.get("base_branch"):
        config.base_branch = base_branch


def _warn_if_tracked(config_path: Path, repo_root: str) -> None:
    """Warn to stderr if the config file appears to be tracked by git."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(config_path)],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(
                f"[specmap] WARNING: {config_path} is tracked by git and may contain API keys. "
                f"Add '.specmap/config.json' to .gitignore.",
                file=sys.stderr,
            )
    except FileNotFoundError:
        pass  # git not available

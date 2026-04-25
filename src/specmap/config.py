"""Two-layer TOML config system for Specmap.

Loads configuration from:
  1. User config:  $XDG_CONFIG_HOME/specmap/config.toml  (secrets allowed)
  2. Repo config:  <repo>/.specmap/config.toml            (secrets blocked)
  3. Environment variables                                (highest priority)

Legacy .specmap/config.json is still read (with a deprecation warning).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

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

# Fields that must never appear in repo-level config (secrets).
_REPO_BLOCKED_FIELDS = {"api_key", "forge_github_token", "forge_gitlab_token"}


# ---------------------------------------------------------------------------
# SpecmapConfig — represents one TOML config file
# ---------------------------------------------------------------------------

@dataclass
class SpecmapConfig:
    """Represents the contents of a single config.toml file."""

    # [llm]
    model: str | None = None
    api_key: str | None = None
    api_base: str | None = None
    # [forge]
    forge_github_token: str | None = None
    forge_gitlab_token: str | None = None
    # [repo]
    spec_patterns: list[str] | None = None
    ignore_patterns: list[str] | None = None
    base_branch: str | None = None
    # [defaults]
    batch_token_budget: int | None = None
    annotate_timeout: int | None = None
    # [server]
    server_host: str | None = None
    server_port: int | None = None
    server_database_path: str | None = None


# ---------------------------------------------------------------------------
# CoreConfig — merged / resolved config with concrete defaults
# ---------------------------------------------------------------------------

@dataclass
class CoreConfig:
    """Merged, resolved configuration — ready for use by library code."""

    model: str = _DEFAULT_MODEL
    api_key: str | None = None
    api_base: str | None = None
    spec_patterns: list[str] = field(default_factory=lambda: list(_DEFAULT_SPEC_PATTERNS))
    ignore_patterns: list[str] = field(default_factory=lambda: list(_DEFAULT_IGNORE_PATTERNS))
    base_branch: str | None = None
    repo_root: str | None = None
    batch_token_budget: int = 8000
    annotate_timeout: int = 120

    @classmethod
    def load(cls, repo_root: str | None = None) -> CoreConfig:
        """Load config from user TOML, repo TOML/JSON, and env vars."""
        config = cls()

        # 1. Detect repo root
        if repo_root is None:
            repo_root = _detect_repo_root()
        config.repo_root = repo_root

        # 2. User-level TOML
        u_path = user_config_path()
        if u_path.exists():
            user_cfg = _load_toml(u_path)
            _apply(config, user_cfg)

        # 3. Repo-level config
        if repo_root:
            toml_path = repo_config_path(repo_root)
            json_path = Path(repo_root) / ".specmap" / "config.json"

            if toml_path.exists():
                repo_cfg = _load_toml(toml_path)
                _apply(config, repo_cfg, block_secrets=True)
                _warn_if_tracked(toml_path, repo_root)
            elif json_path.exists():
                print(
                    "[specmap] WARNING: .specmap/config.json is deprecated — "
                    "migrate to .specmap/config.toml",
                    file=sys.stderr,
                )
                repo_cfg = _load_legacy_json(json_path)
                _apply(config, repo_cfg, block_secrets=True)
                _warn_if_tracked(json_path, repo_root)

        # 4. Environment variable overrides (highest priority)
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
        if env_batch := os.environ.get("SPECMAP_BATCH_TOKEN_BUDGET"):
            try:
                config.batch_token_budget = int(env_batch)
            except ValueError:
                pass
        if env_timeout := os.environ.get("SPECMAP_ANNOTATE_TIMEOUT"):
            try:
                config.annotate_timeout = int(env_timeout)
            except ValueError:
                pass

        return config


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def user_config_path() -> Path:
    """Return $XDG_CONFIG_HOME/specmap/config.toml (default ~/.config/specmap/config.toml)."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "specmap" / "config.toml"


def user_data_path() -> Path:
    """Return $XDG_DATA_HOME/specmap/ (default ~/.local/share/specmap/).

    Used as fallback storage for annotations and walkthroughs when
    the server is not running from within the target repository.
    """
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "specmap"


def repo_config_path(repo_root: str) -> Path:
    """Return <repo>/.specmap/config.toml."""
    return Path(repo_root) / ".specmap" / "config.toml"


# ---------------------------------------------------------------------------
# Repo-root detection
# ---------------------------------------------------------------------------

def _detect_repo_root() -> str | None:
    """Walk up from cwd looking for .git/."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists():
            return str(current)
        current = current.parent
    return None


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _load_toml(path: Path) -> SpecmapConfig:
    """Read a TOML config file and return a SpecmapConfig."""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError) as e:
        print(f"[specmap] Warning: failed to read {path}: {e}", file=sys.stderr)
        return SpecmapConfig()

    cfg = SpecmapConfig()

    # [llm]
    llm = data.get("llm", {})
    if "model" in llm:
        cfg.model = llm["model"]
    if "api_key" in llm:
        cfg.api_key = llm["api_key"]
    if "api_base" in llm:
        cfg.api_base = llm["api_base"]

    # [forge]
    forge = data.get("forge", {})
    gh = forge.get("github", {})
    if "token" in gh:
        cfg.forge_github_token = gh["token"]
    gl = forge.get("gitlab", {})
    if "token" in gl:
        cfg.forge_gitlab_token = gl["token"]

    # [repo]
    repo = data.get("repo", {})
    if "spec_patterns" in repo:
        cfg.spec_patterns = repo["spec_patterns"]
    if "ignore_patterns" in repo:
        cfg.ignore_patterns = repo["ignore_patterns"]
    if "base_branch" in repo:
        cfg.base_branch = repo["base_branch"]

    # [defaults]
    defaults = data.get("defaults", {})
    if "batch_token_budget" in defaults:
        cfg.batch_token_budget = defaults["batch_token_budget"]
    if "annotate_timeout" in defaults:
        cfg.annotate_timeout = defaults["annotate_timeout"]

    # [server]
    server = data.get("server", {})
    if "host" in server:
        cfg.server_host = server["host"]
    if "port" in server:
        cfg.server_port = server["port"]
    if "database_path" in server:
        cfg.server_database_path = server["database_path"]

    return cfg


def _load_legacy_json(path: Path) -> SpecmapConfig:
    """Read the old .specmap/config.json format and return a SpecmapConfig."""
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[specmap] Warning: failed to read {path}: {e}", file=sys.stderr)
        return SpecmapConfig()

    cfg = SpecmapConfig()
    if model := data.get("model"):
        cfg.model = model
    if api_key := data.get("api_key"):
        cfg.api_key = api_key
    if api_base := data.get("api_base"):
        cfg.api_base = api_base
    if spec_patterns := data.get("spec_patterns"):
        if isinstance(spec_patterns, list):
            cfg.spec_patterns = spec_patterns
    if ignore_patterns := data.get("ignore_patterns"):
        if isinstance(ignore_patterns, list):
            cfg.ignore_patterns = ignore_patterns
    if base_branch := data.get("base_branch"):
        cfg.base_branch = base_branch
    if batch_token_budget := data.get("batch_token_budget"):
        if isinstance(batch_token_budget, int):
            cfg.batch_token_budget = batch_token_budget
    if annotate_timeout := data.get("annotate_timeout"):
        if isinstance(annotate_timeout, int):
            cfg.annotate_timeout = annotate_timeout
    return cfg


# ---------------------------------------------------------------------------
# Apply / merge helpers
# ---------------------------------------------------------------------------

def _apply(config: CoreConfig, layer: SpecmapConfig, *, block_secrets: bool = False) -> None:
    """Apply non-None fields from *layer* onto *config*."""
    if block_secrets:
        for field_name in _REPO_BLOCKED_FIELDS:
            if getattr(layer, field_name) is not None:
                print(
                    f"[specmap] WARNING: ignoring '{field_name}' in repo config — "
                    f"secrets belong in user config or env vars",
                    file=sys.stderr,
                )
                setattr(layer, field_name, None)

    if layer.model is not None:
        config.model = layer.model
    if layer.api_key is not None:
        config.api_key = layer.api_key
    if layer.api_base is not None:
        config.api_base = layer.api_base
    if layer.spec_patterns is not None:
        config.spec_patterns = layer.spec_patterns
    if layer.ignore_patterns is not None:
        config.ignore_patterns = layer.ignore_patterns
    if layer.base_branch is not None:
        config.base_branch = layer.base_branch
    if layer.batch_token_budget is not None:
        config.batch_token_budget = layer.batch_token_budget
    if layer.annotate_timeout is not None:
        config.annotate_timeout = layer.annotate_timeout


def _deep_merge(base: dict, override: dict) -> None:
    """Merge *override* into *base* in place, recursing into nested dicts."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


# ---------------------------------------------------------------------------
# Git tracking warning
# ---------------------------------------------------------------------------

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
                f"Add '{config_path.relative_to(repo_root)}' to .gitignore.",
                file=sys.stderr,
            )
    except FileNotFoundError:
        pass  # git not available


# ---------------------------------------------------------------------------
# TOML serialisation helpers
# ---------------------------------------------------------------------------

def _toml_dict(config: SpecmapConfig) -> dict:
    """Convert SpecmapConfig to TOML-structured dict (only non-None fields)."""
    d: dict = {}

    # [llm]
    llm: dict = {}
    if config.model is not None:
        llm["model"] = config.model
    if config.api_key is not None:
        llm["api_key"] = config.api_key
    if config.api_base is not None:
        llm["api_base"] = config.api_base
    if llm:
        d["llm"] = llm

    # [forge]
    forge: dict = {}
    if config.forge_github_token is not None:
        forge["github"] = {"token": config.forge_github_token}
    if config.forge_gitlab_token is not None:
        forge["gitlab"] = {"token": config.forge_gitlab_token}
    if forge:
        d["forge"] = forge

    # [repo]
    repo: dict = {}
    if config.spec_patterns is not None:
        repo["spec_patterns"] = config.spec_patterns
    if config.ignore_patterns is not None:
        repo["ignore_patterns"] = config.ignore_patterns
    if config.base_branch is not None:
        repo["base_branch"] = config.base_branch
    if repo:
        d["repo"] = repo

    # [defaults]
    defaults: dict = {}
    if config.batch_token_budget is not None:
        defaults["batch_token_budget"] = config.batch_token_budget
    if config.annotate_timeout is not None:
        defaults["annotate_timeout"] = config.annotate_timeout
    if defaults:
        d["defaults"] = defaults

    # [server]
    server: dict = {}
    if config.server_host is not None:
        server["host"] = config.server_host
    if config.server_port is not None:
        server["port"] = config.server_port
    if config.server_database_path is not None:
        server["database_path"] = config.server_database_path
    if server:
        d["server"] = server

    return d


# ---------------------------------------------------------------------------
# Save helpers
# ---------------------------------------------------------------------------

def save_user_config(config: SpecmapConfig) -> Path:
    """Write config to user config file with secure permissions."""
    import tomli_w

    path = user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)

    data = _toml_dict(config)

    # Merge with existing file if present
    if path.exists():
        existing = _load_toml(path)
        existing_data = _toml_dict(existing)
        _deep_merge(existing_data, data)
        data = existing_data

    with open(path, "wb") as f:
        tomli_w.dump(data, f)
    os.chmod(path, 0o600)
    return path


def save_repo_config(config: SpecmapConfig, repo_root: str) -> Path:
    """Write config to repo config file. Secrets are blocked."""
    import tomli_w

    for field_name in _REPO_BLOCKED_FIELDS:
        if getattr(config, field_name) is not None:
            raise ValueError(
                f"Cannot store '{field_name}' in repo config — "
                f"secrets belong in user config or env vars"
            )

    path = repo_config_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = _toml_dict(config)

    # Merge with existing
    if path.exists():
        existing = _load_toml(path)
        existing_data = _toml_dict(existing)
        _deep_merge(existing_data, data)
        data = existing_data

    with open(path, "wb") as f:
        tomli_w.dump(data, f)
    return path

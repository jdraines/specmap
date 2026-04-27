"""specmap config — read and write configuration."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import typer

from specmap.cli import app

config_app = typer.Typer(help="Read and write specmap configuration.")
app.add_typer(config_app, name="config")

_KEY_MAP = {
    "llm.model": "model",
    "llm.api_key": "api_key",
    "llm.api_base": "api_base",
    "forge.github.token": "forge_github_token",
    "forge.gitlab.token": "forge_gitlab_token",
    "repo.spec_patterns": "spec_patterns",
    "repo.ignore_patterns": "ignore_patterns",
    "repo.base_branch": "base_branch",
    "defaults.batch_token_budget": "batch_token_budget",
    "defaults.annotate_timeout": "annotate_timeout",
    "server.host": "server_host",
    "server.port": "server_port",
    "server.database_path": "server_database_path",
}

_SECRET_KEYS = {"llm.api_key", "forge.github.token", "forge.gitlab.token"}

_REPO_BLOCKED_KEYS = {"llm.api_key", "forge.github.token", "forge.gitlab.token"}

_INT_KEYS = {"defaults.batch_token_budget", "defaults.annotate_timeout", "server.port"}

_LIST_KEYS = {"repo.spec_patterns", "repo.ignore_patterns"}

_ENV_MAP = {
    "llm.model": "SPECMAP_MODEL",
    "llm.api_key": "SPECMAP_API_KEY",
    "llm.api_base": "SPECMAP_API_BASE",
    "repo.spec_patterns": "SPECMAP_SPEC_PATTERNS",
    "repo.ignore_patterns": "SPECMAP_IGNORE_PATTERNS",
    "repo.base_branch": "SPECMAP_BASE_BRANCH",
    "defaults.batch_token_budget": "SPECMAP_BATCH_TOKEN_BUDGET",
    "defaults.annotate_timeout": "SPECMAP_ANNOTATE_TIMEOUT",
    "server.host": "HOST",
    "server.port": "PORT",
    "server.database_path": "DATABASE_PATH",
}

# -- Defaults used when no config is set ---------------------------------

_DEFAULTS = {
    "llm.model": "gpt-4o-mini",
    "llm.api_key": None,
    "llm.api_base": None,
    "forge.github.token": None,
    "forge.gitlab.token": None,
    "repo.spec_patterns": ["**/*.md"],
    "repo.ignore_patterns": ["*.generated.go", "*.lock", "vendor/**"],
    "repo.base_branch": None,
    "defaults.batch_token_budget": 8000,
    "defaults.annotate_timeout": 120,
    "server.host": "127.0.0.1",
    "server.port": 8080,
    "server.database_path": ".specmap/specmap.db",
}

# -- Path helpers ---------------------------------------------------------


def _user_config_path() -> Path:
    """Return the path to the user-level TOML config file."""
    config_home = os.environ.get("XDG_CONFIG_HOME") or str(
        Path.home() / ".config"
    )
    return Path(config_home) / "specmap" / "config.toml"


def _repo_config_path() -> Path | None:
    """Return the path to the repo-level TOML config file, or None."""
    repo_root = _detect_repo_root()
    if repo_root is None:
        return None
    return Path(repo_root) / ".specmap" / "config.toml"


def _detect_repo_root() -> str | None:
    """Walk up from cwd looking for .git/."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists():
            return str(current)
        current = current.parent
    return None


# -- TOML helpers ---------------------------------------------------------

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

try:
    import tomli_w as _tomli_w  # type: ignore[import-untyped]

    def _dump_toml(data: dict) -> str:
        import io

        buf = io.BytesIO()
        _tomli_w.dump(data, buf)
        return buf.getvalue().decode()

except ModuleNotFoundError:
    # Minimal TOML writer — covers the flat types we actually store.
    def _dump_toml(data: dict) -> str:  # type: ignore[misc]
        lines: list[str] = []
        for section, values in data.items():
            lines.append(f"[{section}]")
            for k, v in values.items():
                if isinstance(v, list):
                    inner = ", ".join(f'"{i}"' for i in v)
                    lines.append(f"{k} = [{inner}]")
                elif isinstance(v, bool):
                    lines.append(f"{k} = {'true' if v else 'false'}")
                elif isinstance(v, int):
                    lines.append(f"{k} = {v}")
                elif v is None:
                    continue
                else:
                    lines.append(f'{k} = "{v}"')
            lines.append("")
        return "\n".join(lines) + "\n"


def _load_toml(path: Path) -> dict:
    """Load a TOML file and return a flat field-name → value dict."""
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    flat: dict = {}
    for section, values in raw.items():
        if isinstance(values, dict):
            for k, v in values.items():
                flat[f"{section}_{k}" if section != "general" else k] = v
        else:
            flat[section] = values
    return flat


def _save_toml(path: Path, field_name: str, value: object) -> None:
    """Set a single field in a TOML config file, preserving other fields."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if path.exists():
        with open(path, "rb") as f:
            existing = tomllib.load(f)

    # Determine the TOML section and key from the dot-notation key.
    section, key = _field_to_toml_section_key(field_name)
    existing.setdefault(section, {})[key] = value

    path.write_text(_dump_toml(existing))


def _field_to_toml_section_key(field_name: str) -> tuple[str, str]:
    """Map a _KEY_MAP field name to (toml_section, toml_key)."""
    # Reverse lookup: field_name -> dot key
    dot_key: str | None = None
    for dk, fn in _KEY_MAP.items():
        if fn == field_name:
            dot_key = dk
            break
    if dot_key is None:
        return ("general", field_name)
    section = dot_key.rsplit(".", 1)[0]
    key = dot_key.rsplit(".", 1)[1]
    # Flatten forge.github.token -> forge, github_token
    parts = dot_key.split(".")
    if len(parts) == 3:
        section = parts[0]
        key = f"{parts[1]}_{parts[2]}"
    return (section, key)


# -- Masking helper -------------------------------------------------------


def _mask(value: str) -> str:
    """Mask a secret value, showing only the first 7 characters."""
    if len(value) > 7:
        return value[:7] + "****"
    return "****"


# -- Resolve helpers ------------------------------------------------------


def _resolve_value(key: str) -> object:
    """Return the fully-resolved value for a config key.

    Resolution order: env → repo TOML → user TOML → default.
    """
    field_name = _KEY_MAP.get(key)
    if field_name is None:
        return None

    # 1. Check env
    env_var = _ENV_MAP.get(key)
    if env_var and env_var in os.environ:
        raw = os.environ[env_var]
        if key in _INT_KEYS:
            try:
                return int(raw)
            except ValueError:
                return raw
        if key in _LIST_KEYS:
            return [p.strip() for p in raw.split(",") if p.strip()]
        return raw

    # 2. Check repo TOML
    rp = _repo_config_path()
    if rp:
        repo_data = _load_toml(rp)
        if field_name in repo_data:
            return repo_data[field_name]

    # 3. Check user TOML
    user_data = _load_toml(_user_config_path())
    if field_name in user_data:
        return user_data[field_name]

    # 4. Default
    return _DEFAULTS.get(key)


def _resolve_source(key: str) -> str:
    """Return the source label for a config key."""
    field_name = _KEY_MAP.get(key)
    if field_name is None:
        return "default"

    env_var = _ENV_MAP.get(key)
    if env_var and env_var in os.environ:
        return "env"

    rp = _repo_config_path()
    if rp:
        repo_data = _load_toml(rp)
        if field_name in repo_data:
            return "repo"

    user_data = _load_toml(_user_config_path())
    if field_name in user_data:
        return "user"

    return "default"


def _format_value(key: str, value: object) -> str:
    """Format a value for display, masking secrets."""
    if value is None:
        return "(not set)"
    s = str(value)
    if key in _SECRET_KEYS and s:
        return _mask(s)
    return s


# -- Subcommands ----------------------------------------------------------


@config_app.command(name="get")
def config_get(
    key: str = typer.Argument(..., help="Dot-notation config key"),
):
    """Print the resolved value for a configuration key."""
    if key not in _KEY_MAP:
        typer.echo(f"Error: unknown key '{key}'", err=True)
        typer.echo(f"Valid keys: {', '.join(sorted(_KEY_MAP))}", err=True)
        raise typer.Exit(code=1)

    value = _resolve_value(key)
    typer.echo(_format_value(key, value))


@config_app.command(name="set")
def config_set(
    key: str = typer.Argument(..., help="Dot-notation config key"),
    value: str = typer.Argument(..., help="Value to set"),
    repo: bool = typer.Option(False, "--repo", help="Write to repo config instead of user config"),
):
    """Write a value to user config (default) or repo config (with --repo)."""
    if key not in _KEY_MAP:
        typer.echo(f"Error: unknown key '{key}'", err=True)
        typer.echo(f"Valid keys: {', '.join(sorted(_KEY_MAP))}", err=True)
        raise typer.Exit(code=1)

    if repo and key in _REPO_BLOCKED_KEYS:
        typer.echo(
            f"Error: '{key}' contains a secret and must not be stored in repo config. "
            f"Use 'specmap config set {key} <value>' (without --repo) to store it in user config.",
            err=True,
        )
        raise typer.Exit(code=1)

    field_name = _KEY_MAP[key]

    # Parse the value to the appropriate type.
    parsed: object
    if key in _INT_KEYS:
        try:
            parsed = int(value)
        except ValueError:
            typer.echo(f"Error: '{key}' requires an integer value", err=True)
            raise typer.Exit(code=1)
    elif key in _LIST_KEYS:
        parsed = [p.strip() for p in value.split(",") if p.strip()]
    else:
        parsed = value

    if repo:
        rp = _repo_config_path()
        if rp is None:
            typer.echo("Error: not inside a git repository", err=True)
            raise typer.Exit(code=1)
        _save_toml(rp, field_name, parsed)
        typer.echo(f"Set {key} in {rp}")
    else:
        up = _user_config_path()
        _save_toml(up, field_name, parsed)
        typer.echo(f"Set {key} in {up}")


@config_app.command(name="list")
def config_list():
    """Show all resolved configuration values with source labels."""
    for key in sorted(_KEY_MAP):
        value = _resolve_value(key)
        source = _resolve_source(key)
        display = _format_value(key, value)
        typer.echo(f"{key} = {display}  ({source})")


@config_app.command(name="path")
def config_path():
    """Print the paths to user and repo configuration files."""
    typer.echo(f"User config: {_user_config_path()}")
    rp = _repo_config_path()
    if rp:
        typer.echo(f"Repo config: {rp}")
    else:
        typer.echo("Repo config: (not in a git repository)")


@config_app.command(name="edit")
def config_edit(
    repo: bool = typer.Option(False, "--repo", help="Edit repo config instead of user config"),
):
    """Open the configuration file in $EDITOR (or vi)."""
    editor = os.environ.get("EDITOR", "vi")

    if repo:
        path = _repo_config_path()
        if path is None:
            typer.echo("Error: not inside a git repository", err=True)
            raise typer.Exit(code=1)
    else:
        path = _user_config_path()

    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("")

    subprocess.run([editor, str(path)])


@config_app.command(name="migrate")
def config_migrate():
    """Migrate .specmap/config.json to TOML config files.

    Reads the JSON config, writes secrets to user config and
    repo settings to repo config, then renames the JSON file to .json.bak.
    """
    repo_root = _detect_repo_root()
    if repo_root is None:
        typer.echo("Error: not inside a git repository", err=True)
        raise typer.Exit(code=1)

    json_path = Path(repo_root) / ".specmap" / "config.json"
    if not json_path.exists():
        typer.echo(f"No config file found at {json_path}", err=True)
        raise typer.Exit(code=1)

    try:
        with open(json_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        typer.echo(f"Error reading {json_path}: {e}", err=True)
        raise typer.Exit(code=1)

    user_path = _user_config_path()
    rp = _repo_config_path()

    migrated_user: list[str] = []
    migrated_repo: list[str] = []

    for dot_key, field_name in _KEY_MAP.items():
        if field_name not in data:
            continue
        value = data[field_name]
        if dot_key in _SECRET_KEYS:
            _save_toml(user_path, field_name, value)
            migrated_user.append(dot_key)
        elif rp:
            _save_toml(rp, field_name, value)
            migrated_repo.append(dot_key)

    # Rename the original JSON file
    backup_path = json_path.with_suffix(".json.bak")
    json_path.rename(backup_path)

    typer.echo(f"Migrated {json_path} -> TOML")
    if migrated_user:
        typer.echo(f"  User config ({user_path}): {', '.join(migrated_user)}")
    if migrated_repo:
        typer.echo(f"  Repo config ({rp}): {', '.join(migrated_repo)}")
    typer.echo(f"  Original renamed to {backup_path}")

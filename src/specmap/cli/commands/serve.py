"""specmap serve — run the API server."""

from __future__ import annotations

import logging
import os
import socket
import threading
import webbrowser

import typer

from specmap.cli import app

serve_app = typer.Typer()


def _port_is_free(host: str, port: int) -> bool:
    """Check whether a TCP port is available to bind."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def _find_open_port(host: str, preferred: int, max_attempts: int = 20) -> int:
    """Return *preferred* if free, otherwise scan upward for an open port."""
    if _port_is_free(host, preferred):
        return preferred
    for offset in range(1, max_attempts + 1):
        candidate = preferred + offset
        if _port_is_free(host, candidate):
            return candidate
    # Last resort: let the OS pick
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def _open_browser_when_ready(url: str, timeout: float = 10.0):
    def _open():
        import time
        import urllib.request

        # Poll /healthz to confirm the app is fully up (not just the reloader)
        health_url = url.rstrip("/") + "/healthz"
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                resp = urllib.request.urlopen(health_url, timeout=1)
                if resp.status == 200:
                    break
            except Exception:
                time.sleep(0.3)
        webbrowser.open(url)

    threading.Thread(target=_open, daemon=True).start()


def _infer_provider(api_key: str) -> tuple[str, str]:
    """Return (provider_name, default_model) based on the API key prefix."""
    if api_key.startswith("sk-ant-"):
        return ("Anthropic", "anthropic/claude-sonnet-4-20250514")
    if api_key.startswith("sk-"):
        return ("OpenAI", "gpt-4o-mini")
    return ("Unknown", "gpt-4o-mini")


def _maybe_prompt_api_key() -> tuple[str | None, str | None]:
    """Prompt the user for an LLM API key and model if not already set.

    Returns (api_key, model). Either or both may be None.
    Skipped entirely if SPECMAP_API_KEY or SPECMAP_SKIP_API_KEY_CHECK is set.
    """
    if os.environ.get("SPECMAP_SKIP_API_KEY_CHECK"):
        return None, None

    # Check merged config (includes env vars, user TOML, repo TOML)
    from specmap.config import CoreConfig

    core = CoreConfig.load()
    if core.api_key:
        return core.api_key, None

    import questionary
    from questionary import Style
    from rich.console import Console

    _PROMPT_STYLE = Style([
        ("highlighted", "fg:#5f819d bold"),
    ])

    console = Console()
    console.print(
        "\n[bold]SPECMAP_API_KEY[/bold] is not set. "
        "An API key enables AI-powered features (annotation generation, guided walkthroughs).\n"
        "[dim]specmap runs locally — your key is stored on this machine and used only to call your chosen LLM provider.[/dim]\n"
    )

    choice = questionary.select(
        "How would you like to proceed?",
        choices=[
            questionary.Choice("Enter an API key", value="enter"),
            questionary.Choice("Read key from a file", value="file"),
            questionary.Choice("Skip (disable AI features)", value="skip"),
        ],
        style=_PROMPT_STYLE,
    ).ask()

    if choice is None:  # user pressed Ctrl-C
        return None, None

    api_key: str | None = None

    if choice == "enter":
        key = questionary.text("API key:").ask()
        if key and key.strip():
            api_key = key.strip()
        else:
            console.print("[yellow]No key entered, skipping.[/yellow]")
            return None, None

    elif choice == "file":
        raw_path = questionary.path("Path to API key file:").ask()
        if raw_path is None:
            return None, None
        path = os.path.abspath(os.path.expanduser(raw_path.strip()))
        try:
            key = open(path).read().strip()  # noqa: SIM115
            if key:
                console.print(f"[green]Read key from {path}[/green]")
                api_key = key
            else:
                console.print("[yellow]File was empty, skipping.[/yellow]")
                return None, None
        except (OSError, IOError) as e:
            console.print(f"[red]Could not read file: {e}[/red]")
            return None, None

    else:  # skip
        console.print("[dim]Skipping — AI features will be disabled.[/dim]\n")
        return None, None

    # We have a key — detect provider and prompt for model
    provider, default_model = _infer_provider(api_key)
    console.print(f"[green]✓ Detected provider: {provider}[/green]")

    model = questionary.text("Model:", default=default_model).ask()
    if model is None:  # Ctrl-C
        model = default_model

    # Offer to save to user config
    from specmap.config import SpecmapConfig, save_user_config, user_config_path

    final_model = model.strip() or default_model
    save = questionary.confirm(
        f"Save to {user_config_path()}?",
        default=True,
    ).ask()
    if save:
        new_cfg = SpecmapConfig(api_key=api_key, model=final_model)
        path = save_user_config(new_cfg)
        console.print(f"[green]Saved to {path}[/green]")

    return api_key, final_model


@app.command()
def serve(
    port: int = typer.Option(8080, help="Port to listen on"),
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    db: str = typer.Option(".specmap/specmap.db", help="SQLite database path"),
    static_dir: str = typer.Option("", help="Directory with built frontend files"),
    reload: bool = typer.Option(False, help="Enable auto-reload for development"),
    no_open: bool = typer.Option(False, "--no-open", help="Don't auto-open browser"),
):
    """Run the specmap API server."""
    import uvicorn

    from specmap.server.config import ServerConfig

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Static dir resolution: --static-dir > STATIC_DIR env > bundled _static/
    resolved_static = static_dir or os.environ.get("STATIC_DIR", "")
    if not resolved_static:
        from specmap.server.static import get_bundled_static_dir

        resolved_static = get_bundled_static_dir() or ""

    # Prompt for API key and model if not set
    api_key, model = _maybe_prompt_api_key()
    if api_key:
        os.environ["SPECMAP_API_KEY"] = api_key
    if model and not os.environ.get("SPECMAP_MODEL"):
        os.environ["SPECMAP_MODEL"] = model

    actual_port = _find_open_port(host, port)
    if actual_port != port:
        logging.getLogger("specmap.server").info(
            "Port %d in use, using %d instead", port, actual_port
        )

    config = ServerConfig.from_env(
        port=str(actual_port), host=host, database_path=db, static_dir=resolved_static
    )

    # Auto-open browser when serving a frontend (not a bare API)
    if resolved_static and not no_open:
        url = f"http://{'localhost' if host in ('0.0.0.0', '127.0.0.1') else host}:{actual_port}"
        _open_browser_when_ready(url)

    if reload:
        # Stash config values as env vars so the factory can reconstruct
        # the config when uvicorn reloads the process.
        os.environ["PORT"] = str(config.port)
        os.environ["HOST"] = config.host
        os.environ["DATABASE_PATH"] = config.database_path
        if config.static_dir:
            os.environ["STATIC_DIR"] = config.static_dir
        uvicorn.run(
            "specmap.server.app:create_app",
            factory=True,
            host=config.host,
            port=config.port,
            reload=True,
        )
    else:
        from specmap.server.app import create_app

        app_instance = create_app(config)
        uvicorn.run(app_instance, host=config.host, port=config.port)

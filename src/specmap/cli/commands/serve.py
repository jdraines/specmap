"""specmap serve — run the API server."""

from __future__ import annotations

import logging
import os
import threading
import webbrowser

import typer

from specmap.cli import app

serve_app = typer.Typer()


def _open_browser_after_delay(url: str, delay: float = 0.8):
    def _open():
        import time

        time.sleep(delay)
        webbrowser.open(url)

    threading.Thread(target=_open, daemon=True).start()


def _maybe_prompt_api_key() -> str | None:
    """Prompt the user for an LLM API key if not already set.

    Returns the key string, or None if skipped.
    Skipped entirely if SPECMAP_API_KEY or SPECMAP_SKIP_API_KEY_CHECK is set.
    """
    if os.environ.get("SPECMAP_API_KEY") or os.environ.get("SPECMAP_SKIP_API_KEY_CHECK"):
        return os.environ.get("SPECMAP_API_KEY") or None

    from rich.console import Console
    from rich.prompt import Prompt

    console = Console()
    console.print(
        "\n[bold]SPECMAP_API_KEY[/bold] is not set. "
        "An API key enables AI-powered features (annotation generation, guided walkthroughs).\n"
    )

    choice = Prompt.ask(
        "How would you like to proceed?",
        choices=["enter", "file", "skip"],
        default="skip",
    )

    if choice == "enter":
        key = Prompt.ask("API key").strip()
        if key:
            return key
        console.print("[yellow]No key entered, skipping.[/yellow]")
        return None

    if choice == "file":
        raw_path = Prompt.ask("Path to API key file").strip()
        path = os.path.abspath(os.path.expanduser(raw_path))
        try:
            key = open(path).read().strip()  # noqa: SIM115
            if key:
                console.print(f"[green]Read key from {path}[/green]")
                return key
            console.print("[yellow]File was empty, skipping.[/yellow]")
        except (OSError, IOError) as e:
            console.print(f"[red]Could not read file: {e}[/red]")
        return None

    # skip
    console.print("[dim]Skipping — AI features will be disabled.[/dim]\n")
    return None


@app.command()
def serve(
    port: int = typer.Option(8080, help="Port to listen on"),
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    db: str = typer.Option("./specmap.db", help="SQLite database path"),
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

    # Prompt for API key if not set
    api_key = _maybe_prompt_api_key()
    if api_key:
        os.environ["SPECMAP_API_KEY"] = api_key

    config = ServerConfig.from_env(
        port=str(port), host=host, database_path=db, static_dir=resolved_static
    )

    # Auto-open browser when serving a frontend (not a bare API)
    if resolved_static and not no_open:
        url = f"http://{'localhost' if host in ('0.0.0.0', '127.0.0.1') else host}:{port}"
        _open_browser_after_delay(url)

    if reload:
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

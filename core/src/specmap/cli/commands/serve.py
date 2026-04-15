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

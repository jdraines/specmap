"""specmap serve — run the API server."""

from __future__ import annotations

import logging

import typer

from specmap.cli import app

serve_app = typer.Typer()


@app.command()
def serve(
    port: int = typer.Option(8080, help="Port to listen on"),
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    db: str = typer.Option("./specmap.db", help="SQLite database path"),
    static_dir: str = typer.Option("", help="Directory with built frontend files"),
    reload: bool = typer.Option(False, help="Enable auto-reload for development"),
):
    """Run the specmap API server."""
    import uvicorn

    from specmap.server.config import ServerConfig

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    config = ServerConfig.from_env(
        port=str(port), host=host, database_path=db, static_dir=static_dir
    )

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

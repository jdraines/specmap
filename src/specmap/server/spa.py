"""SPA (Single Page Application) static file serving."""

from __future__ import annotations

from pathlib import Path

from starlette.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class SPAStaticFiles(StaticFiles):
    """StaticFiles subclass that falls back to index.html for SPA routing."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            response = await super().get_response(path, scope)
            if response.status_code == 404:
                return await self._index_response()
            return response
        except Exception:
            return await self._index_response()

    async def _index_response(self) -> FileResponse:
        # self.directory is set by StaticFiles.__init__
        return FileResponse(
            Path(str(self.all_directories[0])) / "index.html",
            headers={"Cache-Control": "no-cache"},
        )


def mount_spa(app, static_dir: str):
    """Mount SPA static files on the FastAPI app.

    Assets under /assets/ get immutable cache headers.
    Everything else falls back to index.html.
    """
    from fastapi import FastAPI

    assert isinstance(app, FastAPI)
    static_path = Path(static_dir)
    if not static_path.is_dir():
        return

    assets_path = static_path / "assets"
    if assets_path.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(assets_path)),
            name="assets",
        )

    # Catch-all SPA handler — must be mounted last
    app.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="spa")

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException


def mount_spa_static_files(app: FastAPI, dist_dir: Path) -> None:
    """ビルド済みSPAが存在する場合に静的配信とfallbackを登録する。"""
    index_path = dist_dir / "index.html"
    if not index_path.is_file():
        return

    assets_dir = dist_dir / "assets"
    if assets_dir.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=assets_dir),
            name="spa-assets",
        )

    @app.get("/{path:path}", include_in_schema=False)
    def spa_fallback(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        return FileResponse(index_path, media_type="text/html")

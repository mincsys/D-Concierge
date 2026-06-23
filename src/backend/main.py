from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from backend.app.factory import create_app


def create_backend_app(config_path: Path = Path("config.yaml")) -> FastAPI:
    """外部サーバ起動用のFastAPIファクトリ。"""

    return create_app(config_path=config_path)

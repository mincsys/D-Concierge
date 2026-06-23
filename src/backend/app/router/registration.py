from __future__ import annotations

from fastapi import FastAPI

from backend.presentation.rest.account import router as account_router
from backend.presentation.rest.app_config import router as app_config_router
from backend.presentation.rest.chat import router as chat_router
from backend.presentation.rest.delivery import router as delivery_router


def register_routes(app: FastAPI) -> None:
    """FastAPIアプリへREST/SSEルートを登録する。"""

    app.include_router(app_config_router)
    app.include_router(account_router)
    app.include_router(chat_router)
    app.include_router(delivery_router)

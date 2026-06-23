from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.infrastructure.config.settings import AppSettings
from backend.presentation.rest.dependencies import (
    AuthenticatedUser,
    get_authenticated_user,
    get_settings,
)
from backend.presentation.schemas.app_config import AppConfigResponse

router = APIRouter()


@router.get("/api/app-config")
async def get_app_config(
    settings: Annotated[AppSettings, Depends(get_settings)],
    _authenticated_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
) -> AppConfigResponse:
    """画面へ公開できるUI設定だけを返す。"""

    return AppConfigResponse(
        welcome_message=settings.ui.welcome_message,
        sub_welcome_message=settings.ui.sub_welcome_message,
        input_suggestions=settings.ui.input_suggestions,
    )

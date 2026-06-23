from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Request
from sqlalchemy.orm import Session, sessionmaker

from backend.application.account.authenticate_session import (
    AuthenticateSessionCommand,
    AuthenticateSessionUseCase,
)
from backend.infrastructure.config.settings import AppSettings
from backend.infrastructure.database.repositories.account import (
    SqlAlchemyAccountRepository,
)
from backend.infrastructure.database.session.transaction_manager import (
    SqlAlchemyTransactionManager,
)
from backend.infrastructure.runtime.clock import SystemClock
from backend.infrastructure.security.session_token import SecretsSessionTokenProvider
from backend.presentation.errors.http import trace_id_from_request
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError

LOGIN_SESSION_COOKIE_NAME = "d_concierge_session"


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """保護対象APIへ渡す認証済みユーザ。"""

    user_id: str
    user_name: str


async def get_settings(request: Request) -> AppSettings:
    """FastAPI app stateから型付き設定を取得する。"""

    settings = request.app.state.settings
    if not isinstance(settings, AppSettings):
        raise AppError(
            error_type=ErrorType.CONFIGURATION,
            trace=True,
            diagnostic_message="アプリケーション設定が初期化されていません。",
        )
    return settings


def get_session_factory(request: Request) -> sessionmaker[Session]:
    """FastAPI app stateからDBセッションファクトリを取得する。"""

    session_factory = request.app.state.session_factory
    if not isinstance(session_factory, sessionmaker):
        raise AppError(
            error_type=ErrorType.CONFIGURATION,
            trace=True,
            diagnostic_message="DBセッションファクトリが初期化されていません。",
        )
    return session_factory


async def get_authenticated_user(
    request: Request,
    session_token: Annotated[
        str | None,
        Cookie(alias=LOGIN_SESSION_COOKIE_NAME),
    ] = None,
) -> AuthenticatedUser:
    """ログインセッションCookieを検証する依存関係。"""

    settings = await get_settings(request)
    session_factory = get_session_factory(request)
    with session_factory() as session:
        repository = SqlAlchemyAccountRepository(session)
        use_case = AuthenticateSessionUseCase(
            repository=repository,
            transaction_manager=SqlAlchemyTransactionManager(session),
            session_token_provider=SecretsSessionTokenProvider(),
            clock=SystemClock(settings.app.timezone),
        )
        result = use_case.execute(
            AuthenticateSessionCommand(
                session_token=session_token,
                trace_id=trace_id_from_request(request),
            )
        )
    return AuthenticatedUser(
        user_id=result.user_id,
        user_name=result.user_name,
    )

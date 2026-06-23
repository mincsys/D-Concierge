from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response, status

from backend.application.account.change_password import (
    ChangePasswordCommand,
    ChangePasswordUseCase,
)
from backend.application.account.change_user_name import (
    ChangeUserNameCommand,
    ChangeUserNameUseCase,
)
from backend.application.account.delete_account import (
    DeleteAccountCommand,
    DeleteAccountUseCase,
)
from backend.application.account.login import LoginCommand, LoginUseCase
from backend.application.account.logout import LogoutCommand, LogoutUseCase
from backend.application.account.register_account import (
    RegisterAccountCommand,
    RegisterAccountUseCase,
)
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.infrastructure.database.repositories.account import (
    SqlAlchemyAccountRepository,
)
from backend.infrastructure.database.session.transaction_manager import (
    SqlAlchemyTransactionManager,
)
from backend.infrastructure.runtime.clock import SystemClock
from backend.infrastructure.security.password_hasher import PasslibPasswordHasher
from backend.infrastructure.security.session_token import SecretsSessionTokenProvider
from backend.infrastructure.trace_log.writer import TraceLogWriter
from backend.presentation.errors.http import trace_id_from_request
from backend.presentation.rest.dependencies import (
    LOGIN_SESSION_COOKIE_NAME,
    AuthenticatedUser,
    get_authenticated_user,
    get_session_factory,
    get_settings,
)
from backend.presentation.schemas.account import (
    ChangePasswordRequest,
    ChangeUserNameRequest,
    DeleteAccountResponse,
    LoginRequest,
    RegisterAccountRequest,
    UserPayload,
    UserResponse,
)
from backend.shared.errors.error_type import ErrorType
from backend.shared.tracing.trace_id import TraceId

router = APIRouter()

SESSION_MAX_AGE_SECONDS = 400 * 24 * 60 * 60


@dataclass(frozen=True, slots=True)
class AccountTraceLogger:
    """削除ジョブ登録失敗をREST境界のトレースログへ保存する。"""

    writer: TraceLogWriter
    request: Request

    def write_account_event(
        self,
        event_name: str,
        user_id: str,
        trace_id: str,
        diagnostic_message: str,
    ) -> None:
        try:
            self.writer.write(
                TraceLogRecord(
                    occurred_at=datetime.now(UTC),
                    trace_id=TraceId(trace_id),
                    event_name=event_name,
                    stage="application.account.delete_account",
                    error_type=ErrorType.SYSTEM,
                    message=diagnostic_message,
                    exception_type="AccountDeletionDispatchFailed",
                    stacktrace="",
                    http_method=self.request.method,
                    path=self.request.url.path,
                    status_code=status.HTTP_202_ACCEPTED,
                    user_id=user_id,
                )
            )
        except Exception:
            return


@router.get("/api/auth/me", response_model=UserResponse)
async def get_current_user(
    authenticated_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
) -> UserResponse:
    """認証状態を確認する。"""

    return _user_response(authenticated_user.user_id, authenticated_user.user_name)


@router.post("/api/auth/register", response_model=UserResponse)
async def register_account(
    request: Request,
    response: Response,
    body: RegisterAccountRequest,
    session_token: Annotated[
        str | None,
        Cookie(alias=LOGIN_SESSION_COOKIE_NAME),
    ] = None,
) -> UserResponse:
    """アカウント登録を受け付ける。"""

    settings = await get_settings(request)
    session_factory = get_session_factory(request)
    with session_factory() as session:
        use_case = RegisterAccountUseCase(
            repository=SqlAlchemyAccountRepository(session),
            transaction_manager=SqlAlchemyTransactionManager(session),
            password_hasher=PasslibPasswordHasher(),
            session_token_provider=SecretsSessionTokenProvider(),
            clock=SystemClock(settings.app.timezone),
        )
        result = use_case.execute(
            RegisterAccountCommand(
                user_id=body.user_id,
                user_name=body.user_name,
                password=body.password,
                password_confirmation=body.password_confirmation,
                existing_session_token=session_token,
                trace_id=trace_id_from_request(request),
            )
        )
    _set_login_cookie(response, result.session_token)
    return _user_response(result.user.user_id, result.user.user_name)


@router.post("/api/auth/login", response_model=UserResponse)
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    session_token: Annotated[
        str | None,
        Cookie(alias=LOGIN_SESSION_COOKIE_NAME),
    ] = None,
) -> UserResponse:
    """ログインを受け付ける。"""

    settings = await get_settings(request)
    session_factory = get_session_factory(request)
    with session_factory() as session:
        use_case = LoginUseCase(
            repository=SqlAlchemyAccountRepository(session),
            transaction_manager=SqlAlchemyTransactionManager(session),
            password_hasher=PasslibPasswordHasher(),
            session_token_provider=SecretsSessionTokenProvider(),
            clock=SystemClock(settings.app.timezone),
        )
        result = use_case.execute(
            LoginCommand(
                user_id=body.user_id,
                password=body.password,
                existing_session_token=session_token,
                trace_id=trace_id_from_request(request),
            )
        )
    _set_login_cookie(response, result.session_token)
    return _user_response(result.user.user_id, result.user.user_name)


@router.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    session_token: Annotated[
        str | None,
        Cookie(alias=LOGIN_SESSION_COOKIE_NAME),
    ] = None,
) -> Response:
    """ログアウトを受け付ける。"""

    session_factory = get_session_factory(request)
    with session_factory() as session:
        use_case = LogoutUseCase(
            repository=SqlAlchemyAccountRepository(session),
            transaction_manager=SqlAlchemyTransactionManager(session),
            session_token_provider=SecretsSessionTokenProvider(),
        )
        use_case.execute(
            LogoutCommand(
                session_token=session_token,
                trace_id=trace_id_from_request(request),
            )
        )
    _expire_login_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.patch("/api/account/name", response_model=UserResponse)
async def change_user_name(
    request: Request,
    body: ChangeUserNameRequest,
    authenticated_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
) -> UserResponse:
    """ユーザ名変更を受け付ける。"""

    settings = await get_settings(request)
    session_factory = get_session_factory(request)
    with session_factory() as session:
        use_case = ChangeUserNameUseCase(
            repository=SqlAlchemyAccountRepository(session),
            transaction_manager=SqlAlchemyTransactionManager(session),
            clock=SystemClock(settings.app.timezone),
        )
        result = use_case.execute(
            ChangeUserNameCommand(
                authenticated_user_id=authenticated_user.user_id,
                user_name=body.user_name,
                trace_id=trace_id_from_request(request),
            )
        )
    return _user_response(result.user_id, result.user_name)


@router.patch("/api/account/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    request: Request,
    response: Response,
    body: ChangePasswordRequest,
    authenticated_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
) -> Response:
    """パスワード変更を受け付ける。"""

    settings = await get_settings(request)
    session_factory = get_session_factory(request)
    with session_factory() as session:
        use_case = ChangePasswordUseCase(
            repository=SqlAlchemyAccountRepository(session),
            transaction_manager=SqlAlchemyTransactionManager(session),
            password_hasher=PasslibPasswordHasher(),
            clock=SystemClock(settings.app.timezone),
        )
        use_case.execute(
            ChangePasswordCommand(
                authenticated_user_id=authenticated_user.user_id,
                current_password=body.current_password,
                new_password=body.new_password,
                new_password_confirmation=body.new_password_confirmation,
                trace_id=trace_id_from_request(request),
            )
        )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.delete(
    "/api/account",
    response_model=DeleteAccountResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def delete_account(
    request: Request,
    response: Response,
    authenticated_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
) -> DeleteAccountResponse:
    """アカウント削除受付を受け付ける。"""

    settings = await get_settings(request)
    session_factory = get_session_factory(request)
    trace_log_writer = _trace_log_writer(request)
    with session_factory() as session:
        use_case = DeleteAccountUseCase(
            repository=SqlAlchemyAccountRepository(session),
            transaction_manager=SqlAlchemyTransactionManager(session),
            dispatcher=request.app.state.account_deletion_dispatcher,
            trace_logger=AccountTraceLogger(trace_log_writer, request),
            clock=SystemClock(settings.app.timezone),
        )
        result = use_case.execute(
            DeleteAccountCommand(
                authenticated_user_id=authenticated_user.user_id,
                trace_id=trace_id_from_request(request),
            )
        )
    _expire_login_cookie(response)
    return DeleteAccountResponse(account_state=result.account_state)


def _trace_log_writer(request: Request) -> TraceLogWriter:
    writer = request.app.state.trace_log_writer
    if not isinstance(writer, TraceLogWriter):
        raise RuntimeError("トレースログWriterが初期化されていません。")
    return writer


def _user_response(user_id: str, user_name: str) -> UserResponse:
    return UserResponse(user=UserPayload(user_id=user_id, user_name=user_name))


def _set_login_cookie(response: Response, session_token: str) -> None:
    response.headers.append(
        "set-cookie",
        (
            f"{LOGIN_SESSION_COOKIE_NAME}={session_token}; HttpOnly; "
            f"Max-Age={SESSION_MAX_AGE_SECONDS}; Path=/; SameSite=Lax"
        ),
    )


def _expire_login_cookie(response: Response) -> None:
    response.headers.append(
        "set-cookie",
        (f"{LOGIN_SESSION_COOKIE_NAME}=; HttpOnly; Max-Age=0; Path=/; SameSite=Lax"),
    )

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from traceback import format_exception
from typing import Protocol, TypedDict, runtime_checkable

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.application.ports.runtime.interface import IdGeneratorPort
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.shared.tracing.trace_id import TraceId, new_trace_id
from backend.shared.user_messages import (
    AUTHENTICATION_REQUIRED,
    CONFIGURATION_ERROR,
    CONFLICT,
    FORBIDDEN,
    INPUT_ERROR,
    NOT_FOUND,
    SYSTEM_ERROR,
)


class ErrorResponsePayload(TypedDict):
    error: str
    message: str


class FieldErrorResponsePayload(TypedDict):
    error: str
    message: str
    field_errors: dict[str, str]


@runtime_checkable
class FieldErrorProvider(Protocol):
    """項目別エラーを持つ例外の構造。"""

    field_errors: dict[str, str]


class TraceLogWritePort(Protocol):
    """トレースログ出力の最小境界。"""

    def write(self, record: TraceLogRecord) -> Path: ...


class TraceErrorMiddleware:
    """REST境界で予期しない例外をtrace_id付き応答へ変換する。"""

    def __init__(
        self,
        app: ASGIApp,
        trace_log_writer: TraceLogWritePort,
        id_generator: IdGeneratorPort,
    ) -> None:
        self._app = app
        self._trace_log_writer = trace_log_writer
        self._id_generator = id_generator

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        trace_id = new_trace_id(self._id_generator)
        _set_trace_id(scope, trace_id)

        async def send_with_trace_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["x-trace-id"] = str(trace_id)
            await send(message)

        try:
            await self._app(scope, receive, send_with_trace_id)
        except Exception as exception:
            request = Request(scope, receive=receive)
            response = build_error_response(
                request,
                exception,
                self._trace_log_writer,
                trace_id,
            )
            await response(scope, receive, send)


def register_error_handlers(
    app: FastAPI,
    trace_log_writer: TraceLogWritePort,
) -> None:
    """FastAPI標準エラーを共通RESTエラー応答へ変換する。"""

    async def app_error_handler(
        request: Request,
        exception: Exception,
    ) -> JSONResponse:
        if not isinstance(exception, AppError):
            return build_error_response(request, exception, trace_log_writer)
        return build_error_response(request, exception, trace_log_writer)

    async def http_error_handler(
        request: Request,
        exception: Exception,
    ) -> JSONResponse:
        if not isinstance(exception, HTTPException):
            return build_error_response(request, exception, trace_log_writer)
        return build_http_exception_response(request, exception, trace_log_writer)

    async def validation_error_handler(
        request: Request,
        exception: Exception,
    ) -> JSONResponse:
        if not isinstance(exception, RequestValidationError):
            return build_error_response(request, exception, trace_log_writer)
        return build_validation_error_response(request, exception, trace_log_writer)

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)


def status_code_for_error_type(error_type: ErrorType) -> int:
    """AppError分類をHTTPステータスへ変換する。"""

    if error_type is ErrorType.INPUT:
        return status.HTTP_400_BAD_REQUEST
    if error_type is ErrorType.NOT_FOUND:
        return status.HTTP_404_NOT_FOUND
    if error_type is ErrorType.CONFLICT:
        return status.HTTP_409_CONFLICT
    if error_type is ErrorType.CONFIGURATION:
        return status.HTTP_500_INTERNAL_SERVER_ERROR
    if error_type is ErrorType.FORBIDDEN:
        return status.HTTP_403_FORBIDDEN
    return status.HTTP_500_INTERNAL_SERVER_ERROR


def build_error_response(
    request: Request,
    exception: Exception,
    trace_log_writer: TraceLogWritePort,
    trace_id: TraceId | None = None,
) -> JSONResponse:
    """例外を利用者向けHTTP応答と必要なトレースログへ変換する。"""

    response_trace_id = (
        trace_id
        if trace_id is not None
        else trace_id_from_request(
            request,
        )
    )
    if _is_authentication_required_error(exception):
        error_type = ErrorType.FORBIDDEN
        response_status = status.HTTP_401_UNAUTHORIZED
        user_message = AUTHENTICATION_REQUIRED
        error_code = "unauthorized"
        trace_message = ""
        should_trace = False
    elif isinstance(exception, AppError):
        error_type = exception.error_type
        response_status = status_code_for_error_type(error_type)
        user_message = _user_message_for_error_type(error_type)
        error_code = _error_code_for_error_type(error_type)
        trace_message = exception.diagnostic_message
        should_trace = exception.trace
    else:
        error_type = ErrorType.SYSTEM
        response_status = status.HTTP_500_INTERNAL_SERVER_ERROR
        user_message = SYSTEM_ERROR
        error_code = "internal_error"
        trace_message = str(exception)
        should_trace = True

    if should_trace:
        record = TraceLogRecord(
            occurred_at=datetime.now(UTC),
            trace_id=response_trace_id,
            event_name="api_failed",
            stage="presentation.rest",
            error_type=error_type,
            message=trace_message,
            exception_type=type(exception).__name__,
            stacktrace="".join(
                format_exception(type(exception), exception, exception.__traceback__),
            ),
            http_method=request.method,
            path=request.url.path,
            status_code=response_status,
        )
        _write_trace_log(trace_log_writer, record)

    return JSONResponse(
        status_code=response_status,
        headers={"x-trace-id": str(response_trace_id)},
        content=_error_response_payload(error_code, user_message, exception),
    )


def build_http_exception_response(
    request: Request,
    exception: HTTPException,
    trace_log_writer: TraceLogWritePort,
) -> JSONResponse:
    """HTTPExceptionを共通RESTエラー応答へ変換する。"""

    response_status = exception.status_code
    error_type = _error_type_for_status(response_status)
    trace_id = trace_id_from_request(request)
    should_trace = response_status >= status.HTTP_500_INTERNAL_SERVER_ERROR
    message = _http_exception_message(exception, error_type)
    if should_trace:
        record = TraceLogRecord(
            occurred_at=datetime.now(UTC),
            trace_id=trace_id,
            event_name="api_failed",
            stage="presentation.rest",
            error_type=error_type,
            message=message,
            exception_type=type(exception).__name__,
            stacktrace="".join(
                format_exception(type(exception), exception, exception.__traceback__),
            ),
            http_method=request.method,
            path=request.url.path,
            status_code=response_status,
        )
        _write_trace_log(trace_log_writer, record)
    return JSONResponse(
        status_code=response_status,
        headers={"x-trace-id": str(trace_id)},
        content=_error_response_payload(
            _error_code_for_status(response_status), message
        ),
    )


def build_validation_error_response(
    request: Request,
    exception: RequestValidationError,
    trace_log_writer: TraceLogWritePort,
) -> JSONResponse:
    """リクエスト検証エラーを共通RESTエラー応答へ変換する。"""

    return build_error_response(
        request,
        AppError(
            error_type=ErrorType.INPUT,
            trace=False,
            diagnostic_message=str(exception),
            cause=exception,
        ),
        trace_log_writer,
    )


def trace_id_from_request(request: Request) -> TraceId:
    """request.stateから入口で生成済みのtrace_idを取得する。"""

    trace_id = getattr(request.state, "trace_id", None)
    if isinstance(trace_id, TraceId):
        return trace_id
    return new_trace_id()


def _set_trace_id(scope: Scope, trace_id: TraceId) -> None:
    state = scope.get("state")
    if not isinstance(state, dict):
        state = {}
        scope["state"] = state
    state["trace_id"] = trace_id


def _write_trace_log(
    trace_log_writer: TraceLogWritePort,
    record: TraceLogRecord,
) -> None:
    try:
        trace_log_writer.write(record)
    except Exception:
        return


def _user_message_for_error_type(error_type: ErrorType) -> str:
    if error_type is ErrorType.INPUT:
        return INPUT_ERROR
    if error_type is ErrorType.NOT_FOUND:
        return NOT_FOUND
    if error_type is ErrorType.CONFLICT:
        return CONFLICT
    if error_type is ErrorType.CONFIGURATION:
        return CONFIGURATION_ERROR
    if error_type is ErrorType.FORBIDDEN:
        return FORBIDDEN
    return SYSTEM_ERROR


def _error_code_for_error_type(error_type: ErrorType) -> str:
    if error_type is ErrorType.INPUT:
        return "validation_error"
    if error_type is ErrorType.NOT_FOUND:
        return "not_found"
    if error_type is ErrorType.CONFLICT:
        return "conflict"
    if error_type is ErrorType.CONFIGURATION:
        return "configuration_error"
    if error_type is ErrorType.FORBIDDEN:
        return "forbidden"
    return "internal_error"


def _error_type_for_status(response_status: int) -> ErrorType:
    if response_status == status.HTTP_404_NOT_FOUND:
        return ErrorType.NOT_FOUND
    if response_status == status.HTTP_409_CONFLICT:
        return ErrorType.CONFLICT
    if response_status in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ):
        return ErrorType.FORBIDDEN
    if response_status < status.HTTP_500_INTERNAL_SERVER_ERROR:
        return ErrorType.INPUT
    return ErrorType.SYSTEM


def _error_code_for_status(response_status: int) -> str:
    if response_status == status.HTTP_401_UNAUTHORIZED:
        return "unauthorized"
    if response_status == status.HTTP_403_FORBIDDEN:
        return "forbidden"
    return _error_code_for_error_type(_error_type_for_status(response_status))


def _http_exception_message(
    exception: HTTPException,
    error_type: ErrorType,
) -> str:
    if isinstance(exception.detail, str):
        return exception.detail
    return _user_message_for_error_type(error_type)


def _error_response_payload(
    error_code: str,
    message: str,
    exception: Exception | None = None,
) -> ErrorResponsePayload | FieldErrorResponsePayload:
    if isinstance(exception, FieldErrorProvider) and bool(exception.field_errors):
        return {
            "error": error_code,
            "message": message,
            "field_errors": exception.field_errors,
        }
    return {"error": error_code, "message": message}


def _is_authentication_required_error(exception: Exception) -> bool:
    return type(exception).__name__ == "AuthenticationRequiredError"

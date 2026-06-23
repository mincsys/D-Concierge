from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


def test_error_type_values_match_common_design() -> None:
    """
    観点：共通エラー分類が設計値と一致すること
    確認：ErrorTypeがinput、not_found、conflict、configuration、forbidden、systemだけをEnum値として持つこと
    """
    from backend.shared.errors.error_type import ErrorType

    assert tuple(error_type.value for error_type in ErrorType) == (
        "input",
        "not_found",
        "conflict",
        "configuration",
        "forbidden",
        "system",
    )


def test_app_error_keeps_only_common_error_fields() -> None:
    """
    観点：AppErrorが共通設計で定義された内部構造化エラーだけを保持すること
    確認：error_type、trace、diagnostic_message、causeを保持し、trace=Trueでは診断文と原因例外を参照できること
    """
    from backend.shared.errors.error_type import ErrorType
    from backend.shared.errors.errors import AppError

    cause = ValueError("database.url is missing")

    error = AppError(
        error_type=ErrorType.CONFIGURATION,
        trace=True,
        diagnostic_message="database.url が未設定です",
        cause=cause,
    )

    assert error.error_type is ErrorType.CONFIGURATION
    assert error.trace is True
    assert error.diagnostic_message == "database.url が未設定です"
    assert error.cause is cause


def test_app_error_clears_diagnostic_message_when_trace_is_false() -> None:
    """
    観点：AppErrorのtrace=Falseが利用者向け通常エラーをトレースログ対象外にすること
    確認：trace=Falseで生成したAppErrorは内部診断文を空文字へ正規化し、秘密情報を保持しないこと
    """
    from backend.shared.errors.error_type import ErrorType
    from backend.shared.errors.errors import AppError

    error = AppError(
        error_type=ErrorType.INPUT,
        trace=False,
        diagnostic_message="/internal/path/config.yaml",
    )

    assert error.error_type is ErrorType.INPUT
    assert error.trace is False
    assert error.diagnostic_message == ""
    assert error.cause is None


def test_new_trace_id_returns_distinct_uuid_text() -> None:
    """
    観点：trace_id生成がREST/SSE入口で使える相関IDを返すこと
    確認：new_trace_idがTraceId型を返し、文字列表現がUUIDとして解釈でき、連続生成で同じ値を使い回さないこと
    """
    from backend.shared.tracing.trace_id import TraceId, new_trace_id

    first = new_trace_id()
    second = new_trace_id()

    assert isinstance(first, TraceId)
    assert isinstance(second, TraceId)
    assert UUID(str(first)).version == 7
    assert UUID(str(second)).version == 7
    assert str(first) != str(second)


def test_new_trace_id_uses_injected_uuid_generator() -> None:
    """
    観点：trace_id生成がRuntimeProviderのID発番境界を利用できること
    確認：new_trace_idへUUID発番Portを渡すと、そのUUID値がTraceIdへ変換されること
    """
    from backend.shared.tracing.trace_id import new_trace_id

    fixed_uuid = UUID("01890f3c-7b9a-7cc0-8d1a-0123456789ab")

    trace_id = new_trace_id(FixedUuidGenerator(fixed_uuid))

    assert str(trace_id) == str(fixed_uuid)


@dataclass(frozen=True, slots=True)
class FixedUuidGenerator:
    value: UUID

    def new_uuid(self) -> UUID:
        return self.value

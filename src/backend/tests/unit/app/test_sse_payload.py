from uuid import UUID

import pytest

from backend.application.execution.execute_chat_run import RunEvent
from backend.application.execution.run_event_type import RunEventType
from backend.application.ports.database.dto import AnswerData
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.domain.execution.run_state import RunState
from backend.presentation.rest.router import _write_sse_failure_trace
from backend.presentation.sse.payload import (
    EndEventPayload,
    run_event_payload,
    sse_event_bytes,
)
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError


def test_sse_payload_converts_canceled_event() -> None:
    """観点：SSE payload変換。

    確認：キャンセル終端イベントを終了通知payloadへ変換する。
    """
    payload = run_event_payload(
        RunEvent(
            event=RunEventType.CANCELED,
            chat_id=UUID("00000000-0000-0000-0000-000000000701"),
            run_id=UUID("00000000-0000-0000-0000-000000000702"),
            state=RunState.CANCELED,
            user_message="処理をキャンセルしました。",
        )
    )

    assert payload == {
        "run_id": "00000000-0000-0000-0000-000000000702",
        "state": RunState.CANCELED.value,
        "user_message": "処理をキャンセルしました。",
    }


def test_sse_error_payload_uses_run_state_error_value() -> None:
    """観点：SSE payload変換。

    確認：SSE例外時の終了payloadもRunState.ERRORの外部仕様値を使う。
    """
    payload = EndEventPayload(
        run_id="00000000-0000-0000-0000-000000000709",
        state=RunState.ERROR.value,
        user_message="予期しないエラーが発生しました。開発者にお問い合わせください。",
    )

    assert payload["state"] == RunState.ERROR.value


def test_sse_event_bytes_keeps_wire_format() -> None:
    """観点：SSE wire形式。

    確認：event名とJSON dataをSSE形式のbytesへ変換する。
    """
    payload = EndEventPayload(
        run_id="00000000-0000-0000-0000-000000000709",
        state=RunState.ERROR.value,
        user_message="予期しないエラーが発生しました。開発者にお問い合わせください。",
    )

    assert (
        sse_event_bytes("error", payload)
        == (
            "event: error\n"
            'data: {"run_id":"00000000-0000-0000-0000-000000000709",'
            f'"state":"{RunState.ERROR.value}",'
            '"user_message":"予期しないエラーが発生しました。開発者にお問い合わせください。"}\n\n'
        ).encode()
    )


def test_sse_failure_trace_uses_run_state_error_value() -> None:
    """観点：SSE失敗トレース。

    確認：SSE失敗ログのrun_stateもRunState.ERRORの外部仕様値を使う。
    """
    logger = RecordingTraceLogger()

    _write_sse_failure_trace(
        trace_logger=logger,
        trace_id="trace-sse-error",
        chat_id=UUID("00000000-0000-0000-0000-000000000710"),
        run_id=UUID("00000000-0000-0000-0000-000000000711"),
        exc=AppError(
            ErrorType.SYSTEM,
            trace=True,
            diagnostic_message="SSE配信に失敗しました。",
        ),
        error_type=ErrorType.SYSTEM.value,
        message="SSE配信に失敗しました。",
    )

    assert logger.records[-1].run_state == RunState.ERROR.value


@pytest.mark.parametrize(
    "event",
    [
        RunEvent(
            event=RunEventType.STATE,
            chat_id=UUID("00000000-0000-0000-0000-000000000703"),
            run_id=UUID("00000000-0000-0000-0000-000000000704"),
        ),
        RunEvent(
            event=RunEventType.ANSWER,
            chat_id=UUID("00000000-0000-0000-0000-000000000705"),
            run_id=UUID("00000000-0000-0000-0000-000000000706"),
            state=RunState.COMPLETED,
        ),
        RunEvent(
            event=RunEventType.ANSWER,
            chat_id=UUID("00000000-0000-0000-0000-000000000707"),
            run_id=UUID("00000000-0000-0000-0000-000000000708"),
            answer=AnswerData(blocks=()),
        ),
    ],
)
def test_sse_payload_rejects_invalid_event_content(event: RunEvent) -> None:
    """観点：SSE payload変換の異常系。

    確認：必須項目を欠くイベントをSYSTEM例外へ変換する。
    """
    with pytest.raises(AppError) as error_info:
        run_event_payload(event)

    assert error_info.value.error_type is ErrorType.SYSTEM


class RecordingTraceLogger:
    """テスト用トレースログ出力先。"""

    def __init__(self) -> None:
        self.records: list[TraceLogRecord] = []

    def write(self, record: TraceLogRecord) -> None:
        """出力レコードを記録する。"""
        self.records.append(record)

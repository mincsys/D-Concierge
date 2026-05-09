from uuid import UUID

import pytest

from backend.app.factory import _run_event_payload
from backend.application.execution.execute_chat_run import RunEvent
from backend.infrastructure.memory.repository import AnswerData
from backend.shared.errors import AppError, ErrorClass


def test_sse_payload_converts_canceled_event() -> None:
    """観点：SSE payload変換。

    確認：キャンセル終端イベントを終了通知payloadへ変換する。
    """
    payload = _run_event_payload(
        RunEvent(
            event="canceled",
            chat_id=UUID("00000000-0000-0000-0000-000000000701"),
            run_id=UUID("00000000-0000-0000-0000-000000000702"),
            state="キャンセル済み",
            user_message="処理をキャンセルしました。",
        )
    )

    assert payload == {
        "run_id": "00000000-0000-0000-0000-000000000702",
        "state": "キャンセル済み",
        "user_message": "処理をキャンセルしました。",
    }


@pytest.mark.parametrize(
    "event",
    [
        RunEvent(
            event="state",
            chat_id=UUID("00000000-0000-0000-0000-000000000703"),
            run_id=UUID("00000000-0000-0000-0000-000000000704"),
        ),
        RunEvent(
            event="answer",
            chat_id=UUID("00000000-0000-0000-0000-000000000705"),
            run_id=UUID("00000000-0000-0000-0000-000000000706"),
            state="完了",
        ),
        RunEvent(
            event="answer",
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
        _run_event_payload(event)

    assert error_info.value.error_class is ErrorClass.SYSTEM

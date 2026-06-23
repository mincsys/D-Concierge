from __future__ import annotations

from backend.domain.execution.run_state import RunState
from backend.tests.support.chat import RUN_ID_VALUE


def test_run_event_broker_delivers_state_message_and_terminal_event_once() -> None:
    """
    観点：SSEイベント配信IFがrun ID単位のpublish/subscribeを提供すること
    確認：購読者はstate、message、canceledを順序どおり受け取り、
    終端イベント後のpublishは同じ購読へ送信されないこと
    """
    from backend.application.execution.run_event_broker import (
        RunEvent,
        RunEventBroker,
        RunEventType,
    )

    broker = RunEventBroker()
    subscription = broker.subscribe(RUN_ID_VALUE)

    broker.publish(
        RunEvent.state(run_id=RUN_ID_VALUE, state=RunState.RUNNING.value),
    )
    broker.publish(RunEvent.message(run_id=RUN_ID_VALUE, text="調査中です。"))
    broker.publish(
        RunEvent.end(
            event_type=RunEventType.CANCELED,
            run_id=RUN_ID_VALUE,
            state=RunState.CANCELED.value,
            user_message="処理をキャンセルしました。",
        ),
    )
    broker.publish(
        RunEvent.state(run_id=RUN_ID_VALUE, state=RunState.RUNNING.value),
    )

    assert subscription.poll_event() == RunEvent.state(
        run_id=RUN_ID_VALUE,
        state=RunState.RUNNING.value,
    )
    assert subscription.poll_event() == RunEvent.message(
        run_id=RUN_ID_VALUE,
        text="調査中です。",
    )
    assert subscription.poll_event() == RunEvent.end(
        event_type=RunEventType.CANCELED,
        run_id=RUN_ID_VALUE,
        state=RunState.CANCELED.value,
        user_message="処理をキャンセルしました。",
    )
    assert subscription.poll_event() is None


def test_sse_wire_formatter_uses_frontend_event_payload_contract() -> None:
    """
    観点：SSE送信直前のwire形式が画面バックエンドAPI IFとfrontend型に一致すること
    確認：event行とdata行で構成され、payloadにrun_id、stateまたはtext、
    user_messageをJSONとして含めること
    """
    from backend.application.execution.run_event_broker import RunEvent, RunEventType
    from backend.presentation.sse.payload import format_sse_event

    wire = format_sse_event(
        RunEvent.end(
            event_type=RunEventType.CANCELED,
            run_id=RUN_ID_VALUE,
            state=RunState.CANCELED.value,
            user_message="処理をキャンセルしました。",
        ),
    )

    assert wire.startswith("event: canceled\n")
    assert f'"run_id":"{RUN_ID_VALUE}"' in wire
    assert '"state":"canceled"' in wire
    assert '"user_message":"処理をキャンセルしました。"' in wire
    assert wire.endswith("\n\n")


def test_sse_wire_formatter_outputs_state_and_message_payloads() -> None:
    """
    観点：SSE送信直前のwire形式が状態通知と中間メッセージを区別すること
    確認：stateイベントはstate、messageイベントはtextをJSONに含め、
    どちらもevent行とdata行のSSE形式になること
    """
    from backend.application.execution.run_event_broker import RunEvent
    from backend.presentation.sse.payload import format_sse_event

    state_wire = format_sse_event(
        RunEvent.state(run_id=RUN_ID_VALUE, state=RunState.RUNNING.value),
    )
    message_wire = format_sse_event(
        RunEvent.message(run_id=RUN_ID_VALUE, text="調査中です。"),
    )

    assert state_wire.startswith("event: state\n")
    assert '"state":"running"' in state_wire
    assert message_wire.startswith("event: message\n")
    assert '"text":"調査中です。"' in message_wire

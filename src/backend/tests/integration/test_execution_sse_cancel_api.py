from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.application.execution.dto import CodexCancelStatus
from backend.application.ports.database.dto import UnfinishedRun
from backend.domain.chat.chat_state import ChatState
from backend.domain.execution.run_state import RunState
from backend.tests.support.chat import (
    CHAT_ID_VALUE,
    FIXED_CHAT_NOW,
    OTHER_USER_ID,
    RUN_ID_VALUE,
    SESSION_ID_VALUE,
    ErrorPayload,
    insert_chat_run,
    insert_completed_answer,
    run_state,
    seed_chat_user,
    table_count,
)
from backend.tests.support.execution import parse_sse_events
from backend.tests.support.foundation import (
    LOGIN_SESSION_COOKIE_NAME,
    create_foundation_config,
    foundation_test_database_url,
    prepare_foundation_database,
)


@pytest.mark.asyncio
async def test_sse_api_sends_current_state_saved_messages_and_terminal_answer(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-06 実行SSE購読が現在状態と保存済みイベントをSSE wire形式で返すこと
    確認：完了済みrunへ接続するとstate、message、answerを順序どおり配信し、
    payloadがfrontendのSseEvent型と同じキーを持つこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=CHAT_ID_VALUE,
        run_id=RUN_ID_VALUE,
        session_id=SESSION_ID_VALUE,
        instruction_id=UUID("10101010-1010-7010-8010-101010101010"),
        title="SSE完了チャット",
        instruction="完了済み指示",
        run_state=RunState.COMPLETED.value,
    )
    insert_completed_answer(
        database_url,
        run_id=RUN_ID_VALUE,
        message_id=UUID("20202020-2020-7020-8020-202020202020"),
        answer_block_id=UUID("30303030-3030-7030-8030-303030303030"),
        reference_id=UUID("40404040-4040-7040-8040-404040404040"),
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.get(
            f"/api/chats/{CHAT_ID_VALUE}/runs/{RUN_ID_VALUE}/sse",
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse_events(response.text)
    assert [event.event for event in events] == ["state", "message", "answer"]
    assert events[0].payload == {
        "run_id": str(RUN_ID_VALUE),
        "state": RunState.COMPLETED.value,
    }
    assert events[1].payload == {
        "run_id": str(RUN_ID_VALUE),
        "text": "作業を開始します。",
    }
    assert events[2].payload["run_id"] == str(RUN_ID_VALUE)
    assert events[2].payload["state"] == RunState.COMPLETED.value
    answer_payload = events[2].payload
    assert "answer" in answer_payload
    assert answer_payload["answer"]["blocks"][0]["markdown"] == "回答本文"
    answer_reference = answer_payload["answer"]["blocks"][0]["references"][0]
    assert answer_reference["source_type"] == "pdf"
    assert answer_reference["label"] == "資料A"
    assert answer_reference["url"] == (
        "/api/references/40404040-4040-7040-8040-404040404040"
    )
    assert answer_reference["locator"] == {"page_start": 2, "page_end": 3}


@pytest.mark.asyncio
async def test_sse_api_streams_broker_events_after_subscription(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-06 実行SSE購読がRunEventBrokerのライブ配信へ接続すること
    確認：購読開始後にpublishしたmessageとcanceledイベントを同じSSE接続で受信し、
    終端イベント後にstreamが終了すること
    """
    from backend.app.factory import create_app
    from backend.application.execution.run_event_broker import (
        RunEvent,
        RunEventBroker,
        RunEventSubscription,
        RunEventType,
    )

    class AutoPublishingRunEventBroker(RunEventBroker):
        """購読確立直後のpublishを再現するテスト用broker。"""

        subscription_count = 0

        def subscribe(self, run_id: UUID) -> RunEventSubscription:
            subscription = super().subscribe(run_id)
            self.subscription_count += 1
            self.publish(RunEvent.message(run_id=run_id, text="処理中です。"))
            self.publish(
                RunEvent.end(
                    event_type=RunEventType.CANCELED,
                    run_id=run_id,
                    state=RunState.CANCELED.value,
                    user_message="処理をキャンセルしました。",
                )
            )
            return subscription

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=CHAT_ID_VALUE,
        run_id=RUN_ID_VALUE,
        session_id=SESSION_ID_VALUE,
        instruction_id=UUID("51515151-5151-7151-8151-515151515151"),
        title="ライブSSEチャット",
        instruction="ライブSSE指示",
        run_state=RunState.RUNNING.value,
    )
    broker = AutoPublishingRunEventBroker()
    app.state.run_event_broker = broker

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.get(
            f"/api/chats/{CHAT_ID_VALUE}/runs/{RUN_ID_VALUE}/sse",
        )

    assert response.status_code == 200
    assert broker.subscription_count == 1
    events = parse_sse_events(response.text)
    assert [event.event for event in events] == ["state", "message", "canceled"]
    assert events[0].payload["state"] == RunState.RUNNING.value
    assert events[1].payload["text"] == "処理中です。"
    assert events[2].payload["state"] == RunState.CANCELED.value
    assert events[2].payload["user_message"] == "処理をキャンセルしました。"


@pytest.mark.asyncio
async def test_sse_api_rejects_unauthorized_missing_other_user_and_deleting_chat(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-06 実行SSE購読が接続前に認証、所有者、削除中状態を検証すること
    確認：Cookieなしは401、対象なしまたは他ユーザrunは404、
    deletingチャットは409共通エラーとなり、SSE本文を開始しないこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=CHAT_ID_VALUE,
        run_id=RUN_ID_VALUE,
        session_id=SESSION_ID_VALUE,
        instruction_id=UUID("11111111-2222-7111-8222-111111111111"),
        title="削除中チャット",
        instruction="削除中指示",
        run_state=RunState.RUNNING.value,
        chat_state=ChatState.DELETING.value,
    )
    other_chat_id = UUID("55555555-5555-7555-8555-555555555555")
    other_run_id = UUID("66666666-6666-7666-8666-666666666666")
    seed_chat_user(
        database_url,
        user_id=OTHER_USER_ID,
        user_name="別ユーザ",
        session_token="other-f004-token",
    )
    missing_run_id = UUID("99999999-9999-7999-8999-999999999999")
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)
    insert_chat_run(
        database_url,
        user_id=OTHER_USER_ID,
        chat_id=other_chat_id,
        run_id=other_run_id,
        session_id=UUID("77777777-7777-7777-8777-777777777777"),
        instruction_id=UUID("88888888-8888-7888-8888-888888888888"),
        title="他ユーザチャット",
        instruction="他ユーザ指示",
        run_state=RunState.RUNNING.value,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        unauthorized = await client.get(
            f"/api/chats/{CHAT_ID_VALUE}/runs/{RUN_ID_VALUE}/sse",
        )
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        missing = await client.get(
            f"/api/chats/{CHAT_ID_VALUE}/runs/{missing_run_id}/sse",
        )
        other = await client.get(f"/api/chats/{other_chat_id}/runs/{other_run_id}/sse")
        deleting = await client.get(
            f"/api/chats/{CHAT_ID_VALUE}/runs/{RUN_ID_VALUE}/sse",
        )

    _assert_error(unauthorized, 401, "unauthorized")
    _assert_error(missing, 404, "not_found")
    _assert_error(other, 404, "not_found")
    _assert_error(deleting, 409, "conflict")


@pytest.mark.asyncio
async def test_cancel_api_cancels_accepted_run_and_publishes_terminal_state(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-07 キャンセル要求がaccepted runを即時キャンセル済みに整合すること
    確認：200、state=canceled、利用者向けメッセージを返し、
    DB上のrun状態もcanceledになること
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=CHAT_ID_VALUE,
        run_id=RUN_ID_VALUE,
        session_id=SESSION_ID_VALUE,
        instruction_id=UUID("12121212-1212-7121-8121-121212121212"),
        title="受付済みチャット",
        instruction="キャンセル対象指示",
        run_state=RunState.ACCEPTED.value,
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.post(
            f"/api/chats/{CHAT_ID_VALUE}/runs/{RUN_ID_VALUE}/cancel",
        )

    assert response.status_code == 200
    payload = _cancel_payload(response.text)
    assert payload["state"] == RunState.CANCELED.value
    assert payload["user_message"] == "処理をキャンセルしました。"
    assert run_state(database_url, RUN_ID_VALUE) == RunState.CANCELED.value


@pytest.mark.asyncio
async def test_cancel_api_moves_running_run_to_cancel_requested(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-07 キャンセル要求がrunning runの終了要求受付を保存すること
    確認：200、state=cancel_requested、利用者向けメッセージを返し、
    DB上のrun状態もcancel_requestedになること
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=CHAT_ID_VALUE,
        run_id=RUN_ID_VALUE,
        session_id=SESSION_ID_VALUE,
        instruction_id=UUID("13131313-1313-7131-8131-131313131313"),
        title="実行中チャット",
        instruction="キャンセル要求中にする",
        run_state=RunState.RUNNING.value,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.post(
            f"/api/chats/{CHAT_ID_VALUE}/runs/{RUN_ID_VALUE}/cancel",
        )

    assert response.status_code == 200
    payload = _cancel_payload(response.text)
    assert payload["state"] == RunState.CANCEL_REQUESTED.value
    assert payload["user_message"] == "処理をキャンセルしています。"
    assert run_state(database_url, RUN_ID_VALUE) == RunState.CANCEL_REQUESTED.value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cancel_status",
    ("already_exited", "not_registered"),
)
async def test_cancel_api_aligns_runner_completed_result_to_canceled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cancel_status: CodexCancelStatus,
) -> None:
    """
    観点：IF-SB-07 キャンセル要求がCodexRunnerの終了済み結果をDB状態へ反映すること
    確認：already_exitedまたはnot_registeredでは200、state=canceledとなり、
    DB上のrun状態もcanceledへ整合すること
    """
    import backend.presentation.rest.chat as chat_rest
    from backend.app.factory import create_app
    from backend.application.execution.dto import CodexCancelResult

    class CompletedCodexRunCancellation:
        """テスト用にCodexRunner終了済み結果を返す境界。"""

        def cancel(
            self, chat_id: UUID, run_id: UUID, trace_id: str
        ) -> CodexCancelResult:
            return CodexCancelResult(status=cancel_status)

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    monkeypatch.setattr(
        chat_rest, "NoopCodexRunCancellation", CompletedCodexRunCancellation
    )
    app = create_app(config_path=files.config_path, base_dir=tmp_path)
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=CHAT_ID_VALUE,
        run_id=RUN_ID_VALUE,
        session_id=SESSION_ID_VALUE,
        instruction_id=UUID("52525252-5252-7252-8252-525252525252"),
        title="終了済みキャンセルチャット",
        instruction="終了済みキャンセル指示",
        run_state=RunState.RUNNING.value,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.post(
            f"/api/chats/{CHAT_ID_VALUE}/runs/{RUN_ID_VALUE}/cancel",
        )

    assert response.status_code == 200
    payload = _cancel_payload(response.text)
    assert payload["state"] == RunState.CANCELED.value
    assert payload["user_message"] == "処理をキャンセルしました。"
    assert run_state(database_url, RUN_ID_VALUE) == RunState.CANCELED.value


@pytest.mark.asyncio
async def test_cancel_api_rejects_unauthorized_other_user_terminal_and_deleting_chat(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-07 キャンセル要求が認証、所有者、状態、削除中を接続前に検証すること
    確認：Cookieなしは401、他ユーザrunは404、終端済みとdeletingチャットは409となり、
    既存run状態を変更しないこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=CHAT_ID_VALUE,
        run_id=RUN_ID_VALUE,
        session_id=SESSION_ID_VALUE,
        instruction_id=UUID("14141414-1414-7141-8141-141414141414"),
        title="終端済みチャット",
        instruction="完了済み指示",
        run_state=RunState.COMPLETED.value,
    )
    deleting_chat_id = UUID("15151515-1515-7151-8151-151515151515")
    deleting_run_id = UUID("16161616-1616-7161-8161-161616161616")
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=deleting_chat_id,
        run_id=deleting_run_id,
        session_id=UUID("17171717-1717-7171-8171-171717171717"),
        instruction_id=UUID("18181818-1818-7181-8181-181818181818"),
        title="削除中チャット",
        instruction="削除中指示",
        run_state=RunState.RUNNING.value,
        chat_state=ChatState.DELETING.value,
    )
    other_chat_id = UUID("19191919-1919-7191-8191-191919191919")
    other_run_id = UUID("20202020-2020-7020-8020-202020202020")
    seed_chat_user(
        database_url,
        user_id=OTHER_USER_ID,
        user_name="別ユーザ",
        session_token="other-f004-cancel-token",
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)
    insert_chat_run(
        database_url,
        user_id=OTHER_USER_ID,
        chat_id=other_chat_id,
        run_id=other_run_id,
        session_id=UUID("21212121-2121-7121-8121-212121212121"),
        instruction_id=UUID("22222222-2222-7222-8222-222222222222"),
        title="他ユーザチャット",
        instruction="他ユーザ指示",
        run_state=RunState.RUNNING.value,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        unauthorized = await client.post(
            f"/api/chats/{CHAT_ID_VALUE}/runs/{RUN_ID_VALUE}/cancel",
        )
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        other = await client.post(
            f"/api/chats/{other_chat_id}/runs/{other_run_id}/cancel",
        )
        terminal = await client.post(
            f"/api/chats/{CHAT_ID_VALUE}/runs/{RUN_ID_VALUE}/cancel",
        )
        deleting = await client.post(
            f"/api/chats/{deleting_chat_id}/runs/{deleting_run_id}/cancel",
        )

    _assert_error(unauthorized, 401, "unauthorized")
    _assert_error(other, 404, "not_found")
    _assert_error(terminal, 409, "conflict")
    _assert_error(deleting, 409, "conflict")
    assert run_state(database_url, RUN_ID_VALUE) == RunState.COMPLETED.value
    assert run_state(database_url, deleting_run_id) == RunState.RUNNING.value
    assert run_state(database_url, other_run_id) == RunState.RUNNING.value


@pytest.mark.asyncio
async def test_sse_api_sends_error_and_canceled_terminal_events(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-06 実行SSE購読が終端済み異常系を保存状態から再送できること
    確認：error runはerrorイベント、canceled runはcanceledイベントを返し、
    payloadにrun_id、state、user_messageを含めること
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    error_chat_id = UUID("23232323-2323-7323-8323-232323232323")
    error_run_id = UUID("24242424-2424-7424-8424-242424242424")
    canceled_chat_id = UUID("25252525-2525-7525-8525-252525252525")
    canceled_run_id = UUID("26262626-2626-7626-8626-262626262626")
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=error_chat_id,
        run_id=error_run_id,
        session_id=UUID("27272727-2727-7727-8727-272727272727"),
        instruction_id=UUID("28282828-2828-7828-8828-282828282828"),
        title="エラー終端チャット",
        instruction="エラー終端指示",
        run_state=RunState.ERROR.value,
        user_message="システムエラーが発生しました。",
    )
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=canceled_chat_id,
        run_id=canceled_run_id,
        session_id=UUID("29292929-2929-7929-8929-292929292929"),
        instruction_id=UUID("30303030-3030-7030-8030-303030303030"),
        title="キャンセル済みチャット",
        instruction="キャンセル済み指示",
        run_state=RunState.CANCELED.value,
        user_message="処理をキャンセルしました。",
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        error_response = await client.get(
            f"/api/chats/{error_chat_id}/runs/{error_run_id}/sse",
        )
        canceled_response = await client.get(
            f"/api/chats/{canceled_chat_id}/runs/{canceled_run_id}/sse",
        )

    error_events = parse_sse_events(error_response.text)
    canceled_events = parse_sse_events(canceled_response.text)
    assert [event.event for event in error_events] == ["state", "error"]
    assert error_events[1].payload["state"] == RunState.ERROR.value
    assert error_events[1].payload["user_message"] == ("システムエラーが発生しました。")
    assert [event.event for event in canceled_events] == ["state", "canceled"]
    assert canceled_events[1].payload["state"] == RunState.CANCELED.value
    assert canceled_events[1].payload["user_message"] == ("処理をキャンセルしました。")


def test_run_execution_dispatcher_deduplicates_and_reports_submit_failure() -> None:
    """
    観点：RunExecutionDispatcher IFが同一run多重登録とbackground登録失敗を境界で扱うこと
    確認：初回はregistered、同一run再登録はalready_registered、
    background登録失敗はfailedを返すこと
    """
    from backend.infrastructure.runtime.run_execution_dispatcher import (
        InProcessRunExecutionDispatcher,
    )

    success_executor = _RecordingBackgroundExecutor(results=[True])
    dispatcher = InProcessRunExecutionDispatcher(success_executor)

    first = dispatcher.register(CHAT_ID_VALUE, RUN_ID_VALUE, "trace-001")
    duplicate = dispatcher.register(CHAT_ID_VALUE, RUN_ID_VALUE, "trace-002")
    failed = InProcessRunExecutionDispatcher(
        _RecordingBackgroundExecutor(results=[False]),
    ).register(CHAT_ID_VALUE, UUID("31313131-3131-7131-8131-313131313131"), "trace")

    assert first.status == "registered"
    assert duplicate.status == "already_registered"
    assert failed.status == "failed"
    assert success_executor.submissions == [RUN_ID_VALUE]


def test_run_event_broker_handles_terminal_and_empty_subscriptions() -> None:
    """
    観点：SSEイベント配信IFが購読なし配信、終端後配信、空購読を安全に扱うこと
    確認：終端後のイベントは配信されず、新規購読者の空pollはNoneを返すこと
    """
    from backend.application.execution.run_event_broker import (
        RunEvent,
        RunEventBroker,
        RunEventType,
    )

    broker = RunEventBroker()
    broker.publish(RunEvent.state(run_id=RUN_ID_VALUE, state=RunState.RUNNING.value))
    subscription = broker.subscribe(RUN_ID_VALUE)

    terminal_event = RunEvent.end(
        event_type=RunEventType.CANCELED,
        run_id=RUN_ID_VALUE,
        state=RunState.CANCELED.value,
        user_message="処理をキャンセルしました。",
    )
    broker.publish(terminal_event)
    broker.publish(RunEvent.message(run_id=RUN_ID_VALUE, text="終端後です。"))
    later_subscription = broker.subscribe(RUN_ID_VALUE)

    assert subscription.poll_event() == terminal_event
    assert subscription.poll_event() is None
    assert later_subscription.poll_event() is None


def test_run_event_broker_unsubscribes_disconnected_subscription() -> None:
    """
    観点：SSEイベント配信IFが切断時に購読を解除すること
    確認：unsubscribe済みsubscriptionには後続publishが配送されないこと
    """
    from backend.application.execution.run_event_broker import (
        RunEvent,
        RunEventBroker,
    )

    broker = RunEventBroker()
    subscription = broker.subscribe(RUN_ID_VALUE)

    broker.unsubscribe(subscription)
    broker.publish(RunEvent.message(run_id=RUN_ID_VALUE, text="切断後イベント"))

    assert subscription.poll_event() is None


@pytest.mark.asyncio
async def test_app_startup_recovers_unfinished_runs(
    tmp_path: Path,
) -> None:
    """
    観点：起動時実行回復処理がAPI起点外でも未完了runを状態別に整合すること
    確認：アプリ生成時にacceptedは実行登録対象、running/validatingはerror、
    cancel_requestedはcanceledとなり、終端済みrunは変更されないこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    run_ids = {
        RunState.ACCEPTED: UUID("31313131-3131-7131-8131-313131313131"),
        RunState.RUNNING: UUID("32323232-3232-7323-8323-323232323232"),
        RunState.VALIDATING: UUID("33333333-3333-7333-8333-333333333333"),
        RunState.CANCEL_REQUESTED: UUID("34343434-3434-7343-8343-343434343434"),
        RunState.COMPLETED: UUID("35353535-3535-7353-8353-353535353535"),
    }
    for index, state in enumerate(run_ids, start=1):
        insert_chat_run(
            database_url,
            user_id=seeded.user_id,
            chat_id=UUID(f"44444444-4444-7444-8444-44444444444{index}"),
            run_id=run_ids[state],
            session_id=UUID(f"55555555-5555-7555-8555-55555555555{index}"),
            instruction_id=UUID(f"66666666-6666-7666-8666-66666666666{index}"),
            title=f"回復対象{index}",
            instruction=f"回復対象指示{index}",
            run_state=state.value,
            updated_at=FIXED_CHAT_NOW,
        )
    files = create_foundation_config(tmp_path, database_url=database_url)

    create_app(config_path=files.config_path, base_dir=tmp_path)

    assert run_state(database_url, run_ids[RunState.ACCEPTED]) == (
        RunState.ACCEPTED.value
    )
    assert run_state(database_url, run_ids[RunState.RUNNING]) == RunState.ERROR.value
    assert run_state(database_url, run_ids[RunState.VALIDATING]) == RunState.ERROR.value
    assert run_state(database_url, run_ids[RunState.CANCEL_REQUESTED]) == (
        RunState.CANCELED.value
    )
    assert run_state(database_url, run_ids[RunState.COMPLETED]) == (
        RunState.COMPLETED.value
    )
    assert table_count(database_url, "chat_runs") == 5


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("initial_state", "expected_state", "expected_log_fragment"),
    (
        (RunState.ACCEPTED, RunState.ACCEPTED, "accepted_registered=1"),
        (RunState.RUNNING, RunState.ERROR, "error_terminalized=1"),
        (RunState.VALIDATING, RunState.ERROR, "error_terminalized=1"),
    ),
)
async def test_app_startup_recovers_single_unfinished_state_and_logs_summary(
    tmp_path: Path,
    initial_state: RunState,
    expected_state: RunState,
    expected_log_fragment: str,
) -> None:
    """
    観点：起動時実行回復がcancel_requested以外の単独未完了runでも起動すること
    確認：accepted、running、validatingそれぞれ単独残存時に回復処理が走り、
    回復件数のトレースログが保存されること
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=CHAT_ID_VALUE,
        run_id=RUN_ID_VALUE,
        session_id=SESSION_ID_VALUE,
        instruction_id=UUID("53535353-5353-7353-8353-535353535353"),
        title="単独回復対象",
        instruction="単独回復対象指示",
        run_state=initial_state.value,
    )
    files = create_foundation_config(tmp_path, database_url=database_url)

    create_app(config_path=files.config_path, base_dir=tmp_path)

    assert run_state(database_url, RUN_ID_VALUE) == expected_state.value
    trace_log_text = "\n".join(_trace_log_texts(files.trace_log_dir))
    assert "startup_recovery_completed" in trace_log_text
    assert expected_log_fragment in trace_log_text


@pytest.mark.asyncio
async def test_app_startup_logs_recovery_target_read_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    観点：起動時実行回復が回復対象取得失敗を管理者対応対象として記録すること
    確認：Repository読取のSQLAlchemyErrorを無言で握りつぶさず、
    トレースログに失敗イベントと診断メッセージを保存すること
    """
    import backend.app.factory as app_factory

    class FailingRecoveryRepository:
        """起動時回復対象の取得失敗を再現するRepository。"""

        def __init__(self, session: Session) -> None:
            self._session = session

        def list_unfinished_runs_for_recovery(self) -> tuple[UnfinishedRun, ...]:
            raise SQLAlchemyError("recovery target read failed")

        def list_deleting_chats_for_recovery(self) -> tuple[UUID, ...]:
            return ()

    files = create_foundation_config(tmp_path)
    monkeypatch.setattr(
        app_factory, "SqlAlchemyChatRepository", FailingRecoveryRepository
    )

    app_factory.create_app(config_path=files.config_path, base_dir=tmp_path)

    trace_log_text = "\n".join(_trace_log_texts(files.trace_log_dir))
    assert "startup_recovery_failed" in trace_log_text
    assert "recovery target read failed" in trace_log_text


class CancelResponsePayload(ErrorPayload):
    state: str
    user_message: str


@dataclass(slots=True)
class _RecordingBackgroundExecutor:
    results: list[bool]
    submissions: list[UUID] = field(default_factory=list)

    def submit(self, run_id: UUID) -> bool:
        self.submissions.append(run_id)
        if not self.results:
            return False
        return self.results.pop(0)


def _cancel_payload(response_text: str) -> CancelResponsePayload:
    payload = json.loads(response_text)
    assert isinstance(payload, dict)
    state = payload.get("state")
    user_message = payload.get("user_message")
    assert isinstance(state, str)
    assert isinstance(user_message, str)
    return {"error": "", "message": "", "state": state, "user_message": user_message}


def _error_payload(response_text: str) -> ErrorPayload:
    payload = json.loads(response_text)
    assert isinstance(payload, dict)
    error = payload.get("error")
    message = payload.get("message")
    assert isinstance(error, str)
    assert isinstance(message, str)
    return {"error": error, "message": message}


def _assert_error(response: Response, status_code: int, expected_error: str) -> None:
    assert response.status_code == status_code
    payload = _error_payload(response.text)
    assert payload["error"] == expected_error
    assert "detail" not in response.text


def _trace_log_texts(trace_log_dir: Path) -> tuple[str, ...]:
    return tuple(
        path.read_text(encoding="utf-8")
        for path in sorted(trace_log_dir.rglob("*.yaml"))
    )

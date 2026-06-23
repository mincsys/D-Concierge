from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient, Response

from backend.application.ports.runtime.interface import RunDispatchResult
from backend.domain.chat.chat_state import ChatState
from backend.domain.execution.run_state import RunState
from backend.tests.support.chat import (
    CHAT_ID_VALUE,
    FIXED_CHAT_NOW,
    NEXT_RUN_ID_VALUE,
    OTHER_USER_ID,
    RUN_ID_VALUE,
    SESSION_ID_VALUE,
    ChatAcceptedPayload,
    ChatDetailPayload,
    ChatHistoryPayload,
    ErrorPayload,
    FieldErrorPayload,
    insert_chat_run,
    insert_completed_answer,
    instruction_bodies,
    run_state,
    run_states,
    seed_chat_user,
    table_count,
)
from backend.tests.support.foundation import (
    LOGIN_SESSION_COOKIE_NAME,
    create_foundation_config,
    foundation_test_database_url,
    prepare_foundation_database,
)


@pytest.mark.asyncio
async def test_app_config_api_uses_real_authenticated_session_and_public_payload(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-01 アプリ設定取得APIが実ログインセッションを
    保護対象APIとして検証すること
    確認：有効Cookieでは200と公開UI設定だけを返し、Cookieなしでは401共通エラーを返すこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        unauthorized = await client.get("/api/app-config")
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.get("/api/app-config")

    assert unauthorized.status_code == 401
    assert _error_payload(unauthorized.text)["error"] == "unauthorized"
    assert response.status_code == 200
    assert response.headers["x-trace-id"]
    payload = json.loads(response.text)
    assert isinstance(payload, dict)
    assert payload["welcome_message"] == "ようこそ"
    assert payload["sub_welcome_message"] == "必要な資料を指定してください"
    assert payload["input_suggestions"] == [
        "申請手順を確認したい",
        "参考資料の該当ページを知りたい",
    ]
    assert "database" not in response.text
    assert str(files.trace_log_dir) not in response.text


@pytest.mark.asyncio
async def test_start_chat_api_persists_chat_first_run_and_instruction(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-02 新規チャット開始APIがREST、認証、DB、dispatcher境界を結合すること
    確認：200でaccepted受付を返し、chats、chat_runs、user_instructionsへ
    認証ユーザの初回指示を同一チャットとして保存すること
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)
    dispatcher = RecordingRunExecutionDispatcher()
    app.state.run_execution_dispatcher = dispatcher

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.post(
            "/api/chats/start",
            json={"user_instruction": "  申請手順を整理してください  "},
        )

    assert response.status_code == 200
    assert response.headers["x-trace-id"]
    payload = _accepted_payload(response.text)
    assert payload["state"] == "accepted"
    assert payload["sse_url"] == (
        f"/api/chats/{payload['chat_id']}/runs/{payload['run_id']}/sse"
    )
    assert UUID(payload["chat_id"])
    assert UUID(payload["run_id"])
    assert table_count(database_url, "chats") == 1
    assert table_count(database_url, "chat_runs") == 1
    assert instruction_bodies(database_url) == ("申請手順を整理してください",)
    assert dispatcher.registrations == [
        (
            UUID(payload["chat_id"]),
            UUID(payload["run_id"]),
            response.headers["x-trace-id"],
        )
    ]


@pytest.mark.asyncio
async def test_start_chat_api_marks_run_error_when_dispatcher_failed(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-02 新規チャット開始APIがdispatcher登録失敗をaccepted放置にしないこと
    確認：500共通エラーとなり、保存済みrunをerrorへ更新し、指示本文は監査可能に残すこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)
    app.state.run_execution_dispatcher = FailingRunExecutionDispatcher()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.post(
            "/api/chats/start",
            json={"user_instruction": "登録失敗を確認する"},
        )

    assert response.status_code == 500
    assert _error_payload(response.text)["error"] == "internal_error"
    assert table_count(database_url, "chats") == 1
    assert table_count(database_url, "chat_runs") == 1
    assert instruction_bodies(database_url) == ("登録失敗を確認する",)
    assert run_states(database_url) == (RunState.ERROR.value,)


@pytest.mark.asyncio
async def test_chat_protected_apis_reject_missing_cookie_without_db_write(
    tmp_path: Path,
) -> None:
    """
    観点：F003の保護対象チャットAPIが未ログインアクセスをREST境界で拒否すること
    確認：Cookieなしでは401、unauthorized、共通エラー形式となり、
    書込系APIでもchats、chat_runs、user_instructionsを追加しないこと
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
        instruction_id=UUID("28282828-2828-7282-8282-282828282828"),
        title="既存チャット",
        instruction="初回指示",
        run_state=RunState.COMPLETED.value,
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)
    dispatcher = RecordingRunExecutionDispatcher()
    app.state.run_execution_dispatcher = dispatcher

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        start_response = await client.post(
            "/api/chats/start",
            json={"user_instruction": "未ログインの開始"},
        )
        append_response = await client.post(
            f"/api/chats/{CHAT_ID_VALUE}/runs",
            json={"user_instruction": "未ログインの継続"},
        )
        histories_response = await client.get("/api/chat-histories")
        detail_response = await client.get(f"/api/chats/{CHAT_ID_VALUE}")

    _assert_unauthorized_payload(start_response)
    _assert_unauthorized_payload(append_response)
    _assert_unauthorized_payload(histories_response)
    _assert_unauthorized_payload(detail_response)
    assert table_count(database_url, "chats") == 1
    assert table_count(database_url, "chat_runs") == 1
    assert table_count(database_url, "user_instructions") == 1
    assert instruction_bodies(database_url) == ("初回指示",)


@pytest.mark.asyncio
async def test_start_chat_api_rejects_blank_instruction_without_db_write(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-02 新規チャット開始APIが空のユーザ指示を入力不正として扱うこと
    確認：400、validation_error、field_errors.user_instructionを返し、
    chats、chat_runs、user_instructionsを作成しないこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.post(
            "/api/chats/start",
            json={"user_instruction": "   \n\t  "},
        )

    assert response.status_code == 400
    payload = _field_error_payload(response.text)
    assert payload["error"] == "validation_error"
    assert "user_instruction" in payload["field_errors"]
    assert table_count(database_url, "chats") == 0
    assert table_count(database_url, "chat_runs") == 0
    assert table_count(database_url, "user_instructions") == 0


@pytest.mark.asyncio
async def test_append_chat_run_api_persists_next_instruction_for_owner(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-03 継続指示APIが所有者の既存チャットへrunと指示を追加すること
    確認：完了済みrunだけを持つactiveチャットでは200 acceptedとなり、
    新しいrunと指示が追加され、既存チャットIDのSSE URLを返すこと
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
        instruction_id=UUID("aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa"),
        title="既存チャット",
        instruction="初回指示",
        run_state=RunState.COMPLETED.value,
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)
    dispatcher = RecordingRunExecutionDispatcher()
    app.state.run_execution_dispatcher = dispatcher

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.post(
            f"/api/chats/{CHAT_ID_VALUE}/runs",
            json={"user_instruction": "継続の依頼"},
        )

    assert response.status_code == 200
    payload = _accepted_payload(response.text)
    assert payload["chat_id"] == str(CHAT_ID_VALUE)
    assert payload["state"] == "accepted"
    assert payload["sse_url"] == (
        f"/api/chats/{CHAT_ID_VALUE}/runs/{payload['run_id']}/sse"
    )
    assert table_count(database_url, "chat_runs") == 2
    assert instruction_bodies(database_url) == ("初回指示", "継続の依頼")
    assert dispatcher.registrations == [
        (
            CHAT_ID_VALUE,
            UUID(payload["run_id"]),
            response.headers["x-trace-id"],
        )
    ]


@pytest.mark.asyncio
async def test_append_chat_run_api_marks_new_run_error_when_dispatcher_failed(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-03 継続指示APIがdispatcher登録失敗時に追加runをerror化すること
    確認：500共通エラーとなり、既存runを維持したまま追加runだけをerrorとして保存すること
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
        instruction_id=UUID("34343434-3434-7343-8343-343434343434"),
        title="既存チャット",
        instruction="初回指示",
        run_state=RunState.COMPLETED.value,
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)
    app.state.run_execution_dispatcher = FailingRunExecutionDispatcher()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.post(
            f"/api/chats/{CHAT_ID_VALUE}/runs",
            json={"user_instruction": "継続登録失敗"},
        )

    assert response.status_code == 500
    assert _error_payload(response.text)["error"] == "internal_error"
    assert table_count(database_url, "chat_runs") == 2
    assert instruction_bodies(database_url) == ("初回指示", "継続登録失敗")
    assert sorted(run_states(database_url)) == [
        RunState.COMPLETED.value,
        RunState.ERROR.value,
    ]


@pytest.mark.asyncio
async def test_append_chat_run_api_rejects_blank_instruction_without_db_write(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-03 継続指示APIが空のユーザ指示を入力不正として扱うこと
    確認：400、validation_error、field_errors.user_instructionを返し、
    新しいrunとuser_instructionを保存しないこと
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
        instruction_id=UUID("29292929-2929-7292-8292-292929292929"),
        title="既存チャット",
        instruction="初回指示",
        run_state=RunState.COMPLETED.value,
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.post(
            f"/api/chats/{CHAT_ID_VALUE}/runs",
            json={"user_instruction": "   \n\t  "},
        )

    assert response.status_code == 400
    payload = _field_error_payload(response.text)
    assert payload["error"] == "validation_error"
    assert "user_instruction" in payload["field_errors"]
    assert table_count(database_url, "chat_runs") == 1
    assert table_count(database_url, "user_instructions") == 1
    assert instruction_bodies(database_url) == ("初回指示",)


@pytest.mark.asyncio
async def test_append_chat_run_api_rejects_unfinished_run_conflict_without_db_write(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-03 継続指示APIが未完了runを持つチャットへの多重受付を拒否すること
    確認：409共通エラーを返し、新しいrunと指示を保存せず、既存run状態を維持すること
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
        instruction_id=UUID("bbbbbbbb-bbbb-7bbb-8bbb-bbbbbbbbbbbb"),
        title="受付中チャット",
        instruction="初回指示",
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
            f"/api/chats/{CHAT_ID_VALUE}/runs",
            json={"user_instruction": "継続の依頼"},
        )

    assert response.status_code == 409
    payload = _error_payload(response.text)
    assert payload["error"] == "conflict"
    assert "detail" not in response.text
    assert table_count(database_url, "chat_runs") == 1
    assert instruction_bodies(database_url) == ("初回指示",)
    assert run_state(database_url, RUN_ID_VALUE) == RunState.ACCEPTED.value


@pytest.mark.asyncio
async def test_append_chat_run_api_rejects_missing_and_deleting_chat_without_db_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    観点：IF-SB-03 継続指示APIが対象なしと削除中チャットを受付前に拒否すること
    確認：対象なしは404、削除中は409の共通エラー形式となり、
    新しいrunとuser_instructionを保存しないこと
    """
    from backend.app.factory import create_app
    from backend.infrastructure.runtime.chat_deletion_dispatcher import (
        DatabaseChatDeletionExecutor,
    )

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    deleting_chat_id = UUID("30303030-3030-7303-8303-303030303030")
    missing_chat_id = UUID("31313131-3131-7313-8313-313131313131")
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=deleting_chat_id,
        run_id=RUN_ID_VALUE,
        session_id=SESSION_ID_VALUE,
        instruction_id=UUID("32323232-3232-7323-8323-323232323232"),
        title="削除中チャット",
        instruction="初回指示",
        run_state=RunState.COMPLETED.value,
        chat_state=ChatState.DELETING.value,
    )
    files = create_foundation_config(tmp_path, database_url=database_url)

    def execute_noop(
        self: DatabaseChatDeletionExecutor,
        chat_id: UUID,
        trace_id: str,
    ) -> None:
        return

    monkeypatch.setattr(DatabaseChatDeletionExecutor, "execute", execute_noop)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        missing_response = await client.post(
            f"/api/chats/{missing_chat_id}/runs",
            json={"user_instruction": "対象なしへの継続"},
        )
        deleting_response = await client.post(
            f"/api/chats/{deleting_chat_id}/runs",
            json={"user_instruction": "削除中への継続"},
        )

    assert missing_response.status_code == 404
    assert _error_payload(missing_response.text)["error"] == "not_found"
    assert deleting_response.status_code == 409
    assert _error_payload(deleting_response.text)["error"] == "conflict"
    assert "detail" not in missing_response.text
    assert "detail" not in deleting_response.text
    assert table_count(database_url, "chat_runs") == 1
    assert table_count(database_url, "user_instructions") == 1
    assert instruction_bodies(database_url) == ("初回指示",)


@pytest.mark.asyncio
async def test_chat_histories_api_returns_owner_active_chats_ordered_by_updated_at(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-04 履歴一覧APIがログインユーザのactiveチャットだけを返すこと
    確認：別ユーザとdeletingチャットを除外し、updated_at降順で
    chat_id、title、latest_run_id、latest_stateを返すこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    seed_chat_user(
        database_url,
        user_id=OTHER_USER_ID,
        user_name="別ユーザ",
        session_token="other-session-token",
    )
    newer_chat_id = UUID("55555555-5555-7555-8555-555555555555")
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=CHAT_ID_VALUE,
        run_id=RUN_ID_VALUE,
        session_id=SESSION_ID_VALUE,
        instruction_id=UUID("cccccccc-cccc-7ccc-8ccc-cccccccccccc"),
        title="古い履歴",
        instruction="古い指示",
        run_state=RunState.COMPLETED.value,
    )
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=newer_chat_id,
        run_id=NEXT_RUN_ID_VALUE,
        session_id=UUID("66666666-6666-7666-8666-666666666666"),
        instruction_id=UUID("dddddddd-dddd-7ddd-8ddd-dddddddddddd"),
        title="新しい履歴",
        instruction="新しい指示",
        run_state=RunState.ACCEPTED.value,
        updated_at=FIXED_CHAT_NOW + timedelta(minutes=2),
    )
    insert_chat_run(
        database_url,
        user_id=OTHER_USER_ID,
        chat_id=UUID("77777777-7777-7777-8777-777777777777"),
        run_id=UUID("88888888-8888-7888-8888-888888888888"),
        session_id=UUID("99999999-9999-7999-8999-999999999999"),
        instruction_id=UUID("eeeeeeee-eeee-7eee-8eee-eeeeeeeeeeee"),
        title="別ユーザ履歴",
        instruction="別ユーザ指示",
        run_state=RunState.COMPLETED.value,
    )
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=UUID("12121212-1212-7121-8121-121212121212"),
        run_id=UUID("13131313-1313-7131-8131-131313131313"),
        session_id=UUID("14141414-1414-7141-8141-141414141414"),
        instruction_id=UUID("15151515-1515-7151-8151-151515151515"),
        title="削除中履歴",
        instruction="削除中指示",
        run_state=RunState.COMPLETED.value,
        chat_state=ChatState.DELETING.value,
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.get("/api/chat-histories")

    assert response.status_code == 200
    payload = _history_payload(response.text)
    assert [item["chat_id"] for item in payload] == [
        str(newer_chat_id),
        str(CHAT_ID_VALUE),
    ]
    assert payload[0]["title"] == "新しい履歴"
    assert payload[0]["latest_run_id"] == str(NEXT_RUN_ID_VALUE)
    assert payload[0]["latest_state"] == RunState.ACCEPTED.value


@pytest.mark.asyncio
async def test_chat_detail_api_returns_runs_answer_and_references_for_owner(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-05 履歴詳細APIが保存済みチャット内容を画面再表示用に返すこと
    確認：所有者のactiveチャットではrun、指示、中間メッセージ、回答ブロック、
    表示用参照元URLとPDF locatorを返すこと
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
        instruction_id=UUID("16161616-1616-7161-8161-161616161616"),
        title="履歴詳細",
        instruction="詳細指示",
        run_state=RunState.COMPLETED.value,
    )
    insert_completed_answer(
        database_url,
        run_id=RUN_ID_VALUE,
        message_id=UUID("17171717-1717-7171-8171-171717171717"),
        answer_block_id=UUID("18181818-1818-7181-8181-181818181818"),
        reference_id=UUID("19191919-1919-7191-8191-191919191919"),
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.get(f"/api/chats/{CHAT_ID_VALUE}")

    assert response.status_code == 200
    payload = _detail_payload(response.text)
    assert payload["chat_id"] == str(CHAT_ID_VALUE)
    assert payload["title"] == "履歴詳細"
    assert len(payload["runs"]) == 1
    run = payload["runs"][0]
    assert run["run_id"] == str(RUN_ID_VALUE)
    assert run["state"] == RunState.COMPLETED.value
    assert run["user_instruction"] == "詳細指示"
    assert run["intermediate_messages"][0]["text"] == "作業を開始します。"
    answer_block = run["answer"]["blocks"][0]
    assert answer_block["markdown"] == "回答本文"
    reference = answer_block["references"][0]
    assert reference["url"] == "/api/references/19191919-1919-7191-8191-191919191919"
    assert reference["locator"] == {
        "page_start": 2,
        "page_end": 3,
    }


@pytest.mark.asyncio
async def test_chat_detail_api_returns_run_without_answer_before_generation(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-05 履歴詳細APIが回答未生成runを再表示できること
    確認：answerを返さず、受付済みrunの指示と状態だけを返すこと
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
        instruction_id=UUID("35353535-3535-7353-8353-353535353535"),
        title="受付済み履歴",
        instruction="未生成指示",
        run_state=RunState.ACCEPTED.value,
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.get(f"/api/chats/{CHAT_ID_VALUE}")

    assert response.status_code == 200
    payload = json.loads(response.text)
    assert isinstance(payload, dict)
    runs = payload.get("runs")
    assert isinstance(runs, list)
    run = runs[0]
    assert isinstance(run, dict)
    assert run["state"] == RunState.ACCEPTED.value
    assert run["user_instruction"] == "未生成指示"
    assert "answer" not in run


@pytest.mark.asyncio
async def test_chat_detail_api_rejects_other_user_and_deleting_chat(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-05 履歴詳細APIがユーザ分離と削除中チャット除外を守ること
    確認：別ユーザ所有チャットは404、deletingチャットは409となり、
    共通エラー形式で内部情報を返さないこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    seed_chat_user(
        database_url,
        user_id=OTHER_USER_ID,
        user_name="別ユーザ",
        session_token="other-session-token",
    )
    other_chat_id = UUID("20202020-2020-7202-8202-202020202020")
    deleting_chat_id = UUID("21212121-2121-7212-8212-212121212121")
    insert_chat_run(
        database_url,
        user_id=OTHER_USER_ID,
        chat_id=other_chat_id,
        run_id=UUID("22222222-2222-7222-8222-222222222223"),
        session_id=UUID("23232323-2323-7232-8232-232323232323"),
        instruction_id=UUID("24242424-2424-7242-8242-242424242424"),
        title="別ユーザ履歴",
        instruction="別ユーザ指示",
        run_state=RunState.COMPLETED.value,
    )
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=deleting_chat_id,
        run_id=UUID("25252525-2525-7252-8252-252525252525"),
        session_id=UUID("26262626-2626-7262-8262-262626262626"),
        instruction_id=UUID("27272727-2727-7272-8272-272727272727"),
        title="削除中履歴",
        instruction="削除中指示",
        run_state=RunState.COMPLETED.value,
        chat_state=ChatState.DELETING.value,
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        other_response = await client.get(f"/api/chats/{other_chat_id}")
        deleting_response = await client.get(f"/api/chats/{deleting_chat_id}")

    assert other_response.status_code == 404
    assert _error_payload(other_response.text)["error"] == "not_found"
    assert deleting_response.status_code == 409
    assert _error_payload(deleting_response.text)["error"] == "conflict"
    assert "detail" not in other_response.text
    assert "detail" not in deleting_response.text


def _accepted_payload(response_text: str) -> ChatAcceptedPayload:
    payload = json.loads(response_text)
    assert isinstance(payload, dict)
    chat_id = payload.get("chat_id")
    run_id = payload.get("run_id")
    sse_url = payload.get("sse_url")
    state = payload.get("state")
    assert isinstance(chat_id, str)
    assert isinstance(run_id, str)
    assert isinstance(sse_url, str)
    assert isinstance(state, str)
    return {
        "chat_id": chat_id,
        "run_id": run_id,
        "sse_url": sse_url,
        "state": state,
    }


def _history_payload(response_text: str) -> list[ChatHistoryPayload]:
    payload = json.loads(response_text)
    assert isinstance(payload, list)
    result: list[ChatHistoryPayload] = []
    for item in payload:
        assert isinstance(item, dict)
        chat_id = item.get("chat_id")
        title = item.get("title")
        latest_run_id = item.get("latest_run_id")
        latest_state = item.get("latest_state")
        updated_at = item.get("updated_at")
        assert isinstance(chat_id, str)
        assert isinstance(title, str)
        assert isinstance(latest_run_id, str) or latest_run_id is None
        assert isinstance(latest_state, str)
        assert isinstance(updated_at, str)
        history_item: ChatHistoryPayload = {
            "chat_id": chat_id,
            "title": title,
            "latest_state": latest_state,
            "updated_at": updated_at,
        }
        if latest_run_id is not None:
            history_item["latest_run_id"] = latest_run_id
        result.append(history_item)
    return result


def _detail_payload(response_text: str) -> ChatDetailPayload:
    payload = json.loads(response_text)
    assert isinstance(payload, dict)
    chat_id = payload.get("chat_id")
    title = payload.get("title")
    runs = payload.get("runs")
    assert isinstance(chat_id, str)
    assert isinstance(title, str)
    assert isinstance(runs, list)
    return {
        "chat_id": chat_id,
        "title": title,
        "runs": runs,
    }


def _field_error_payload(response_text: str) -> FieldErrorPayload:
    payload = json.loads(response_text)
    assert isinstance(payload, dict)
    error = payload.get("error")
    message = payload.get("message")
    field_errors = payload.get("field_errors")
    assert isinstance(error, str)
    assert isinstance(message, str)
    assert isinstance(field_errors, dict)
    assert all(isinstance(key, str) for key in field_errors)
    assert all(isinstance(value, str) for value in field_errors.values())
    return {
        "error": error,
        "message": message,
        "field_errors": field_errors,
    }


def _error_payload(response_text: str) -> ErrorPayload:
    payload = json.loads(response_text)
    assert isinstance(payload, dict)
    error = payload.get("error")
    message = payload.get("message")
    assert isinstance(error, str)
    assert isinstance(message, str)
    return {"error": error, "message": message}


def _assert_unauthorized_payload(response: Response) -> None:
    assert response.status_code == 401
    payload = _error_payload(response.text)
    assert payload["error"] == "unauthorized"
    assert "detail" not in response.text


class FailingRunExecutionDispatcher:
    """dispatcher登録失敗を再現する結合テスト用スタブ。"""

    def register(self, chat_id: UUID, run_id: UUID, trace_id: str) -> RunDispatchResult:
        return RunDispatchResult(
            status="failed",
            diagnostic_message="dispatcher unavailable",
        )


class RecordingRunExecutionDispatcher:
    """APIから渡されたrun実行登録を観測する結合テスト用スタブ。"""

    def __init__(self) -> None:
        self.registrations: list[tuple[UUID, UUID, str]] = []

    def register(self, chat_id: UUID, run_id: UUID, trace_id: str) -> RunDispatchResult:
        self.registrations.append((chat_id, run_id, trace_id))
        return RunDispatchResult(status="registered")

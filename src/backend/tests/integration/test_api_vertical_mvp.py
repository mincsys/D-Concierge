import asyncio
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import TypeAdapter
from pypdf import PdfWriter

from backend.app.factory import create_app
from backend.application.chat.get_chat_detail import GetChatDetailUseCase
from backend.application.execution.execute_chat_run import RunEvent
from backend.application.execution.run_event_type import RunEventType
from backend.application.ports.codex.cancel_request_result import CancelRequestResult
from backend.application.ports.database.dto import (
    AnswerBlockData,
    AnswerData,
    ArtifactData,
    DisplayReferenceData,
    HistoryItem,
)
from backend.application.ports.runtime.dispatch_status import DispatchStatus
from backend.application.ports.runtime.dto import DispatchResult
from backend.application.transactions import NoopTransactionManager
from backend.domain.execution.run_state import RunState
from backend.domain.references.source_type import SourceType
from backend.infrastructure.codex.codex_event_kind import CodexEventKind
from backend.infrastructure.codex.codex_runner import (
    CancelResult,
    CodexRunRequest,
)
from backend.infrastructure.codex.codex_runner import (
    CodexRunResult as InfrastructureCodexRunResult,
)
from backend.infrastructure.codex.jsonl_event_parser import (
    ParsedCodexEvent,
)
from backend.infrastructure.config.models import (
    AppConfig,
    AppRuntimeConfig,
    DatabaseConfig,
    GeneratorConfig,
    ServerConfig,
    TraceLogConfig,
    UiConfig,
    ValidatorConfig,
)
from backend.infrastructure.trace_log.trace_log_writer import TraceLogWriter
from backend.presentation.rest.router import _run_sse_events
from backend.presentation.schemas.api import (
    AppConfigResponseSchema,
    CancelChatRunResponseSchema,
    ChatDetailResponseSchema,
    ChatHistoryItemResponseSchema,
    ChatStartResponseSchema,
    DeleteChatResponseSchema,
)
from backend.presentation.sse.run_event_broker import RunEventSubscription
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.tests.support.memory_repository import InMemoryChatRepository


def test_app_config_exposes_only_public_ui_settings(tmp_path: Path) -> None:
    """観点：IF-SB-01。確認：画面公開項目だけを返し、内部パスやDB URLを返さない。"""
    client = _make_client(tmp_path)

    response = client.get("/api/app-config")

    assert response.status_code == 200
    payload = TypeAdapter(AppConfigResponseSchema).validate_json(response.text)
    assert payload.welcome_message == "ようこそ"
    assert payload.input_suggestions == ["要約してください"]
    assert "database" not in response.text
    assert "codex" not in response.text


def test_start_chat_persists_initial_run_and_history(tmp_path: Path) -> None:
    """観点：IF-SB-02。確認：新規チャット、受付run、指示を保存し、履歴詳細で再表示できる。"""
    client = _make_client(tmp_path)

    start_response = client.post(
        "/api/chats/start",
        json={"user_instruction": "資料を要約してください"},
    )

    assert start_response.status_code == 200
    accepted = TypeAdapter(ChatStartResponseSchema).validate_json(start_response.text)
    assert UUID(accepted.chat_id)
    assert UUID(accepted.run_id)
    assert accepted.state == RunState.ACCEPTED.value
    assert (
        accepted.sse_url == f"/api/chats/{accepted.chat_id}/runs/{accepted.run_id}/sse"
    )

    detail_response = client.get(f"/api/chats/{accepted.chat_id}")
    detail = TypeAdapter(ChatDetailResponseSchema).validate_json(detail_response.text)
    assert detail.chat_id == accepted.chat_id
    assert detail.runs[0].run_id == accepted.run_id
    assert detail.runs[0].user_instruction == "資料を要約してください"


def test_start_chat_registers_accepted_run_to_dispatcher(tmp_path: Path) -> None:
    """観点：IF-SB-02と実行登録。

    確認：新規チャット受付後にrun dispatcherへチャットIDとrun IDを渡す。
    """
    repository = InMemoryChatRepository()
    dispatcher = RecordingDispatcher()
    app = create_app(
        config=_make_config(tmp_path),
        repository=repository,
        run_dispatcher=dispatcher,
    )
    client = TestClient(app)

    response = client.post(
        "/api/chats/start",
        json={"user_instruction": "資料を要約してください"},
    )

    accepted = TypeAdapter(ChatStartResponseSchema).validate_json(response.text)
    assert dispatcher.registered == [(UUID(accepted.chat_id), UUID(accepted.run_id))]


def test_start_chat_rejects_blank_instruction_without_partial_persistence(
    tmp_path: Path,
) -> None:
    """観点：IF-SB-02異常系。確認：空白指示をHTTP 400で拒否し、履歴を作成しない。"""
    client = _make_client(tmp_path)

    response = client.post("/api/chats/start", json={"user_instruction": "   "})

    assert response.status_code == 400
    histories_response = client.get("/api/chat-histories")
    histories = TypeAdapter(list[ChatHistoryItemResponseSchema]).validate_json(
        histories_response.text
    )
    assert histories == []


def test_append_run_rejects_when_unfinished_run_exists(tmp_path: Path) -> None:
    """観点：IF-SB-03競合。

    確認：未完了runがあるチャットへの継続指示をHTTP 409で拒否する。
    """
    client = _make_client(tmp_path)
    start_response = client.post(
        "/api/chats/start",
        json={"user_instruction": "初回"},
    )
    accepted = TypeAdapter(ChatStartResponseSchema).validate_json(start_response.text)

    response = client.post(
        f"/api/chats/{accepted.chat_id}/runs",
        json={"user_instruction": "追加"},
    )

    assert response.status_code == 409


def test_append_run_accepts_after_previous_run_is_terminal(tmp_path: Path) -> None:
    """観点：IF-SB-03正常系。確認：終端済みrunだけのチャットへ継続指示を追加する。"""
    client = _make_client(tmp_path)
    start_response = client.post(
        "/api/chats/start",
        json={"user_instruction": "初回"},
    )
    accepted = TypeAdapter(ChatStartResponseSchema).validate_json(start_response.text)
    client.post(f"/api/chats/{accepted.chat_id}/runs/{accepted.run_id}/cancel")

    response = client.post(
        f"/api/chats/{accepted.chat_id}/runs",
        json={"user_instruction": "追加"},
    )

    assert response.status_code == 200
    appended = TypeAdapter(ChatStartResponseSchema).validate_json(response.text)
    assert appended.chat_id == accepted.chat_id
    assert appended.state == RunState.ACCEPTED.value


def test_cancel_accepted_run_returns_cancel_request_and_terminal_history(
    tmp_path: Path,
) -> None:
    """観点：IF-SB-07。確認：受付runをキャンセルし、応答と履歴状態を設計どおりにする。"""
    client = _make_client(tmp_path)
    start_response = client.post(
        "/api/chats/start",
        json={"user_instruction": "初回"},
    )
    accepted = TypeAdapter(ChatStartResponseSchema).validate_json(start_response.text)

    cancel_response = client.post(
        f"/api/chats/{accepted.chat_id}/runs/{accepted.run_id}/cancel"
    )

    assert cancel_response.status_code == 200
    canceled = TypeAdapter(CancelChatRunResponseSchema).validate_json(
        cancel_response.text
    )
    assert canceled.run_id == accepted.run_id
    assert canceled.state == "キャンセル要求中"
    assert canceled.user_message == "処理をキャンセルしています。"

    detail_response = client.get(f"/api/chats/{accepted.chat_id}")
    detail = TypeAdapter(ChatDetailResponseSchema).validate_json(detail_response.text)
    assert detail.runs[0].state == "キャンセル済み"
    assert detail.runs[0].user_message == "処理をキャンセルしました。"


def test_histories_are_returned_in_updated_desc_order(tmp_path: Path) -> None:
    """観点：IF-SB-04。確認：履歴一覧は更新日時降順で、本文や中間メッセージ全文を含めない。"""
    client = _make_client(tmp_path)
    first_response = client.post(
        "/api/chats/start",
        json={"user_instruction": "古い履歴"},
    )
    second_response = client.post(
        "/api/chats/start",
        json={"user_instruction": "新しい履歴"},
    )
    first = TypeAdapter(ChatStartResponseSchema).validate_json(first_response.text)
    second = TypeAdapter(ChatStartResponseSchema).validate_json(second_response.text)

    response = client.get("/api/chat-histories")

    assert response.status_code == 200
    histories = TypeAdapter(list[ChatHistoryItemResponseSchema]).validate_json(
        response.text
    )
    assert [history.chat_id for history in histories] == [second.chat_id, first.chat_id]
    assert "user_instruction" not in response.text
    assert histories[0].latest_state == "受付"


def test_sse_sends_current_state_first(tmp_path: Path) -> None:
    """観点：IF-SB-06。確認：SSE接続直後に現在状態のstateイベントを送信する。"""
    client = _make_client(tmp_path)
    start_response = client.post(
        "/api/chats/start",
        json={"user_instruction": "初回"},
    )
    accepted = TypeAdapter(ChatStartResponseSchema).validate_json(start_response.text)

    with client.stream(
        "GET",
        f"/api/chats/{accepted.chat_id}/runs/{accepted.run_id}/sse",
    ) as response:
        body = next(response.iter_text())

    assert "event: state" in body
    assert f'"run_id":"{accepted.run_id}"' in body
    assert '"state":"受付"' in body


def test_sse_streams_published_message_and_answer_events(tmp_path: Path) -> None:
    """観点：IF-SB-06。

    確認：接続直後の現在状態に続けて、購読した中間メッセージと最終回答をSSE配信する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("初回")
    reference_id = UUID("00000000-0000-0000-0000-000000000601")
    event_source = PreloadedRunEventSource(
        events=(
            RunEvent(
                event=RunEventType.MESSAGE,
                chat_id=accepted.chat_id,
                run_id=accepted.run_id,
                text="資料を検索しています。",
            ),
            RunEvent(
                event=RunEventType.ANSWER,
                chat_id=accepted.chat_id,
                run_id=accepted.run_id,
                state=RunState.COMPLETED,
                answer=AnswerData(
                    blocks=(
                        AnswerBlockData(
                            markdown="検証済み回答",
                            references=(
                                DisplayReferenceData(
                                    reference_id=reference_id,
                                    source_type=SourceType.PDF,
                                    label="資料",
                                    relative_path="manual.pdf",
                                    page_start=2,
                                    page_end=3,
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        )
    )
    app = create_app(
        config=_make_config(tmp_path),
        repository=repository,
        run_dispatcher=None,
        run_event_source=event_source,
    )
    client = TestClient(app)

    with client.stream(
        "GET",
        f"/api/chats/{accepted.chat_id}/runs/{accepted.run_id}/sse",
    ) as response:
        body = "".join(response.iter_text())

    assert "event: state" in body
    assert "event: message" in body
    assert "event: answer" in body
    assert '"text":"資料を検索しています。"' in body
    assert '"markdown":"検証済み回答"' in body
    assert f'"/api/references/{reference_id}"' in body


def test_sse_replays_saved_intermediate_messages_on_connect(tmp_path: Path) -> None:
    """観点：IF-SB-06。

    確認：SSE接続前に保存済みの中間メッセージも、接続直後に発生順で配信する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("初回")
    repository.add_intermediate_message(
        accepted.chat_id, accepted.run_id, "作業を開始します。"
    )
    app = create_app(
        config=_make_config(tmp_path),
        repository=repository,
        run_dispatcher=None,
        run_event_source=ClosedRunEventSource(),
    )
    client = TestClient(app)

    with client.stream(
        "GET",
        f"/api/chats/{accepted.chat_id}/runs/{accepted.run_id}/sse",
    ) as response:
        body = "".join(response.iter_text())

    assert "event: state" in body
    assert "event: message" in body
    assert body.index("event: state") < body.index("event: message")
    assert '"text":"作業を開始します。"' in body


def test_sse_streams_state_and_error_events(tmp_path: Path) -> None:
    """観点：IF-SB-06異常系。

    確認：購読した状態変化とエラー終端をSSE配信し、接続を終了する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("初回")
    event_source = PreloadedRunEventSource(
        events=(
            RunEvent(
                event=RunEventType.STATE,
                chat_id=accepted.chat_id,
                run_id=accepted.run_id,
                state=RunState.RUNNING,
            ),
            RunEvent(
                event=RunEventType.ERROR,
                chat_id=accepted.chat_id,
                run_id=accepted.run_id,
                state=RunState.ERROR,
                user_message="回答の生成に失敗しました。再度お試しください。",
            ),
        )
    )
    app = create_app(
        config=_make_config(tmp_path),
        repository=repository,
        run_dispatcher=None,
        run_event_source=event_source,
    )
    client = TestClient(app)

    with client.stream(
        "GET",
        f"/api/chats/{accepted.chat_id}/runs/{accepted.run_id}/sse",
    ) as response:
        body = "".join(response.iter_text())

    assert body.count("event: state") == 2
    assert "event: error" in body
    assert '"state":"エラー"' in body
    assert '"user_message":"回答の生成に失敗しました。再度お試しください。"' in body


def test_sse_closes_when_subscription_returns_no_event(tmp_path: Path) -> None:
    """観点：IF-SB-06切断。

    確認：購読キューが終端した場合は、初期状態だけを送信して終了する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("初回")
    app = create_app(
        config=_make_config(tmp_path),
        repository=repository,
        run_dispatcher=None,
        run_event_source=ClosedRunEventSource(),
    )
    client = TestClient(app)

    with client.stream(
        "GET",
        f"/api/chats/{accepted.chat_id}/runs/{accepted.run_id}/sse",
    ) as response:
        body = "".join(response.iter_text())

    assert body.count("event: state") == 1
    assert '"state":"受付"' in body


@pytest.mark.asyncio
async def test_sse_disconnect_unsubscribes_without_waiting_for_event(
    tmp_path: Path,
) -> None:
    """観点：SSE購読切断。

    確認：イベント未到着の接続切断でも待機を継続せず、購読を解除する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("初回")
    event_source = OpenRunEventSource()
    request = DisconnectingAfterInitialStateRequest()
    stream = _run_sse_events(
        GetChatDetailUseCase(
            repository=repository,
            transaction_manager=NoopTransactionManager(),
        ),
        event_source,
        accepted.chat_id,
        accepted.run_id,
        TraceLogWriter(tmp_path / "logs"),
        "trace-sse-disconnect",
        request,
    )

    first_chunk = await anext(stream)
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(anext(stream), timeout=0.5)

    assert b"event: state" in first_chunk
    assert event_source.subscription is not None
    assert event_source.unsubscribed == [event_source.subscription]


def test_chat_detail_returns_completed_answer_and_references(tmp_path: Path) -> None:
    """観点：IF-SB-05。確認：回答と表示用参照元メタ情報を履歴詳細で再表示する。"""
    client, repository = _make_client_with_repository(tmp_path)
    reference_id = repository.save_completed_answer_for_test(
        markdown="検証済み回答",
        reference_relative_path="manual.pdf",
        artifact_relative_path="run-id/chart.svg",
        artifact_mime_type="image/svg+xml",
    )
    histories_response = client.get("/api/chat-histories")
    histories = TypeAdapter(list[ChatHistoryItemResponseSchema]).validate_json(
        histories_response.text
    )

    response = client.get(f"/api/chats/{histories[0].chat_id}")

    assert response.status_code == 200
    detail = TypeAdapter(ChatDetailResponseSchema).validate_json(response.text)
    assert detail.runs[0].state == "完了"
    assert detail.runs[0].answer is not None
    assert detail.runs[0].answer.blocks[0].markdown == "検証済み回答"
    assert (
        detail.runs[0].answer.blocks[0].references[0].url
        == f"/api/references/{reference_id}"
    )
    assert detail.runs[0].answer.blocks[0].references[0].locator.page_start == 1


def test_delete_chat_marks_deleting_and_excludes_history_and_detail(
    tmp_path: Path,
) -> None:
    """観点：IF-SB-10。

    確認：削除受付後、対象チャットを削除中にし、履歴一覧と履歴詳細の対象外にする。
    """
    client = _make_client(tmp_path)
    start_response = client.post(
        "/api/chats/start",
        json={"user_instruction": "削除対象"},
    )
    accepted = TypeAdapter(ChatStartResponseSchema).validate_json(start_response.text)

    delete_response = client.delete(f"/api/chats/{accepted.chat_id}")

    assert delete_response.status_code == 202
    deleted = TypeAdapter(DeleteChatResponseSchema).validate_json(delete_response.text)
    assert deleted.chat_id == accepted.chat_id
    assert deleted.chat_state == "削除中"
    histories = TypeAdapter(list[ChatHistoryItemResponseSchema]).validate_json(
        client.get("/api/chat-histories").text
    )
    assert [history.chat_id for history in histories] == []
    detail_response = client.get(f"/api/chats/{accepted.chat_id}")
    assert detail_response.status_code == 409
    assert detail_response.json()["message"] == (
        "このチャットは削除中のため操作できません。"
    )


def test_delete_chat_is_idempotent_while_chat_is_deleting(tmp_path: Path) -> None:
    """観点：IF-SB-10冪等性。

    確認：削除中チャットへの削除再送は受付済みとして扱う。
    """
    client = _make_client(tmp_path)
    start_response = client.post(
        "/api/chats/start",
        json={"user_instruction": "削除対象"},
    )
    accepted = TypeAdapter(ChatStartResponseSchema).validate_json(start_response.text)

    first_response = client.delete(f"/api/chats/{accepted.chat_id}")
    second_response = client.delete(f"/api/chats/{accepted.chat_id}")

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert second_response.json()["chat_state"] == "削除中"


def test_delete_chat_returns_not_found_after_physical_deletion(tmp_path: Path) -> None:
    """観点：IF-SB-10対象なし。

    確認：物理削除後または存在しないチャットへの削除要求は404として扱う。
    """
    client = _make_client(tmp_path)
    missing_chat_id = uuid4()

    response = client.delete(f"/api/chats/{missing_chat_id}")

    assert response.status_code == 404


def test_deleting_chat_rejects_followup_sse_reference_and_artifact(
    tmp_path: Path,
) -> None:
    """観点：IF-SB-10削除中競合。

    確認：削除中チャットへの継続指示、SSE購読、参照元取得、成果物取得を409で拒否する。
    """
    client, repository = _make_client_with_repository(tmp_path)
    reference_id = repository.save_completed_answer_for_test(
        markdown="回答",
        reference_relative_path="manual.pdf",
        artifact_relative_path="run-id/chart.svg",
        artifact_mime_type="image/svg+xml",
    )
    artifact_id = repository.latest_artifact_id_for_test()
    histories = TypeAdapter(list[ChatHistoryItemResponseSchema]).validate_json(
        client.get("/api/chat-histories").text
    )
    detail = TypeAdapter(ChatDetailResponseSchema).validate_json(
        client.get(f"/api/chats/{histories[0].chat_id}").text
    )
    chat_id = histories[0].chat_id
    run_id = detail.runs[0].run_id

    delete_response = client.delete(f"/api/chats/{chat_id}")

    assert delete_response.status_code == 202
    expected = "このチャットは削除中のため操作できません。"
    followup_response = client.post(
        f"/api/chats/{chat_id}/runs",
        json={"user_instruction": "続けて"},
    )
    sse_response = client.get(f"/api/chats/{chat_id}/runs/{run_id}/sse")
    reference_response = client.get(f"/api/references/{reference_id}")
    artifact_response = client.get(f"/api/artifacts/{artifact_id}")

    assert followup_response.status_code == 409
    assert followup_response.json()["message"] == expected
    assert sse_response.status_code == 409
    assert sse_response.json()["message"] == expected
    assert reference_response.status_code == 409
    assert reference_response.json()["message"] == expected
    assert artifact_response.status_code == 409
    assert artifact_response.json()["message"] == expected


def test_reference_endpoint_serves_saved_pdf_inside_datasource(tmp_path: Path) -> None:
    """観点：IF-SB-09。確認：保存済みPDF参照元をapplication/pdfで配信する。"""
    client, repository = _make_client_with_repository(tmp_path)
    pdf_path = tmp_path / "readonly" / "manual.pdf"
    pdf_path.parent.mkdir()
    pdf_path.write_bytes(b"%PDF-1.4\n")
    reference_id = repository.save_completed_answer_for_test(
        markdown="回答",
        reference_relative_path="manual.pdf",
        artifact_relative_path="run-id/chart.svg",
        artifact_mime_type="image/svg+xml",
    )

    response = client.get(f"/api/references/{reference_id}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == b"%PDF-1.4\n"


def test_reference_endpoint_rejects_path_traversal(tmp_path: Path) -> None:
    """観点：IF-SB-09異常系。

    確認：共有データソース外の参照元パスをHTTP 403で拒否する。
    """
    client, repository = _make_client_with_repository(tmp_path)
    reference_id = repository.save_completed_answer_for_test(
        markdown="回答",
        reference_relative_path="../secret.pdf",
        artifact_relative_path="run-id/chart.svg",
        artifact_mime_type="image/svg+xml",
    )

    response = client.get(f"/api/references/{reference_id}")

    assert response.status_code == 403
    assert "secret.pdf" not in response.text


def test_artifact_endpoint_serves_allowed_saved_artifact(tmp_path: Path) -> None:
    """観点：IF-SB-08。確認：採用済み成果物を保存済みMIMEタイプで配信する。"""
    client, repository = _make_client_with_repository(tmp_path)
    artifact_path = tmp_path / "codex" / "saved_artifacts" / "run-id" / "chart.svg"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text("<svg />", encoding="utf-8")
    repository.save_completed_answer_for_test(
        markdown="回答",
        reference_relative_path="manual.pdf",
        artifact_relative_path="run-id/chart.svg",
        artifact_mime_type="image/svg+xml",
    )
    artifact_id = repository.latest_artifact_id_for_test()

    response = client.get(f"/api/artifacts/{artifact_id}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"
    assert response.text == "<svg />"


def test_artifact_delivery_allows_jpeg(tmp_path: Path) -> None:
    """観点：IF-SB-08。確認：jpg/jpeg成果物をimage/jpegで配信する。"""
    client, repository = _make_client_with_repository(tmp_path)
    artifact_path = tmp_path / "codex" / "saved_artifacts" / "run-id" / "photo.jpg"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_bytes(b"jpeg")
    repository.save_completed_answer_for_test(
        markdown="回答",
        reference_relative_path="manual.pdf",
        artifact_relative_path="run-id/photo.jpg",
        artifact_mime_type="image/jpeg",
    )
    artifact_id = repository.latest_artifact_id_for_test()

    response = client.get(f"/api/artifacts/{artifact_id}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content == b"jpeg"


def test_api_sse_reference_and_artifact_boundaries_do_not_write_success_trace_logs(
    tmp_path: Path,
) -> None:
    """観点：トレースログ。

    確認：REST、SSE、参照元PDF配信、Codex成果物配信の正常系ではトレースログを保存しない。
    """
    client, repository = _make_client_with_repository(tmp_path)
    pdf_path = tmp_path / "readonly" / "manual.pdf"
    pdf_path.parent.mkdir()
    pdf_path.write_bytes(b"%PDF-1.4\n")
    artifact_path = tmp_path / "codex" / "saved_artifacts" / "run-id" / "chart.svg"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text("<svg />", encoding="utf-8")
    reference_id = repository.save_completed_answer_for_test(
        markdown="回答",
        reference_relative_path="manual.pdf",
        artifact_relative_path="run-id/chart.svg",
        artifact_mime_type="image/svg+xml",
    )
    artifact_id = repository.latest_artifact_id_for_test()
    histories = TypeAdapter(list[ChatHistoryItemResponseSchema]).validate_json(
        client.get("/api/chat-histories").text
    )
    run_id = histories[0].latest_run_id
    assert run_id is not None

    client.get(f"/api/chats/{histories[0].chat_id}")
    with client.stream(
        "GET",
        f"/api/chats/{histories[0].chat_id}/runs/{run_id}/sse",
    ) as response:
        _ = "".join(response.iter_text())
    client.get(f"/api/references/{reference_id}")
    client.get(f"/api/artifacts/{artifact_id}")

    assert _trace_records(tmp_path) == []


def test_input_failure_does_not_write_trace_log(tmp_path: Path) -> None:
    """観点：トレースログ。確認：入力不正は準正常系としてログ保存しない。"""
    client = _make_client(tmp_path)

    response = client.post("/api/chats/start", json={"user_instruction": "   "})

    assert response.status_code == 400
    assert _trace_records(tmp_path) == []


def test_request_validation_failure_does_not_write_trace_log(tmp_path: Path) -> None:
    """観点：トレースログ。確認：リクエスト形式不正はログ保存しない。"""
    client = _make_client(tmp_path)

    response = client.post("/api/chats/start", json={})

    assert response.status_code == 422
    assert response.json() == {
        "error": "input",
        "message": "リクエストの形式が不正です。",
    }
    assert _trace_records(tmp_path) == []


def test_artifact_endpoint_rejects_disallowed_mime_type(tmp_path: Path) -> None:
    """観点：IF-SB-08異常系。確認：許可外MIMEタイプの成果物をHTTP 403で拒否する。"""
    client, repository = _make_client_with_repository(tmp_path)
    repository.save_completed_answer_for_test(
        markdown="回答",
        reference_relative_path="manual.pdf",
        artifact_relative_path="run-id/script.js",
        artifact_mime_type="application/javascript",
    )
    artifact_id = repository.latest_artifact_id_for_test()

    response = client.get(f"/api/artifacts/{artifact_id}")

    assert response.status_code == 403


def test_reference_endpoint_returns_404_when_pdf_file_is_missing(
    tmp_path: Path,
) -> None:
    """観点：IF-SB-09異常系。確認：保存メタ情報のPDF実体がない場合はHTTP 404にする。"""
    client, repository = _make_client_with_repository(tmp_path)
    reference_id = repository.save_completed_answer_for_test(
        markdown="回答",
        reference_relative_path="missing.pdf",
        artifact_relative_path="run-id/chart.svg",
        artifact_mime_type="image/svg+xml",
    )

    response = client.get(f"/api/references/{reference_id}")

    assert response.status_code == 404


def test_artifact_endpoint_returns_404_when_file_is_missing(tmp_path: Path) -> None:
    """観点：IF-SB-08異常系。

    確認：保存メタ情報の成果物実体がない場合はHTTP 404にする。
    """
    client, repository = _make_client_with_repository(tmp_path)
    accepted = repository.create_chat_with_first_run("成果物確認")
    artifact_id = UUID("00000000-0000-0000-0000-000000000302")
    repository.save_completed_answer(
        accepted.chat_id,
        accepted.run_id,
        AnswerData(
            blocks=(
                AnswerBlockData(
                    markdown="回答",
                    artifacts=(
                        ArtifactData(
                            artifact_id=artifact_id,
                            mime_type="image/png",
                            relative_path="run-id/missing.png",
                        ),
                    ),
                ),
            ),
        ),
    )

    response = client.get(f"/api/artifacts/{artifact_id}")

    assert response.status_code == 404


def test_missing_chat_detail_returns_404(tmp_path: Path) -> None:
    """観点：IF-SB-05異常系。確認：対象チャットなしをHTTP 404にする。"""
    client = _make_client(tmp_path)

    response = client.get("/api/chats/00000000-0000-0000-0000-000000009999")

    assert response.status_code == 404


def test_spa_static_fallback_serves_index_without_catching_api(tmp_path: Path) -> None:
    """観点：SPA静的配信。確認：非API GETだけをindex.htmlへfallbackする。"""
    dist_dir = Path("src/backend/app/static/dist")
    index_path = dist_dir / "index.html"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("<main>SPA</main>", encoding="utf-8")
    try:
        client = _make_client(tmp_path)

        page_response = client.get("/chat/history")
        api_response = client.get("/api/unknown")
    finally:
        index_path.unlink(missing_ok=True)

    assert page_response.status_code == 200
    assert page_response.text == "<main>SPA</main>"
    assert api_response.status_code == 404


def test_repository_system_error_returns_500(tmp_path: Path) -> None:
    """観点：エラー変換。確認：RepositoryのSYSTEM例外をHTTP 500にする。"""
    app = create_app(
        config=_make_config(tmp_path),
        repository=BrokenHistoryRepository(),
        run_dispatcher=None,
    )
    client = TestClient(app)

    response = client.get("/api/chat-histories")

    assert response.status_code == 500


def test_unexpected_api_error_writes_system_trace_log(tmp_path: Path) -> None:
    """観点：トレースログ。

    確認：想定外例外でもSYSTEM分類のAPI失敗ログを保存する。
    """
    app = create_app(
        config=_make_config(tmp_path),
        repository=UnexpectedHistoryRepository(),
        run_dispatcher=None,
    )
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/api/chat-histories")

    assert response.status_code == 500
    records = _trace_records(tmp_path)
    assert any(
        record["event_name"] == "api_failed"
        and record["stage"] == "chat_histories"
        and record["error_type"] == "system"
        and record["exception_type"] == "RuntimeError"
        and "stacktrace" in record
        for record in records
    )


def test_create_app_writes_trace_log_with_app_timezone_path(tmp_path: Path) -> None:
    """観点：トレースログ。確認：アプリ共通タイムゾーンの日時でログパスを作る。"""
    app = create_app(
        config=_make_config(tmp_path),
        repository=UnexpectedHistoryRepository(),
        run_dispatcher=None,
        clock=FixedClock(datetime(2026, 5, 10, 15, 0, tzinfo=UTC)),
    )
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/api/chat-histories")

    assert response.status_code == 500
    log_path = tmp_path / "logs/trace/2026-05-11/00-00-00_000000_api_failed.yaml"
    payload = yaml.safe_load(log_path.read_text(encoding="utf-8"))
    assert payload["occurred_at"] == "2026-05-11T00:00:00+09:00"
    assert payload["event_name"] == "api_failed"


def test_startup_recovery_reregisters_and_terminalizes_unfinished_runs(
    tmp_path: Path,
) -> None:
    """観点：起動時実行回復。確認：未完了runを再登録または終端状態へ整合する。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("accepted run")
    running = repository.create_chat_with_first_run("running run")
    validating = repository.create_chat_with_first_run("validating run")
    canceling = repository.create_chat_with_first_run("cancel requested run")
    completed = repository.create_chat_with_first_run("completed run")
    repository.set_run_state(running.chat_id, running.run_id, RunState.RUNNING)
    repository.set_run_state(validating.chat_id, validating.run_id, RunState.VALIDATING)
    repository.set_run_state(
        canceling.chat_id, canceling.run_id, RunState.CANCEL_REQUESTED
    )
    repository.set_run_state(completed.chat_id, completed.run_id, RunState.COMPLETED)
    dispatcher = RecordingDispatcher()

    create_app(
        config=_make_config(tmp_path),
        repository=repository,
        run_dispatcher=dispatcher,
    )

    assert dispatcher.registered == [(accepted.chat_id, accepted.run_id)]
    assert (
        repository.get_chat_detail(accepted.chat_id).runs[0].state is RunState.ACCEPTED
    )
    assert repository.get_chat_detail(running.chat_id).runs[0].state is RunState.ERROR
    assert (
        repository.get_chat_detail(validating.chat_id).runs[0].state is RunState.ERROR
    )
    assert (
        repository.get_chat_detail(canceling.chat_id).runs[0].state is RunState.CANCELED
    )
    assert (
        repository.get_chat_detail(completed.chat_id).runs[0].state
        is RunState.COMPLETED
    )


def test_create_app_cleans_expired_trace_logs(tmp_path: Path) -> None:
    """観点：トレースログ保持。確認：アプリ生成時に保存期間超過ログを削除する。"""
    expired_dir = tmp_path / "logs/trace/2026-01-01"
    retained_dir = tmp_path / "logs/trace/not-a-date"
    expired_dir.mkdir(parents=True)
    retained_dir.mkdir(parents=True)
    (expired_dir / "old.yaml").write_text("{}", encoding="utf-8")
    (retained_dir / "kept.yaml").write_text("{}", encoding="utf-8")

    create_app(
        config=_make_config(tmp_path),
        repository=InMemoryChatRepository(),
        run_dispatcher=None,
    )

    assert expired_dir.exists() is False
    assert retained_dir.exists()


def test_default_runtime_executes_start_chat_through_codex_adapters(
    tmp_path: Path,
) -> None:
    """観点：既定実行構成。

    確認：create_app既定のdispatcher/adapterで生成、検証、回答保存まで到達する。
    """
    repository = InMemoryChatRepository()
    datasource_dir = tmp_path / "readonly"
    datasource_dir.mkdir()
    _write_pdf(datasource_dir / "manual.pdf", page_count=2)
    codex_runner = RecordingApplicationCodexRunner(
        generation_result=InfrastructureCodexRunResult(
            events=(
                ParsedCodexEvent(
                    kind=CodexEventKind.THREAD_STARTED,
                    event_type="thread.started",
                    thread_id="generation-thread",
                ),
                ParsedCodexEvent(
                    kind=CodexEventKind.AGENT_MESSAGE,
                    event_type="item.completed",
                    text='{"payload":{"kind":"progress","text":"PDFを確認しています。"}}',
                ),
                ParsedCodexEvent(
                    kind=CodexEventKind.AGENT_MESSAGE,
                    event_type="item.completed",
                    text=(
                        '{"payload":{"kind":"final","answers":[{"text":"回答です。","references":[{'
                        '"source_type":"pdf","locator":{"path":"readonly/manual.pdf",'
                        '"start_page":1,"end_page":2}}]}]}}'
                    ),
                ),
                ParsedCodexEvent(
                    kind=CodexEventKind.TURN_COMPLETED, event_type="turn.completed"
                ),
            ),
            final_message=(
                '{"payload":{"kind":"final","answers":[{"text":"回答です。","references":[{'
                '"source_type":"pdf","locator":{"path":"readonly/manual.pdf",'
                '"start_page":1,"end_page":2}}]}]}}'
            ),
            codex_conversation_id="generation-thread",
        ),
        validation_result=InfrastructureCodexRunResult(
            events=(
                ParsedCodexEvent(
                    kind=CodexEventKind.THREAD_STARTED,
                    event_type="thread.started",
                    thread_id="validation-thread",
                ),
                ParsedCodexEvent(
                    kind=CodexEventKind.AGENT_MESSAGE,
                    event_type="item.completed",
                    text='{"payload":{"kind":"progress","text":"参照元PDFを検証しています。"}}',
                ),
                ParsedCodexEvent(
                    kind=CodexEventKind.UNKNOWN, event_type="item.completed"
                ),
                ParsedCodexEvent(
                    kind=CodexEventKind.AGENT_MESSAGE,
                    event_type="item.completed",
                    text='{"payload":{"kind":"final","valid":true,"comment":""}}',
                ),
                ParsedCodexEvent(
                    kind=CodexEventKind.TURN_COMPLETED, event_type="turn.completed"
                ),
            ),
            final_message='{"payload":{"kind":"final","valid":true,"comment":""}}',
            codex_conversation_id="validation-thread",
        ),
    )
    app = create_app(
        config=_make_config(tmp_path),
        repository=repository,
        codex_runner=codex_runner,
        background_executor=ImmediateBackgroundExecutor(),
    )
    client = TestClient(app)

    response = client.post(
        "/api/chats/start",
        json={"user_instruction": "資料を要約してください"},
    )

    assert response.status_code == 200
    accepted = TypeAdapter(ChatStartResponseSchema).validate_json(response.text)
    detail_response = client.get(f"/api/chats/{accepted.chat_id}")
    detail = TypeAdapter(ChatDetailResponseSchema).validate_json(detail_response.text)
    saved_context = repository.get_chat_runtime_context(UUID(accepted.chat_id))
    assert detail.runs[0].state == "完了"
    assert [message.text for message in detail.runs[0].intermediate_messages] == [
        "作業を開始します。",
        "PDFを確認しています。",
        "作業が完了しました。",
        "回答を検証します。",
        "参照元PDFを検証しています。",
        "回答を検証しました。",
    ]
    assert detail.runs[0].answer is not None
    assert detail.runs[0].answer.blocks[0].markdown == "回答です。"
    assert detail.runs[0].answer.blocks[0].references[0].label == "manual.pdf"
    assert detail.runs[0].answer.blocks[0].references[0].locator.page_start == 1
    assert saved_context.generation_conversation_id == "generation-thread"
    assert saved_context.validation_conversation_id == "validation-thread"
    assert codex_runner.generation_requests[0].timeout_seconds == 300
    assert codex_runner.validation_requests[0].timeout_seconds == 300
    generation_readonly_pdf = (
        codex_runner.generation_requests[0].workdir / "readonly" / "manual.pdf"
    )
    validation_readonly_pdf = (
        codex_runner.validation_requests[0].workdir / "readonly" / "manual.pdf"
    )
    assert (codex_runner.generation_requests[0].workdir / "readonly").is_symlink()
    assert (codex_runner.validation_requests[0].workdir / "readonly").is_symlink()
    assert generation_readonly_pdf.resolve() == datasource_dir / "manual.pdf"
    assert validation_readonly_pdf.resolve() == datasource_dir / "manual.pdf"
    assert not (
        codex_runner.validation_requests[0].workdir
        / "readonly"
        / "answer-candidate.json"
    ).exists()


@dataclass(slots=True)
class RecordingDispatcher:
    """テスト用run dispatcher。"""

    registered: list[tuple[UUID, UUID]] = field(default_factory=list)

    def register(
        self,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str = "",
    ) -> DispatchResult:
        """登録されたrun IDを記録する。"""
        _ = trace_id
        self.registered.append((chat_id, run_id))
        return DispatchResult(status=DispatchStatus.REGISTERED)


class BrokenHistoryRepository(InMemoryChatRepository):
    """履歴一覧でシステム例外を返すテスト用Repository。"""

    def list_histories(self) -> tuple[HistoryItem, ...]:
        """システム例外を発生させる。"""
        raise AppError(
            ErrorType.SYSTEM,
            trace=True,
            diagnostic_message="DB接続に失敗しました。",
        )


class UnexpectedHistoryRepository(InMemoryChatRepository):
    """履歴一覧で想定外例外を返すテスト用Repository。"""

    def list_histories(self) -> tuple[HistoryItem, ...]:
        """想定外例外を発生させる。"""
        raise RuntimeError("unexpected failure")


@dataclass(slots=True)
class PreloadedRunEventSource:
    """購読開始時にイベントを投入するテスト用RunEventSource。"""

    events: tuple[RunEvent, ...]
    subscriptions: list[RunEventSubscription] = field(default_factory=list)

    def subscribe(self, run_id: UUID) -> RunEventSubscription:
        """購読を開始し、固定イベントを投入する。"""
        subscription = RunEventSubscription(run_id=run_id)
        for event in self.events:
            subscription.push(event)
        self.subscriptions.append(subscription)
        return subscription

    def unsubscribe(self, subscription: RunEventSubscription) -> None:
        """購読を解除する。"""
        subscription.close()


class ClosedRunEventSource:
    """購読開始時に終端済みsubscriptionを返すテスト用RunEventSource。"""

    def subscribe(self, run_id: UUID) -> RunEventSubscription:
        """終端済みsubscriptionを返す。"""
        subscription = RunEventSubscription(run_id=run_id)
        subscription.close()
        return subscription

    def unsubscribe(self, subscription: RunEventSubscription) -> None:
        """購読を解除する。"""
        subscription.close()


@dataclass(slots=True)
class OpenRunEventSource:
    """イベント未到着の購読を保持するテスト用RunEventSource。"""

    subscription: RunEventSubscription | None = None
    unsubscribed: list[RunEventSubscription] = field(default_factory=list)

    def subscribe(self, run_id: UUID) -> RunEventSubscription:
        """空のsubscriptionを返す。"""
        self.subscription = RunEventSubscription(run_id=run_id)
        return self.subscription

    def unsubscribe(self, subscription: RunEventSubscription) -> None:
        """購読解除を記録する。"""
        self.unsubscribed.append(subscription)
        subscription.close()


@dataclass(slots=True)
class DisconnectingAfterInitialStateRequest:
    """初期状態送信後に切断済みを返すテスト用Request。"""

    checks: int = 0

    async def is_disconnected(self) -> bool:
        """初回確認では接続中、次回以降は切断済みを返す。"""
        self.checks += 1
        return self.checks > 1


@dataclass(slots=True)
class ImmediateBackgroundExecutor:
    """テスト用にsubmitされた処理を同期実行する。"""

    def submit(self, task: Callable[[], None]) -> Future[None]:
        """登録されたタスクを即時実行し、完了Futureを返す。"""
        future: Future[None] = Future()
        try:
            task()
        except Exception as exc:
            future.set_exception(exc)
        else:
            future.set_result(None)
        return future


@dataclass(slots=True)
class RecordingApplicationCodexRunner:
    """既定DIテスト用CodexRunner。"""

    generation_result: InfrastructureCodexRunResult
    validation_result: InfrastructureCodexRunResult
    generation_requests: list[CodexRunRequest] = field(default_factory=list)
    validation_requests: list[CodexRunRequest] = field(default_factory=list)
    cancel_requests: list[UUID] = field(default_factory=list)

    def run_generation(self, request: CodexRunRequest) -> InfrastructureCodexRunResult:
        """生成要求を記録して固定結果を返す。"""
        self.generation_requests.append(request)
        for event in self.generation_result.events:
            if request.on_event is not None:
                request.on_event(event)
        return self.generation_result

    def run_validation(self, request: CodexRunRequest) -> InfrastructureCodexRunResult:
        """検証要求を記録して固定結果を返す。"""
        self.validation_requests.append(request)
        for event in self.validation_result.events:
            if request.on_event is not None:
                request.on_event(event)
        return self.validation_result

    def cancel(self, run_id: UUID, trace_id: str) -> CancelResult:
        """キャンセル要求を記録する。"""
        _ = trace_id
        self.cancel_requests.append(run_id)
        return CancelRequestResult.SENT


def _make_client(tmp_path: Path) -> TestClient:
    client, _repository = _make_client_with_repository(tmp_path)
    return client


def _make_client_with_repository(
    tmp_path: Path,
) -> tuple[TestClient, InMemoryChatRepository]:
    repository = InMemoryChatRepository(
        now_values=(
            datetime(2026, 5, 9, 10, 0, tzinfo=UTC),
            datetime(2026, 5, 9, 10, 1, tzinfo=UTC),
            datetime(2026, 5, 9, 10, 2, tzinfo=UTC),
        )
    )
    app = create_app(
        config=_make_config(tmp_path),
        repository=repository,
        run_dispatcher=None,
    )
    return TestClient(app), repository


def _make_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        app=AppRuntimeConfig(timezone=ZoneInfo("Asia/Tokyo")),
        ui=UiConfig(
            welcome_message="ようこそ",
            input_suggestions=("要約してください",),
        ),
        datasource_dir=tmp_path / "readonly",
        generator=GeneratorConfig(
            max_retries=2,
            home=tmp_path / "codex/.codex",
            workdir=tmp_path / "codex/sessions",
            output_schema=tmp_path
            / "codex/output_json_schema/pdf-reference-schema.json",
            saved_artifacts_dir=tmp_path / "codex/saved_artifacts",
        ),
        validator=ValidatorConfig(
            max_retries=3,
            home=tmp_path / "codex/.codex_validator",
            workdir=tmp_path / "codex/sessions_validator",
            output_schema=tmp_path / "codex/output_json_schema/validator_schema.json",
        ),
        database=DatabaseConfig(
            url="postgresql+psycopg://user:password@127.0.0.1:5432/db"
        ),
        server=ServerConfig(timeout_seconds=300),
        trace_log=TraceLogConfig(
            dir=tmp_path / "logs/trace",
            retention_days=90,
            max_files_per_day=1000,
        ),
    )


@dataclass(frozen=True, slots=True)
class FixedClock:
    """テスト用に固定時刻を返す時計。"""

    now_value: datetime

    def now(self) -> datetime:
        """UTC基準の現在時刻を返す。"""
        return self.now_utc()

    def now_utc(self) -> datetime:
        """UTC基準の現在時刻を返す。"""
        return self.now_value.astimezone(UTC)

    def now_app_timezone(self) -> datetime:
        """アプリタイムゾーン基準の現在時刻を返す。"""
        return self.now_utc().astimezone(ZoneInfo("Asia/Tokyo"))


def _trace_records(tmp_path: Path) -> list[dict[str, str]]:
    log_files = sorted((tmp_path / "logs/trace").glob("*/*.yaml"))
    records: list[dict[str, str]] = []
    for log_file in log_files:
        loaded = yaml.safe_load(log_file.read_text(encoding="utf-8"))
        assert isinstance(loaded, dict)
        records.append({str(key): str(value) for key, value in loaded.items()})
    return records


def _trace_event_names(tmp_path: Path) -> list[str]:
    return [
        f"{record['event_name']}:{record['stage']}"
        for record in _trace_records(tmp_path)
    ]


def _write_pdf(path: Path, *, page_count: int) -> None:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=72, height=72)
    with path.open("wb") as pdf_file:
        writer.write(pdf_file)

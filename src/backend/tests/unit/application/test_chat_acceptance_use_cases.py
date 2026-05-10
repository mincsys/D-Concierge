from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest

from backend.application.chat.append_chat_run import AppendChatRunUseCase
from backend.application.chat.start_chat import StartChatUseCase
from backend.application.ports.runtime.dto import DispatchResult
from backend.shared.errors import AppError, ErrorClass
from backend.tests.support.memory_repository import InMemoryChatRepository


def test_start_chat_use_case_accepts_first_run_and_registers_dispatcher() -> None:
    """観点：StartChatUseCase。確認：新規チャットと初回runを受付し、dispatcherへ登録する。"""
    repository = InMemoryChatRepository()
    dispatcher = RecordingDispatcher()
    usecase = StartChatUseCase(repository=repository, run_dispatcher=dispatcher)

    result = usecase.execute("  資料を要約してください  ", trace_id="trace-101")

    assert result.state == "受付"
    assert result.sse_url == f"/api/chats/{result.chat_id}/runs/{result.run_id}/sse"
    assert dispatcher.registered == [(result.chat_id, result.run_id)]
    detail = repository.get_chat_detail(result.chat_id)
    assert detail.runs[0].user_instruction == "資料を要約してください"


def test_start_chat_use_case_rejects_blank_instruction_without_dispatch() -> None:
    """観点：StartChatUseCase。確認：空白だけの初回指示を入力不正として拒否する。"""
    repository = InMemoryChatRepository()
    dispatcher = RecordingDispatcher()
    usecase = StartChatUseCase(repository=repository, run_dispatcher=dispatcher)

    with pytest.raises(AppError) as error_info:
        usecase.execute("   ", trace_id="trace-102")

    assert error_info.value.error_class is ErrorClass.INPUT
    assert dispatcher.registered == []
    assert repository.list_histories() == ()


def test_start_chat_use_case_marks_run_error_when_dispatcher_fails() -> None:
    """観点：StartChatUseCase。確認：dispatcher登録失敗時は受付runをエラーに更新する。"""
    repository = InMemoryChatRepository()
    dispatcher = FailingDispatcher()
    usecase = StartChatUseCase(repository=repository, run_dispatcher=dispatcher)

    with pytest.raises(AppError) as error_info:
        usecase.execute("資料を要約してください", trace_id="trace-103")

    assert error_info.value.error_class is ErrorClass.SYSTEM
    assert dispatcher.registered_run_id is not None
    detail = repository.get_chat_detail(dispatcher.registered_chat_id)
    assert detail.runs[0].run_id == dispatcher.registered_run_id
    assert detail.runs[0].state == "エラー"
    assert detail.runs[0].user_message == "チャット実行処理を開始できませんでした。"


def test_append_chat_run_use_case_accepts_after_terminal_run() -> None:
    """観点：AppendChatRunUseCase。確認：終端済みrunだけのチャットへ継続runを追加する。"""
    repository = InMemoryChatRepository()
    first = repository.create_chat_with_first_run("初回")
    repository.set_run_state(first.chat_id, first.run_id, "完了")
    dispatcher = RecordingDispatcher()
    usecase = AppendChatRunUseCase(repository=repository, run_dispatcher=dispatcher)

    result = usecase.execute(
        chat_id=first.chat_id,
        user_instruction="追加で表にしてください",
        trace_id="trace-104",
    )

    assert result.chat_id == first.chat_id
    assert result.state == "受付"
    assert dispatcher.registered == [(first.chat_id, result.run_id)]
    detail = repository.get_chat_detail(first.chat_id)
    assert [run.user_instruction for run in detail.runs] == [
        "初回",
        "追加で表にしてください",
    ]


def test_append_chat_run_use_case_rejects_missing_chat_and_unfinished_run() -> None:
    """観点：AppendChatRunUseCase。確認：対象なしと未完了runありを設計どおり拒否する。"""
    repository = InMemoryChatRepository()
    dispatcher = RecordingDispatcher()
    usecase = AppendChatRunUseCase(repository=repository, run_dispatcher=dispatcher)

    with pytest.raises(AppError) as missing_error:
        usecase.execute(
            chat_id=uuid4(),
            user_instruction="追加",
            trace_id="trace-105",
        )
    first = repository.create_chat_with_first_run("初回")
    with pytest.raises(AppError) as conflict_error:
        usecase.execute(
            chat_id=first.chat_id,
            user_instruction="追加",
            trace_id="trace-106",
        )

    assert missing_error.value.error_class is ErrorClass.NOT_FOUND
    assert conflict_error.value.error_class is ErrorClass.CONFLICT
    assert dispatcher.registered == []


def test_append_chat_run_use_case_marks_run_error_when_dispatcher_fails() -> None:
    """観点：AppendChatRunUseCase。確認：dispatcher登録失敗時は追加runをエラーに更新する。"""
    repository = InMemoryChatRepository()
    first = repository.create_chat_with_first_run("初回")
    repository.set_run_state(first.chat_id, first.run_id, "完了")
    dispatcher = FailingDispatcher()
    usecase = AppendChatRunUseCase(repository=repository, run_dispatcher=dispatcher)

    with pytest.raises(AppError) as error_info:
        usecase.execute(
            chat_id=first.chat_id,
            user_instruction="追加",
            trace_id="trace-107",
        )

    assert error_info.value.error_class is ErrorClass.SYSTEM
    assert dispatcher.registered_run_id is not None
    detail = repository.get_chat_detail(first.chat_id)
    appended_run = detail.runs[-1]
    assert appended_run.run_id == dispatcher.registered_run_id
    assert appended_run.state == "エラー"
    assert appended_run.user_message == "チャット実行処理を開始できませんでした。"


@dataclass(slots=True)
class RecordingDispatcher:
    registered: list[tuple[UUID, UUID]] = field(default_factory=list)

    def register(self, chat_id: UUID, run_id: UUID) -> DispatchResult:
        self.registered.append((chat_id, run_id))
        return DispatchResult(status="registered")


@dataclass(slots=True)
class FailingDispatcher:
    registered_chat_id: UUID = UUID("00000000-0000-0000-0000-000000000000")
    registered_run_id: UUID | None = None

    def register(self, chat_id: UUID, run_id: UUID) -> DispatchResult:
        self.registered_chat_id = chat_id
        self.registered_run_id = run_id
        return DispatchResult(status="failed", failure_reason="executor closed")

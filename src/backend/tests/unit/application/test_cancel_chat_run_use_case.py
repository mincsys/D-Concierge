from dataclasses import dataclass, field
from uuid import UUID

import pytest

from backend.application.execution.cancel_chat_run import (
    CancelChatRunUseCase,
)
from backend.application.execution.execute_chat_run import RunEvent
from backend.application.ports.codex.dto import CancelRequestResult
from backend.domain.execution.run_state_policy import RunState
from backend.shared.errors import AppError, ErrorClass
from backend.tests.support.memory_repository import InMemoryChatRepository


def test_cancel_chat_run_use_case_completes_accepted_run_without_cancel_request() -> (
    None
):
    """観点：CancelChatRunUseCase。確認：受付runは終了要求なしでキャンセル済みに終端する。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("初回")
    requester = RecordingCancelRequester()
    publisher = RecordingPublisher()
    usecase = CancelChatRunUseCase(
        repository=repository,
        cancel_requester=requester,
        event_publisher=publisher,
    )

    result = usecase.request_cancel(
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
        trace_id="trace-201",
    )

    assert result.run_id == accepted.run_id
    assert result.state == "キャンセル要求中"
    assert result.user_message == "処理をキャンセルしています。"
    assert requester.requested == []
    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state == "キャンセル済み"
    assert detail.runs[0].user_message == "処理をキャンセルしました。"
    assert [event.event for event in publisher.events] == ["state", "canceled"]
    assert publisher.events[-1].state == "キャンセル済み"


def test_cancel_chat_run_use_case_rejects_terminal_run() -> None:
    """観点：CancelChatRunUseCase。確認：終端済みrunへのキャンセルを競合として扱う。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("初回")
    repository.set_run_state(accepted.chat_id, accepted.run_id, "完了")
    requester = RecordingCancelRequester()
    usecase = CancelChatRunUseCase(repository=repository, cancel_requester=requester)

    with pytest.raises(AppError) as error_info:
        usecase.request_cancel(
            chat_id=accepted.chat_id,
            run_id=accepted.run_id,
            trace_id="trace-202",
        )

    assert error_info.value.error_class is ErrorClass.CONFLICT
    assert requester.requested == []


def test_cancel_chat_run_use_case_rejects_stale_state_update() -> None:
    """観点：キャンセル競合。

    確認：状態取得後に条件付き更新が不成立になった場合は競合にする。
    """
    usecase = CancelChatRunUseCase(repository=StaleCancelRepository())

    with pytest.raises(AppError) as error_info:
        usecase.request_cancel(
            chat_id=UUID("00000000-0000-0000-0000-000000000901"),
            run_id=UUID("00000000-0000-0000-0000-000000000902"),
            trace_id="trace-205",
        )

    assert error_info.value.error_class is ErrorClass.CONFLICT


def test_cancel_chat_run_use_case_allows_missing_event_publisher() -> None:
    """観点：CancelChatRunUseCase。確認：イベント発行先未設定でもキャンセルを完了する。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("初回")
    usecase = CancelChatRunUseCase(repository=repository)

    result = usecase.request_cancel(
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
        trace_id="trace-203",
    )

    assert result.run_id == accepted.run_id
    assert repository.get_chat_detail(accepted.chat_id).runs[0].state == (
        "キャンセル済み"
    )


def test_cancel_chat_run_use_case_requests_cancel_for_running_run() -> None:
    """観点：二段階キャンセル。

    確認：実行中runで終了要求送信済みの場合、キャンセル要求中のまま実行処理側の終端を待つ。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("初回")
    repository.set_run_state(accepted.chat_id, accepted.run_id, "実行中")
    requester = RecordingCancelRequester()
    publisher = RecordingPublisher()
    usecase = CancelChatRunUseCase(
        repository=repository,
        cancel_requester=requester,
        event_publisher=publisher,
    )

    usecase.request_cancel(
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
        trace_id="trace-204",
    )

    assert requester.requested == [accepted.run_id]
    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state == "キャンセル要求中"
    assert detail.runs[0].user_message == "処理をキャンセルしています。"
    assert [event.event for event in publisher.events] == ["state"]


def test_cancel_chat_run_use_case_requests_cancel_for_validating_run() -> None:
    """観点：検証中キャンセル。

    確認：検証中runで終了要求送信済みの場合もキャンセル要求中のまま実行処理側の終端を待つ。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("初回")
    repository.set_run_state(accepted.chat_id, accepted.run_id, "検証中")
    requester = RecordingCancelRequester()
    publisher = RecordingPublisher()
    usecase = CancelChatRunUseCase(
        repository=repository,
        cancel_requester=requester,
        event_publisher=publisher,
    )

    usecase.request_cancel(
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
        trace_id="trace-208",
    )

    assert requester.requested == [accepted.run_id]
    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state == "キャンセル要求中"
    assert [event.event for event in publisher.events] == ["state"]


def test_cancel_chat_run_use_case_completes_cancel_when_process_already_exited() -> (
    None
):
    """観点：二段階キャンセル。確認：プロセス終了済みならキャンセル済みへ整合する。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("初回")
    repository.set_run_state(accepted.chat_id, accepted.run_id, "検証中")
    requester = RecordingCancelRequester(result="already_exited")
    publisher = RecordingPublisher()
    usecase = CancelChatRunUseCase(
        repository=repository,
        cancel_requester=requester,
        event_publisher=publisher,
    )

    usecase.request_cancel(
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
        trace_id="trace-205",
    )

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state == "キャンセル済み"
    assert [event.event for event in publisher.events] == ["state", "canceled"]


def test_cancel_chat_run_use_case_completes_running_run_without_cancel_requester() -> (
    None
):
    """観点：終了要求境界なし。

    確認：実行中runで終了要求境界がない場合はnot_registered相当としてキャンセル済みに整合する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("初回")
    repository.set_run_state(accepted.chat_id, accepted.run_id, "実行中")
    publisher = RecordingPublisher()
    usecase = CancelChatRunUseCase(
        repository=repository,
        event_publisher=publisher,
    )

    usecase.request_cancel(
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
        trace_id="trace-206",
    )

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state == "キャンセル済み"
    assert [event.event for event in publisher.events] == ["state", "canceled"]


def test_cancel_chat_run_use_case_ignores_stale_cancel_completion() -> None:
    """観点：キャンセル済み確定の競合。

    確認：キャンセル要求中への更新後に終端確定が不成立でも例外にせず状態イベントだけ返す。
    """
    repository = StaleCompletionRepository()
    publisher = RecordingPublisher()
    usecase = CancelChatRunUseCase(
        repository=repository,
        event_publisher=publisher,
    )

    result = usecase.request_cancel(
        chat_id=UUID("00000000-0000-0000-0000-000000000903"),
        run_id=UUID("00000000-0000-0000-0000-000000000904"),
        trace_id="trace-207",
    )

    assert result.state == "キャンセル要求中"
    assert [event.event for event in publisher.events] == ["state"]
    assert repository.update_calls == 2


@dataclass(slots=True)
class RecordingCancelRequester:
    requested: list[UUID] = field(default_factory=list)
    result: CancelRequestResult = "sent"

    def request_cancel(self, run_id: UUID) -> CancelRequestResult:
        self.requested.append(run_id)
        return self.result


@dataclass(slots=True)
class RecordingPublisher:
    events: list[RunEvent] = field(default_factory=list)

    def publish(self, event: RunEvent) -> None:
        self.events.append(event)


class StaleCancelRepository:
    """条件付き更新だけ不成立にするテスト用Repository。"""

    def get_run_state(self, chat_id: UUID, run_id: UUID) -> RunState:
        """キャンセル可能状態を返す。"""
        _ = (chat_id, run_id)
        return "実行中"

    def cancel_run(self, chat_id: UUID, run_id: UUID) -> None:
        """互換用メソッド。"""
        _ = (chat_id, run_id)

    def update_run_state_if_current(
        self,
        chat_id: UUID,
        run_id: UUID,
        expected_states: tuple[RunState, ...],
        state: RunState,
        user_message: str | None = None,
    ) -> bool:
        """常に状態競合として扱う。"""
        _ = (chat_id, run_id, expected_states, state, user_message)
        return False


@dataclass(slots=True)
class StaleCompletionRepository:
    """キャンセル済み確定だけ不成立にするテスト用Repository。"""

    update_calls: int = 0

    def get_run_state(self, chat_id: UUID, run_id: UUID) -> RunState:
        """受付状態を返す。"""
        _ = (chat_id, run_id)
        return "受付"

    def cancel_run(self, chat_id: UUID, run_id: UUID) -> None:
        """互換用メソッド。"""
        _ = (chat_id, run_id)

    def update_run_state_if_current(
        self,
        chat_id: UUID,
        run_id: UUID,
        expected_states: tuple[RunState, ...],
        state: RunState,
        user_message: str | None = None,
    ) -> bool:
        """キャンセル要求中だけ成立させ、キャンセル済み確定は不成立にする。"""
        _ = (chat_id, run_id, expected_states, user_message)
        self.update_calls += 1
        return state == "キャンセル要求中"

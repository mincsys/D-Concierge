from __future__ import annotations

import pytest

from backend.application.account.errors import FieldValidationError
from backend.domain.execution.run_state import RunState
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.shared.tracing.trace_id import TraceId
from backend.tests.support.chat import (
    CHAT_ID_VALUE,
    NEXT_RUN_ID_VALUE,
    RUN_ID_VALUE,
    TRACE_ID_VALUE,
    DispatchResultRecord,
    FakeChatRepository,
    FakeRunExecutionDispatcher,
    FakeTransactionManager,
    FixedClock,
    FixedUuidGenerator,
    fixed_chat_detail_record,
)


def test_start_chat_accepts_first_instruction_and_dispatches_run() -> None:
    """
    観点：新規チャット開始ユースケースが初回指示、チャット、run、dispatcher登録を調停すること
    確認：指示本文を正規化してタイトルを生成し、accepted runを保存した後、
    trace_id付きでバックグラウンド登録し、SSE URLを含む受付結果を返すこと
    """
    from backend.application.chat.start_chat import (
        StartChatCommand,
        StartChatUseCase,
    )

    repository = FakeChatRepository()
    dispatcher = FakeRunExecutionDispatcher()
    transaction = FakeTransactionManager()
    use_case = StartChatUseCase(
        repository=repository,
        transaction_manager=transaction,
        dispatcher=dispatcher,
        id_generator=FixedUuidGenerator(),
        clock=FixedClock(),
    )

    result = use_case.execute(
        StartChatCommand(
            authenticated_user_id="user-001",
            user_instruction="  最初の依頼\n  詳細を整理してください  ",
            trace_id=TraceId(TRACE_ID_VALUE),
        )
    )

    assert result.chat_id == CHAT_ID_VALUE
    assert result.run_id == RUN_ID_VALUE
    assert result.state == RunState.ACCEPTED.value
    assert result.sse_url == f"/api/chats/{CHAT_ID_VALUE}/runs/{RUN_ID_VALUE}/sse"
    assert transaction.commit_count == 1
    assert repository.saved_first_runs[0].title == "最初の依頼 詳細を整理してください"
    assert repository.saved_first_runs[0].user_instruction == (
        "最初の依頼\n  詳細を整理してください"
    )
    assert dispatcher.registrations == [
        (CHAT_ID_VALUE, RUN_ID_VALUE, TRACE_ID_VALUE),
    ]


@pytest.mark.parametrize("invalid_instruction", ("", "   \n\t  "))
def test_start_chat_rejects_blank_instruction_without_side_effects(
    invalid_instruction: str,
) -> None:
    """
    観点：新規チャット開始ユースケースが空白だけの指示を入力不正として保存前に拒否すること
    確認：user_instructionのfield_errorsを返し、ID発番、DB保存、dispatcher登録を行わないこと
    """
    from backend.application.chat.start_chat import (
        StartChatCommand,
        StartChatUseCase,
    )

    repository = FakeChatRepository()
    dispatcher = FakeRunExecutionDispatcher()
    id_generator = FixedUuidGenerator()
    use_case = StartChatUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        dispatcher=dispatcher,
        id_generator=id_generator,
        clock=FixedClock(),
    )

    with pytest.raises(FieldValidationError) as raised:
        use_case.execute(
            StartChatCommand(
                authenticated_user_id="user-001",
                user_instruction=invalid_instruction,
                trace_id=TraceId(TRACE_ID_VALUE),
            )
        )

    assert "user_instruction" in raised.value.field_errors
    assert repository.saved_first_runs == []
    assert dispatcher.registrations == []
    assert id_generator.values[0] == CHAT_ID_VALUE


def test_start_chat_marks_saved_run_error_when_dispatcher_failed() -> None:
    """
    観点：新規チャット開始ユースケースがdispatcher登録失敗をaccepted放置にしないこと
    確認：保存済みrunをerrorへ更新してからSYSTEM分類のAppErrorを送出し、
    受付成功レスポンスを返さないこと
    """
    from backend.application.chat.start_chat import (
        StartChatCommand,
        StartChatUseCase,
    )

    repository = FakeChatRepository()
    dispatcher = FakeRunExecutionDispatcher(
        next_result=DispatchResultRecord(
            status="failed",
            diagnostic_message="dispatcher unavailable",
        ),
    )
    use_case = StartChatUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        dispatcher=dispatcher,
        id_generator=FixedUuidGenerator(),
        clock=FixedClock(),
    )

    with pytest.raises(AppError) as raised:
        use_case.execute(
            StartChatCommand(
                authenticated_user_id="user-001",
                user_instruction="初回指示",
                trace_id=TraceId(TRACE_ID_VALUE),
            )
        )

    assert raised.value.error_type is ErrorType.SYSTEM
    assert repository.run_errors[0].run_id == RUN_ID_VALUE
    assert "dispatcher unavailable" in repository.run_errors[0].diagnostic_message


def test_append_chat_run_accepts_existing_active_chat_without_new_session() -> None:
    """
    観点：継続指示受付ユースケースが既存チャットへ新しいrunだけを追加すること
    確認：対象チャットの所有者と未完了runなしを満たす場合、session_idを採番せず、
    追加runをacceptedで保存し、対象runのSSE URLを返すこと
    """
    from backend.application.chat.append_chat_run import (
        AppendChatRunCommand,
        AppendChatRunUseCase,
    )

    repository = FakeChatRepository(
        details={("user-001", CHAT_ID_VALUE): fixed_chat_detail_record()},
    )
    dispatcher = FakeRunExecutionDispatcher()
    transaction = FakeTransactionManager()
    use_case = AppendChatRunUseCase(
        repository=repository,
        transaction_manager=transaction,
        dispatcher=dispatcher,
        id_generator=FixedUuidGenerator(values=[NEXT_RUN_ID_VALUE]),
        clock=FixedClock(),
    )

    result = use_case.execute(
        AppendChatRunCommand(
            authenticated_user_id="user-001",
            chat_id=CHAT_ID_VALUE,
            user_instruction=" 継続の依頼 ",
            trace_id=TraceId(TRACE_ID_VALUE),
        )
    )

    assert result.chat_id == CHAT_ID_VALUE
    assert result.run_id == NEXT_RUN_ID_VALUE
    assert result.state == RunState.ACCEPTED.value
    assert result.sse_url == f"/api/chats/{CHAT_ID_VALUE}/runs/{NEXT_RUN_ID_VALUE}/sse"
    assert repository.saved_append_runs[0].user_instruction == "継続の依頼"
    assert transaction.commit_count == 1
    assert dispatcher.registrations == [
        (CHAT_ID_VALUE, NEXT_RUN_ID_VALUE, TRACE_ID_VALUE),
    ]


@pytest.mark.parametrize("invalid_instruction", ("", "   \n\t  "))
def test_append_chat_run_rejects_blank_instruction_without_side_effects(
    invalid_instruction: str,
) -> None:
    """
    観点：継続指示受付ユースケースが空白だけの継続指示を保存前に拒否すること
    確認：user_instructionのfield_errorsを返し、ID発番、run保存、
    dispatcher登録を行わないこと
    """
    from backend.application.chat.append_chat_run import (
        AppendChatRunCommand,
        AppendChatRunUseCase,
    )

    repository = FakeChatRepository(
        details={("user-001", CHAT_ID_VALUE): fixed_chat_detail_record()},
    )
    dispatcher = FakeRunExecutionDispatcher()
    id_generator = FixedUuidGenerator(values=[NEXT_RUN_ID_VALUE])
    use_case = AppendChatRunUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        dispatcher=dispatcher,
        id_generator=id_generator,
        clock=FixedClock(),
    )

    with pytest.raises(FieldValidationError) as raised:
        use_case.execute(
            AppendChatRunCommand(
                authenticated_user_id="user-001",
                chat_id=CHAT_ID_VALUE,
                user_instruction=invalid_instruction,
                trace_id=TraceId(TRACE_ID_VALUE),
            )
        )

    assert "user_instruction" in raised.value.field_errors
    assert repository.saved_append_runs == []
    assert dispatcher.registrations == []
    assert id_generator.values == [NEXT_RUN_ID_VALUE]


@pytest.mark.parametrize(
    ("repository", "expected_error_type"),
    (
        (FakeChatRepository(), ErrorType.NOT_FOUND),
        (
            FakeChatRepository(
                details={("user-001", CHAT_ID_VALUE): fixed_chat_detail_record()},
                conflict_chat_ids={CHAT_ID_VALUE},
            ),
            ErrorType.CONFLICT,
        ),
    ),
)
def test_append_chat_run_rejects_not_found_or_unfinished_run_without_save(
    repository: FakeChatRepository,
    expected_error_type: ErrorType,
) -> None:
    """
    観点：継続指示受付ユースケースが対象なしと未完了run競合を保存前に拒否すること
    確認：NOT_FOUNDまたはCONFLICTのAppErrorとなり、新しいrun保存とdispatcher登録を行わないこと
    """
    from backend.application.chat.append_chat_run import (
        AppendChatRunCommand,
        AppendChatRunUseCase,
    )

    dispatcher = FakeRunExecutionDispatcher()
    use_case = AppendChatRunUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        dispatcher=dispatcher,
        id_generator=FixedUuidGenerator(values=[NEXT_RUN_ID_VALUE]),
        clock=FixedClock(),
    )

    with pytest.raises(AppError) as raised:
        use_case.execute(
            AppendChatRunCommand(
                authenticated_user_id="user-001",
                chat_id=CHAT_ID_VALUE,
                user_instruction="継続の依頼",
                trace_id=TraceId(TRACE_ID_VALUE),
            )
        )

    assert raised.value.error_type is expected_error_type
    assert repository.saved_append_runs == []
    assert dispatcher.registrations == []


def test_append_chat_run_rejects_deleting_chat_without_save() -> None:
    """
    観点：継続指示受付ユースケースが削除中チャットへの受付を拒否すること
    確認：CONFLICTのAppErrorとなり、新しいrun保存とdispatcher登録を行わないこと
    """
    from backend.application.chat.append_chat_run import (
        AppendChatRunCommand,
        AppendChatRunUseCase,
    )

    repository = FakeChatRepository(
        details={("user-001", CHAT_ID_VALUE): fixed_chat_detail_record()},
        deleting_chat_ids={CHAT_ID_VALUE},
    )
    dispatcher = FakeRunExecutionDispatcher()
    use_case = AppendChatRunUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        dispatcher=dispatcher,
        id_generator=FixedUuidGenerator(values=[NEXT_RUN_ID_VALUE]),
        clock=FixedClock(),
    )

    with pytest.raises(AppError) as raised:
        use_case.execute(
            AppendChatRunCommand(
                authenticated_user_id="user-001",
                chat_id=CHAT_ID_VALUE,
                user_instruction="継続の依頼",
                trace_id=TraceId(TRACE_ID_VALUE),
            )
        )

    assert raised.value.error_type is ErrorType.CONFLICT
    assert repository.saved_append_runs == []
    assert dispatcher.registrations == []


def test_append_chat_run_marks_saved_run_error_when_dispatcher_failed() -> None:
    """
    観点：継続指示受付ユースケースがdispatcher登録失敗をaccepted放置にしないこと
    確認：追加済みrunをerrorへ更新してからSYSTEM分類のAppErrorを送出し、
    受付成功レスポンスを返さないこと
    """
    from backend.application.chat.append_chat_run import (
        AppendChatRunCommand,
        AppendChatRunUseCase,
    )

    repository = FakeChatRepository(
        details={("user-001", CHAT_ID_VALUE): fixed_chat_detail_record()},
    )
    dispatcher = FakeRunExecutionDispatcher(
        next_result=DispatchResultRecord(
            status="failed",
            diagnostic_message="dispatcher unavailable",
        ),
    )
    use_case = AppendChatRunUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        dispatcher=dispatcher,
        id_generator=FixedUuidGenerator(values=[NEXT_RUN_ID_VALUE]),
        clock=FixedClock(),
    )

    with pytest.raises(AppError) as raised:
        use_case.execute(
            AppendChatRunCommand(
                authenticated_user_id="user-001",
                chat_id=CHAT_ID_VALUE,
                user_instruction="継続の依頼",
                trace_id=TraceId(TRACE_ID_VALUE),
            )
        )

    assert raised.value.error_type is ErrorType.SYSTEM
    assert repository.saved_append_runs[0].run_id == NEXT_RUN_ID_VALUE
    assert repository.run_errors[0].run_id == NEXT_RUN_ID_VALUE
    assert "dispatcher unavailable" in repository.run_errors[0].diagnostic_message
    assert dispatcher.registrations == [
        (CHAT_ID_VALUE, NEXT_RUN_ID_VALUE, TRACE_ID_VALUE),
    ]

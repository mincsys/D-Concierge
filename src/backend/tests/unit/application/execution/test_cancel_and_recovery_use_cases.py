from __future__ import annotations

from uuid import UUID

import pytest

from backend.application.execution.dto import CodexCancelStatus
from backend.domain.execution.run_state import RunState
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.shared.tracing.trace_id import TraceId
from backend.tests.support.chat import (
    CHAT_ID_VALUE,
    RUN_ID_VALUE,
    TRACE_ID_VALUE,
    FakeTransactionManager,
    FixedClock,
)
from backend.tests.support.execution import (
    CancelRunTargetRecord,
    FakeBackgroundExecutor,
    FakeCodexRunner,
    FakeExecutionRepository,
    FakeRunEventPublisher,
    accepted_cancel_target,
    recovery_run,
    running_cancel_target,
)


def test_cancel_accepted_run_finishes_without_codex_cancel() -> None:
    """
    観点：キャンセルユースケースがaccepted runを実行コンテナなしで終端できること
    確認：cancel_requestedを経由してcanceledへ更新し、CodexRunner.cancelを呼ばず、
    stateとcanceledのSSEイベントを発行すること
    """
    from backend.application.execution.cancel_chat_run import (
        CancelChatRunCommand,
        CancelChatRunUseCase,
    )

    repository = FakeExecutionRepository(
        cancel_targets={
            ("user-001", CHAT_ID_VALUE, RUN_ID_VALUE): accepted_cancel_target(),
        },
    )
    runner = FakeCodexRunner()
    publisher = FakeRunEventPublisher()
    use_case = CancelChatRunUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        codex_runner=runner,
        event_publisher=publisher,
        clock=FixedClock(),
    )

    result = use_case.execute(
        CancelChatRunCommand(
            authenticated_user_id="user-001",
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            trace_id=TraceId(TRACE_ID_VALUE),
        )
    )

    assert result.state == RunState.CANCELED.value
    assert result.user_message == "処理をキャンセルしました。"
    assert runner.cancel_requests == []
    assert [transition.next_state for transition in repository.transitions] == [
        RunState.CANCEL_REQUESTED.value,
        RunState.CANCELED.value,
    ]
    assert [(event.event_name, event.payload_state) for event in publisher.events] == [
        ("state", RunState.CANCEL_REQUESTED.value),
        ("canceled", RunState.CANCELED.value),
    ]


def test_cancel_running_run_requests_codex_stop_and_keeps_cancel_requested() -> None:
    """
    観点：キャンセルユースケースがrunning runの終了要求を実行基盤へ委譲すること
    確認：runをcancel_requestedへ更新し、CodexRunner.cancelへchat_id/run_id/trace_idを渡し、
    REST応答はキャンセル受付中の利用者向けメッセージになること
    """
    from backend.application.execution.cancel_chat_run import (
        CancelChatRunCommand,
        CancelChatRunUseCase,
    )

    repository = FakeExecutionRepository(
        cancel_targets={
            ("user-001", CHAT_ID_VALUE, RUN_ID_VALUE): running_cancel_target(),
        },
    )
    runner = FakeCodexRunner(next_cancel_result="sent")
    publisher = FakeRunEventPublisher()
    use_case = CancelChatRunUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        codex_runner=runner,
        event_publisher=publisher,
        clock=FixedClock(),
    )

    result = use_case.execute(
        CancelChatRunCommand(
            authenticated_user_id="user-001",
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            trace_id=TraceId(TRACE_ID_VALUE),
        )
    )

    assert result.state == RunState.CANCEL_REQUESTED.value
    assert result.user_message == "処理をキャンセルしています。"
    assert runner.cancel_requests[0].chat_id == CHAT_ID_VALUE
    assert runner.cancel_requests[0].run_id == RUN_ID_VALUE
    assert runner.cancel_requests[0].trace_id == TRACE_ID_VALUE
    assert repository.transitions[0].next_state == RunState.CANCEL_REQUESTED.value
    assert publisher.events[0].event_name == "state"


@pytest.mark.parametrize(
    "cancel_result",
    ("already_exited", "not_registered"),
)
def test_cancel_running_run_aligns_completed_runner_to_canceled(
    cancel_result: CodexCancelStatus,
) -> None:
    """
    観点：CodexRunnerが既に終了または未登録を返したrunning runの状態整合
    確認：回答採用前のrunはcancel_requestedを経由してcanceledへ終端し、
    stateとcanceledのSSEイベントを発行すること
    """
    from backend.application.execution.cancel_chat_run import (
        CancelChatRunCommand,
        CancelChatRunUseCase,
    )

    repository = FakeExecutionRepository(
        cancel_targets={
            ("user-001", CHAT_ID_VALUE, RUN_ID_VALUE): running_cancel_target(),
        },
    )
    runner = FakeCodexRunner(next_cancel_result=cancel_result)
    publisher = FakeRunEventPublisher()
    use_case = CancelChatRunUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        codex_runner=runner,
        event_publisher=publisher,
        clock=FixedClock(),
    )

    result = use_case.execute(
        CancelChatRunCommand(
            authenticated_user_id="user-001",
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            trace_id=TraceId(TRACE_ID_VALUE),
        )
    )

    assert result.state == RunState.CANCELED.value
    assert result.user_message == "処理をキャンセルしました。"
    assert runner.cancel_requests[0].run_id == RUN_ID_VALUE
    assert [transition.next_state for transition in repository.transitions] == [
        RunState.CANCEL_REQUESTED.value,
        RunState.CANCELED.value,
    ]
    assert [(event.event_name, event.payload_state) for event in publisher.events] == [
        ("state", RunState.CANCEL_REQUESTED.value),
        ("canceled", RunState.CANCELED.value),
    ]


def test_cancel_runner_already_stopped_detects_canceled_update_conflict() -> None:
    """
    観点：CodexRunner終了済み後のcanceled終端更新が競合した場合の扱い
    確認：cancel_requestedへの更新後、canceledへの条件付き更新が不成立なら
    CONFLICTとなり、canceledイベントを発行しないこと
    """
    from backend.application.execution.cancel_chat_run import (
        CancelChatRunCommand,
        CancelChatRunUseCase,
    )

    repository = FakeExecutionRepository(
        cancel_targets={
            ("user-001", CHAT_ID_VALUE, RUN_ID_VALUE): running_cancel_target(),
        },
        fail_next_states={RunState.CANCELED.value},
    )
    runner = FakeCodexRunner(next_cancel_result="already_exited")
    publisher = FakeRunEventPublisher()
    use_case = CancelChatRunUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        codex_runner=runner,
        event_publisher=publisher,
        clock=FixedClock(),
    )

    with pytest.raises(AppError) as raised:
        use_case.execute(
            CancelChatRunCommand(
                authenticated_user_id="user-001",
                chat_id=CHAT_ID_VALUE,
                run_id=RUN_ID_VALUE,
                trace_id=TraceId(TRACE_ID_VALUE),
            )
        )

    assert raised.value.error_type is ErrorType.CONFLICT
    assert [transition.next_state for transition in repository.transitions] == [
        RunState.CANCEL_REQUESTED.value,
        RunState.CANCELED.value,
    ]
    assert [(event.event_name, event.payload_state) for event in publisher.events] == [
        ("state", RunState.CANCEL_REQUESTED.value),
    ]


@pytest.mark.parametrize(
    "terminal_state",
    (
        RunState.COMPLETED,
        RunState.ERROR,
        RunState.TIMED_OUT,
        RunState.CANCELED,
        RunState.CANCEL_REQUESTED,
    ),
)
def test_cancel_rejects_uncancelable_run_without_side_effects(
    terminal_state: RunState,
) -> None:
    """
    観点：キャンセルユースケースがキャンセル不可状態を変更しないこと
    確認：終端済みまたはcancel_requestedではCONFLICTのAppErrorとなり、
    DB更新、CodexRunner.cancel、SSE配信を行わないこと
    """
    from backend.application.execution.cancel_chat_run import (
        CancelChatRunCommand,
        CancelChatRunUseCase,
    )

    repository = FakeExecutionRepository(
        cancel_targets={
            ("user-001", CHAT_ID_VALUE, RUN_ID_VALUE): CancelRunTargetRecord(
                user_id="user-001",
                chat_id=CHAT_ID_VALUE,
                run_id=RUN_ID_VALUE,
                state=terminal_state.value,
            ),
        },
    )
    runner = FakeCodexRunner()
    publisher = FakeRunEventPublisher()
    use_case = CancelChatRunUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        codex_runner=runner,
        event_publisher=publisher,
        clock=FixedClock(),
    )

    with pytest.raises(AppError) as raised:
        use_case.execute(
            CancelChatRunCommand(
                authenticated_user_id="user-001",
                chat_id=CHAT_ID_VALUE,
                run_id=RUN_ID_VALUE,
                trace_id=TraceId(TRACE_ID_VALUE),
            )
        )

    assert raised.value.error_type is ErrorType.CONFLICT
    assert repository.transitions == []
    assert runner.cancel_requests == []
    assert publisher.events == []


def test_cancel_rejects_missing_or_deleting_target_without_side_effects() -> None:
    """
    観点：キャンセルユースケースが対象なしと削除中チャットを更新前に拒否すること
    確認：NOT_FOUNDまたはCONFLICTのAppErrorとなり、DB更新、CodexRunner.cancel、
    SSE配信を行わないこと
    """
    from backend.application.execution.cancel_chat_run import (
        CancelChatRunCommand,
        CancelChatRunUseCase,
    )

    deleting_repository = FakeExecutionRepository(
        cancel_targets={
            ("user-001", CHAT_ID_VALUE, RUN_ID_VALUE): CancelRunTargetRecord(
                user_id="user-001",
                chat_id=CHAT_ID_VALUE,
                run_id=RUN_ID_VALUE,
                state=RunState.RUNNING.value,
                chat_state="deleting",
            ),
        },
    )
    scenarios = (
        (FakeExecutionRepository(), ErrorType.NOT_FOUND),
        (deleting_repository, ErrorType.CONFLICT),
    )

    for repository, expected_error_type in scenarios:
        runner = FakeCodexRunner()
        publisher = FakeRunEventPublisher()
        use_case = CancelChatRunUseCase(
            repository=repository,
            transaction_manager=FakeTransactionManager(),
            codex_runner=runner,
            event_publisher=publisher,
            clock=FixedClock(),
        )

        with pytest.raises(AppError) as raised:
            use_case.execute(
                CancelChatRunCommand(
                    authenticated_user_id="user-001",
                    chat_id=CHAT_ID_VALUE,
                    run_id=RUN_ID_VALUE,
                    trace_id=TraceId(TRACE_ID_VALUE),
                )
            )

        assert raised.value.error_type is expected_error_type
        assert repository.transitions == []
        assert runner.cancel_requests == []
        assert publisher.events == []


def test_cancel_rejects_state_update_conflict_without_later_side_effects() -> None:
    """
    観点：キャンセルユースケースが状態条件付き更新の競合を検知すること
    確認：更新不成立時はCONFLICTとなり、CodexRunner.cancelとSSE配信を行わないこと
    """
    from backend.application.execution.cancel_chat_run import (
        CancelChatRunCommand,
        CancelChatRunUseCase,
    )

    repository = FakeExecutionRepository(
        cancel_targets={
            ("user-001", CHAT_ID_VALUE, RUN_ID_VALUE): running_cancel_target(),
        },
        fail_update_run_ids={RUN_ID_VALUE},
    )
    runner = FakeCodexRunner()
    publisher = FakeRunEventPublisher()
    use_case = CancelChatRunUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        codex_runner=runner,
        event_publisher=publisher,
        clock=FixedClock(),
    )

    with pytest.raises(AppError) as raised:
        use_case.execute(
            CancelChatRunCommand(
                authenticated_user_id="user-001",
                chat_id=CHAT_ID_VALUE,
                run_id=RUN_ID_VALUE,
                trace_id=TraceId(TRACE_ID_VALUE),
            )
        )

    assert raised.value.error_type is ErrorType.CONFLICT
    assert len(repository.transitions) == 1
    assert runner.cancel_requests == []
    assert publisher.events == []


def test_recovery_registers_accepted_and_terminalizes_lost_runs() -> None:
    """
    観点：起動時実行回復ユースケースが未完了runを状態別に整合すること
    確認：acceptedはdispatcherへ再登録し、running/validatingはerror、
    cancel_requestedはcanceledへ更新して、終端済みrunを変更しないこと
    """
    from backend.application.execution.recover_unfinished_runs import (
        RecoverUnfinishedRunsCommand,
        RecoverUnfinishedRunsUseCase,
    )

    running_id = UUID("33333333-3333-7333-8333-333333333333")
    validating_id = UUID("44444444-4444-7444-8444-444444444444")
    cancel_requested_id = UUID("55555555-5555-7555-8555-555555555555")
    repository = FakeExecutionRepository(
        unfinished_runs=[
            recovery_run(RunState.ACCEPTED, RUN_ID_VALUE),
            recovery_run(RunState.RUNNING, running_id),
            recovery_run(RunState.VALIDATING, validating_id),
            recovery_run(RunState.CANCEL_REQUESTED, cancel_requested_id),
        ],
    )
    background = FakeBackgroundExecutor()
    use_case = RecoverUnfinishedRunsUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        background_executor=background,
        clock=FixedClock(),
    )

    result = use_case.execute(RecoverUnfinishedRunsCommand(trace_id=TRACE_ID_VALUE))

    assert result.accepted_registered == 1
    assert result.error_terminalized == 2
    assert result.canceled_terminalized == 1
    assert background.submitted_run_ids == [RUN_ID_VALUE]
    assert [transition.next_state for transition in repository.transitions] == [
        RunState.ERROR.value,
        RunState.ERROR.value,
        RunState.CANCELED.value,
    ]


def test_recovery_marks_accepted_error_when_dispatch_registration_fails() -> None:
    """
    観点：起動時実行回復ユースケースがaccepted runの再登録失敗を放置しないこと
    確認：dispatcher登録に失敗したaccepted runをerrorへ更新し、
    次回起動までacceptedのまま残さないこと
    """
    from backend.application.execution.recover_unfinished_runs import (
        RecoverUnfinishedRunsCommand,
        RecoverUnfinishedRunsUseCase,
    )

    repository = FakeExecutionRepository(
        unfinished_runs=[recovery_run(RunState.ACCEPTED, RUN_ID_VALUE)],
    )
    background = FakeBackgroundExecutor(fail_on_run_ids={RUN_ID_VALUE})
    use_case = RecoverUnfinishedRunsUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        background_executor=background,
        clock=FixedClock(),
    )

    result = use_case.execute(RecoverUnfinishedRunsCommand(trace_id=TRACE_ID_VALUE))

    assert result.accepted_registered == 0
    assert result.error_terminalized == 1
    assert repository.transitions[0].expected_state == RunState.ACCEPTED.value
    assert repository.transitions[0].next_state == RunState.ERROR.value


def test_recovery_ignores_state_update_conflicts() -> None:
    """
    観点：起動時実行回復が状態条件付き更新不成立を他処理との競合として扱うこと
    確認：accepted再登録失敗、running喪失、cancel_requested終端化の各更新が
    不成立でも件数を加算せず、処理全体は完了すること
    """
    from backend.application.execution.recover_unfinished_runs import (
        RecoverUnfinishedRunsCommand,
        RecoverUnfinishedRunsUseCase,
    )

    running_id = UUID("33333333-3333-7333-8333-333333333333")
    cancel_requested_id = UUID("55555555-5555-7555-8555-555555555555")
    repository = FakeExecutionRepository(
        unfinished_runs=[
            recovery_run(RunState.ACCEPTED, RUN_ID_VALUE),
            recovery_run(RunState.RUNNING, running_id),
            recovery_run(RunState.CANCEL_REQUESTED, cancel_requested_id),
        ],
        fail_update_run_ids={RUN_ID_VALUE, running_id, cancel_requested_id},
    )
    background = FakeBackgroundExecutor(fail_on_run_ids={RUN_ID_VALUE})
    use_case = RecoverUnfinishedRunsUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        background_executor=background,
        clock=FixedClock(),
    )

    result = use_case.execute(RecoverUnfinishedRunsCommand(trace_id=TRACE_ID_VALUE))

    assert result.accepted_registered == 0
    assert result.error_terminalized == 0
    assert result.canceled_terminalized == 0
    assert [transition.next_state for transition in repository.transitions] == [
        RunState.ERROR.value,
        RunState.ERROR.value,
        RunState.CANCELED.value,
    ]


def test_run_event_broker_unsubscribes_closed_subscription() -> None:
    """
    観点：SSEイベント配信IFが切断済み購読者へ後続イベントを送らないこと
    確認：unsubscribe後にpublishしても対象subscriptionのpollはNoneのままになること
    """
    from backend.application.execution.run_event_broker import (
        RunEvent,
        RunEventBroker,
    )

    broker = RunEventBroker()
    subscription = broker.subscribe(RUN_ID_VALUE)

    broker.unsubscribe(subscription)
    broker.publish(RunEvent.message(run_id=RUN_ID_VALUE, text="切断後のイベント"))

    assert subscription.poll_event() is None


def test_run_event_broker_unsubscribe_keeps_remaining_subscription() -> None:
    """
    観点：SSEイベント配信IFの購読解除が重複解除と残購読者を安全に扱うこと
    確認：同じsubscriptionの再解除は無害で、別subscriptionには後続イベントが届くこと
    """
    from backend.application.execution.run_event_broker import (
        RunEvent,
        RunEventBroker,
    )

    broker = RunEventBroker()
    first = broker.subscribe(RUN_ID_VALUE)
    second = broker.subscribe(RUN_ID_VALUE)

    broker.unsubscribe(first)
    broker.unsubscribe(first)
    broker.publish(RunEvent.message(run_id=RUN_ID_VALUE, text="残購読者へのイベント"))

    assert first.poll_event() is None
    assert second.poll_event() == RunEvent.message(
        run_id=RUN_ID_VALUE,
        text="残購読者へのイベント",
    )

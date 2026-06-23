from __future__ import annotations

from dataclasses import fields, is_dataclass


def test_chat_repository_port_exposes_f003_acceptance_and_history_methods() -> None:
    """
    観点：ChatRepository IFがF003のチャット受付と履歴再表示の永続化境界を表すこと
    確認：新規チャット、継続run、受付runエラー化、履歴一覧、履歴詳細に必要な
    公開メソッドがProtocolに定義されていること
    """
    from backend.application.ports.database.interface import ChatRepositoryPort

    expected_method_names = (
        "create_chat_with_first_run",
        "append_run",
        "mark_run_error",
        "list_histories",
        "get_chat_detail",
    )

    for method_name in expected_method_names:
        assert hasattr(ChatRepositoryPort, method_name), method_name


def test_chat_repository_dtos_expose_f003_history_fields() -> None:
    """
    観点：Repository DTOが履歴一覧と履歴詳細に必要な保存済み表示情報をORMなしで返すこと
    確認：AcceptedRun、HistoryItem、ChatRunData、ChatDetail、AnswerData、
    DisplayReferenceDataがdataclassであり、run状態、指示、中間メッセージ、
    回答ブロック、参照元URL生成に必要な項目を保持すること
    """
    from backend.application.ports.database.dto import (
        AcceptedRun,
        AnswerData,
        ChatDetail,
        ChatRunData,
        DisplayReferenceData,
        HistoryItem,
        IntermediateMessageData,
    )

    dto_classes = (
        AcceptedRun,
        HistoryItem,
        ChatRunData,
        IntermediateMessageData,
        ChatDetail,
        AnswerData,
        DisplayReferenceData,
    )

    assert all(is_dataclass(dto_class) for dto_class in dto_classes)
    assert {"chat_id", "run_id", "state", "started_at"} <= _dataclass_field_names(
        AcceptedRun,
    )
    assert {"chat_id", "title", "latest_run_id", "latest_state", "updated_at"} <= (
        _dataclass_field_names(HistoryItem)
    )
    assert {
        "run_id",
        "state",
        "user_instruction",
        "intermediate_messages",
        "answer",
        "user_message",
    } <= _dataclass_field_names(ChatRunData)
    assert {"chat_id", "title", "runs"} <= _dataclass_field_names(ChatDetail)
    reference_fields = {
        "reference_id",
        "source_type",
        "label",
        "path",
        "page_start",
        "page_end",
    }
    assert reference_fields <= _dataclass_field_names(DisplayReferenceData)


def test_run_execution_dispatcher_port_exposes_f003_registration_result() -> None:
    """
    観点：チャット受付が実行本体をRunExecutionDispatcher IFへ委譲すること
    確認：RunExecutionDispatcherPort、RunDispatchResult、RunDispatchStatusが
    registered、already_registered、failedを表すruntime portとして定義されること
    """
    from backend.application.ports.runtime.interface import (
        RunDispatchResult,
        RunDispatchStatus,
        RunExecutionDispatcherPort,
    )

    assert hasattr(RunExecutionDispatcherPort, "register")
    assert is_dataclass(RunDispatchResult)
    assert tuple(status.value for status in RunDispatchStatus) == (
        "registered",
        "already_registered",
        "failed",
    )


def test_f004_runtime_ports_expose_dispatch_and_background_boundaries() -> None:
    """
    観点：RunExecutionDispatcher IFがF004の多重登録防止と回復境界を持つこと
    確認：ChatRunExecutorPortとBackgroundExecutorPortが定義され、
    dispatcherはregisterだけでHTTP応答を生成しない境界として維持されること
    """
    from backend.application.ports.runtime.interface import (
        BackgroundExecutorPort,
        ChatRunExecutorPort,
        RunExecutionDispatcherPort,
    )

    assert hasattr(RunExecutionDispatcherPort, "register")
    assert hasattr(ChatRunExecutorPort, "execute")
    assert hasattr(BackgroundExecutorPort, "submit")


def test_chat_repository_port_exposes_f004_runtime_state_methods() -> None:
    """
    観点：ChatRepository IFがSSE、キャンセル、起動時回復に必要なrun状態境界を表すこと
    確認：現在状態取得、状態条件付き更新、中間メッセージ取得、
    起動時回復対象取得の公開メソッドがProtocolに定義されること
    """
    from backend.application.ports.database.interface import ChatRepositoryPort

    expected_method_names = (
        "get_run_state_for_sse",
        "list_intermediate_messages_for_sse",
        "get_cancel_target",
        "update_run_state_if_current",
        "list_unfinished_runs_for_recovery",
    )

    for method_name in expected_method_names:
        assert hasattr(ChatRepositoryPort, method_name), method_name


def test_chat_repository_port_exposes_f007_deletion_methods() -> None:
    """
    観点：ChatRepository IFがF007のチャット削除受付、物理削除、起動時再登録の
    永続化境界を表すこと
    確認：削除中更新、削除対象取得、削除中チャット一覧、DBカスケード削除に
    必要な公開メソッドがProtocolに定義されること
    """
    from backend.application.ports.database.interface import ChatRepositoryPort

    expected_method_names = (
        "mark_chat_deleting",
        "get_chat_deletion_target",
        "list_deleting_chats_for_recovery",
        "delete_chat_cascade",
    )

    for method_name in expected_method_names:
        assert hasattr(ChatRepositoryPort, method_name), method_name


def test_chat_deletion_dto_exposes_f007_physical_delete_fields() -> None:
    """
    観点：ChatDeletionTargetがチャット物理削除に必要な情報をORMなしで返すこと
    確認：対象chat_id、user_id、session_id、未完了run、保存済み成果物storage_pathを
    DTO項目として保持すること
    """
    from backend.application.ports.database.dto import ChatDeletionTarget

    assert is_dataclass(ChatDeletionTarget)
    assert {
        "chat_id",
        "user_id",
        "session_id",
        "unfinished_run_ids",
        "storage_paths",
    } <= _dataclass_field_names(ChatDeletionTarget)


def test_chat_deletion_runtime_ports_expose_f007_dispatch_status() -> None:
    """
    観点：チャット削除受付が物理削除ジョブ登録をruntime portへ委譲すること
    確認：ChatDeletionDispatcherPort、ChatDeletionDispatchResult、
    ChatDeletionDispatchStatusがregistered、already_registered、failedを表すこと
    """
    from backend.application.ports.runtime.interface import (
        ChatDeletionDispatcherPort,
        ChatDeletionDispatchResult,
        ChatDeletionDispatchStatus,
    )

    assert hasattr(ChatDeletionDispatcherPort, "dispatch_chat_deletion")
    assert is_dataclass(ChatDeletionDispatchResult)
    assert tuple(status.value for status in ChatDeletionDispatchStatus) == (
        "registered",
        "already_registered",
        "failed",
    )


def _dataclass_field_names(dataclass_type: type) -> set[str]:
    return {field.name for field in fields(dataclass_type)}

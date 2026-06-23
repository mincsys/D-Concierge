from __future__ import annotations

from dataclasses import is_dataclass


def test_database_repository_ports_are_declared_for_application_boundary() -> None:
    """
    観点：Repository境界がapplication層のPortとして定義されること
    確認：トランザクション、アカウント、ログインセッション、チャット受付、
    起動時回復、実行、読取、削除の用途別Repository Portをimportできること
    """
    from backend.application.ports.database.interface import (
        AcceptedRunStateRepositoryPort,
        AccountDeletionRepositoryPort,
        AccountReadRepositoryPort,
        AccountRepositoryPort,
        AccountWriteRepositoryPort,
        AppendChatRunRepositoryPort,
        CancelChatRunRepositoryPort,
        ChatExecutionRepositoryPort,
        ChatReadRepositoryPort,
        ChatRepositoryPort,
        ChatRuntimeRepositoryPort,
        DeleteChatRepositoryPort,
        LoginSessionRepositoryPort,
        RecoveryRepositoryPort,
        StartChatRepositoryPort,
        TransactionManagerPort,
    )

    ports = (
        TransactionManagerPort,
        AccountReadRepositoryPort,
        AccountWriteRepositoryPort,
        LoginSessionRepositoryPort,
        AccountDeletionRepositoryPort,
        AccountRepositoryPort,
        StartChatRepositoryPort,
        AppendChatRunRepositoryPort,
        AcceptedRunStateRepositoryPort,
        RecoveryRepositoryPort,
        ChatExecutionRepositoryPort,
        CancelChatRunRepositoryPort,
        ChatRuntimeRepositoryPort,
        ChatReadRepositoryPort,
        DeleteChatRepositoryPort,
        ChatRepositoryPort,
    )

    assert all(type(port).__name__ == "_ProtocolMeta" for port in ports)


def test_repository_boundary_dtos_are_dataclasses_not_orm_models() -> None:
    """
    観点：Repository境界がSQLAlchemyモデルではなくDTOでapplication層へ値を返すこと
    確認：AccountUserData、LoginSessionData、AcceptedRun、UnfinishedRun、
    ChatRuntimeContext、HistoryItem、ChatDetail、AnswerData、
    DisplayReferenceData、ArtifactDataがdataclassであること
    """
    from backend.application.ports.database.dto import (
        AcceptedRun,
        AccountDeletionTarget,
        AccountUserData,
        AnswerData,
        ArtifactData,
        ChatDeletionTarget,
        ChatDetail,
        ChatRuntimeContext,
        DisplayReferenceData,
        HistoryItem,
        LoginSessionData,
        UnfinishedRun,
    )

    dto_classes = (
        AccountUserData,
        LoginSessionData,
        AccountDeletionTarget,
        AcceptedRun,
        UnfinishedRun,
        ChatRuntimeContext,
        HistoryItem,
        ChatDetail,
        AnswerData,
        DisplayReferenceData,
        ArtifactData,
        ChatDeletionTarget,
    )

    assert all(is_dataclass(dto_class) for dto_class in dto_classes)
    assert all(not hasattr(dto_class, "__table__") for dto_class in dto_classes)

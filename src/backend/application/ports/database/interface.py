from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Protocol
from uuid import UUID

from backend.application.ports.database.dto import (
    AcceptedRun,
    AccountDeletionTarget,
    AccountUserData,
    AnswerData,
    ArtifactData,
    CancelRunTarget,
    ChatDeletionTarget,
    ChatDetail,
    ChatRuntimeContext,
    DisplayReferenceData,
    HistoryItem,
    IntermediateMessageData,
    LoginSessionData,
    SseRunSnapshot,
    UnfinishedRun,
)


class TransactionManagerPort(Protocol):
    """DBトランザクション境界。"""

    def __enter__(self) -> None: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class AccountReadRepositoryPort(Protocol):
    """アカウント読取境界。"""

    def find_user_by_id(self, user_id: str) -> AccountUserData | None: ...

    def find_user_by_name(self, user_name: str) -> AccountUserData | None: ...


class AccountWriteRepositoryPort(Protocol):
    """アカウント更新境界。"""

    def create_user(
        self,
        user_id: str,
        user_name: str,
        password_hash: str,
        created_at: datetime,
    ) -> AccountUserData: ...

    def update_user_name(
        self,
        user_id: str,
        user_name: str,
        updated_at: datetime,
    ) -> AccountUserData | None: ...

    def update_password_hash(
        self,
        user_id: str,
        password_hash: str,
        updated_at: datetime,
    ) -> None: ...


class LoginSessionRepositoryPort(Protocol):
    """ログインセッション境界。"""

    def get_user_for_login(self, user_id: str) -> AccountUserData | None: ...

    def create_login_session(
        self,
        token_hash: str,
        user_id: str,
        expires_at: datetime,
        created_at: datetime,
    ) -> LoginSessionData: ...

    def find_session_by_token_hash(
        self,
        token_hash: str,
    ) -> LoginSessionData | None: ...

    def delete_session_by_token_hash(self, token_hash: str) -> int: ...

    def delete_sessions_by_user_id(self, user_id: str) -> int: ...

    def find_valid_session(self, token_hash: str) -> LoginSessionData | None: ...

    def delete_session(self, token_hash: str) -> None: ...


class AccountDeletionRepositoryPort(Protocol):
    """アカウント削除境界。"""

    def mark_user_deleting(
        self,
        user_id: str,
        updated_at: datetime,
    ) -> str | None: ...

    def mark_user_chats_deleting(self, user_id: str, updated_at: datetime) -> int: ...

    def delete_user(self, user_id: str) -> None: ...

    def get_account_deletion_target(
        self,
        user_id: str,
    ) -> AccountDeletionTarget | None: ...

    def delete_account_data(self, user_id: str) -> None: ...

    def delete_expired_sessions(self, now: datetime) -> int: ...

    def list_deleting_user_ids(self) -> tuple[str, ...]: ...


class AccountRepositoryPort(
    AccountReadRepositoryPort,
    AccountWriteRepositoryPort,
    LoginSessionRepositoryPort,
    AccountDeletionRepositoryPort,
    Protocol,
):
    """アカウント関連Repositoryの集約境界。"""


class StartChatRepositoryPort(Protocol):
    """新規チャット開始境界。"""

    def create_chat_with_first_run(
        self,
        user_id: str,
        chat_id: UUID,
        run_id: UUID,
        session_id: UUID,
        title: str,
        user_instruction: str,
        trace_id: str,
        started_at: datetime,
    ) -> AcceptedRun: ...


class AppendChatRunRepositoryPort(Protocol):
    """チャット継続指示のrun追加境界。"""

    def append_run(
        self,
        user_id: str,
        chat_id: UUID,
        run_id: UUID,
        user_instruction: str,
        trace_id: str,
        started_at: datetime,
    ) -> AcceptedRun: ...


class AcceptedRunStateRepositoryPort(Protocol):
    """受付済みrunの状態更新境界。"""

    def mark_run_running(self, run_id: UUID) -> None: ...

    def mark_run_error(self, run_id: UUID, diagnostic_message: str) -> None: ...


class RecoveryRepositoryPort(Protocol):
    """起動時回復境界。"""

    def list_unfinished_runs(self) -> tuple[UnfinishedRun, ...]: ...

    def list_unfinished_runs_for_recovery(self) -> tuple[UnfinishedRun, ...]: ...


class ChatExecutionRepositoryPort(Protocol):
    """チャット実行結果保存境界。"""

    def load_runtime_context(self, chat_id: UUID) -> ChatRuntimeContext | None: ...

    def save_answers(self, run_id: UUID, answers: tuple[AnswerData, ...]) -> None: ...


class CancelChatRunRepositoryPort(Protocol):
    """runキャンセル境界。"""

    def request_cancel(self, run_id: UUID) -> bool: ...

    def get_cancel_target(
        self,
        user_id: str,
        chat_id: UUID,
        run_id: UUID,
    ) -> CancelRunTarget | None: ...

    def update_run_state_if_current(
        self,
        run_id: UUID,
        expected_state: str,
        next_state: str,
        user_message: str | None = None,
    ) -> bool: ...


class SseRunRepositoryPort(Protocol):
    """SSE購読開始時のrun状態読取境界。"""

    def get_run_state_for_sse(
        self,
        user_id: str,
        chat_id: UUID,
        run_id: UUID,
    ) -> SseRunSnapshot | None: ...

    def list_intermediate_messages_for_sse(
        self,
        run_id: UUID,
    ) -> tuple[IntermediateMessageData, ...]: ...


class ChatRuntimeRepositoryPort(
    AppendChatRunRepositoryPort,
    AcceptedRunStateRepositoryPort,
    RecoveryRepositoryPort,
    ChatExecutionRepositoryPort,
    CancelChatRunRepositoryPort,
    SseRunRepositoryPort,
    Protocol,
):
    """チャット実行系Repositoryの集約境界。"""


class ChatReadRepositoryPort(Protocol):
    """チャット読取境界。"""

    def list_histories(self, user_id: str) -> tuple[HistoryItem, ...]: ...

    def get_chat_detail(self, user_id: str, chat_id: UUID) -> ChatDetail | None: ...


class DeleteChatRepositoryPort(Protocol):
    """チャット削除境界。"""

    def mark_chat_deleting(
        self,
        user_id: str,
        chat_id: UUID,
        updated_at: datetime,
    ) -> str | None: ...

    def get_chat_deletion_target(self, chat_id: UUID) -> ChatDeletionTarget | None: ...

    def list_deleting_chats_for_recovery(self) -> tuple[UUID, ...]: ...

    def delete_chat_cascade(self, chat_id: UUID) -> None: ...


class ReferenceDeliveryRepositoryPort(Protocol):
    """参照元PDF配信用Repository境界。"""

    def get_reference_for_delivery(
        self,
        user_id: str,
        reference_id: UUID,
    ) -> DisplayReferenceData | None: ...


class ArtifactDeliveryRepositoryPort(Protocol):
    """Codex成果物配信用Repository境界。"""

    def get_artifact_for_delivery(
        self,
        user_id: str,
        artifact_id: UUID,
    ) -> ArtifactData | None: ...


class ChatRepositoryPort(
    StartChatRepositoryPort,
    ChatRuntimeRepositoryPort,
    ChatReadRepositoryPort,
    DeleteChatRepositoryPort,
    ReferenceDeliveryRepositoryPort,
    ArtifactDeliveryRepositoryPort,
    Protocol,
):
    """チャット関連Repositoryの集約境界。"""

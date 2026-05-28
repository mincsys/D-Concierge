from contextlib import AbstractContextManager
from datetime import datetime
from typing import Protocol
from uuid import UUID

from backend.application.ports.database.dto import (
    AcceptedRun,
    AccountDeletionTarget,
    AccountUserData,
    AnswerData,
    ArtifactData,
    ChatDeletionTarget,
    ChatDetail,
    ChatRuntimeContext,
    DeleteChatResult,
    DisplayReferenceData,
    HistoryItem,
    LoginSessionData,
    UnfinishedRun,
)
from backend.domain.execution.run_state import RunState


class TransactionManagerPort(Protocol):
    """DBトランザクション境界を管理する境界。"""

    def transaction(self) -> AbstractContextManager[None]:
        """1つのDB作業単位を開始する。"""


class AccountReadRepositoryPort(Protocol):
    """ユーザとログインセッション参照境界。"""

    def get_user_for_login(self, user_id: str) -> AccountUserData | None:
        """ログイン検証用ユーザ情報を返す。"""

    def find_session_by_token_hash(self, token_hash: str) -> LoginSessionData | None:
        """トークンハッシュに対応するログインセッションを返す。"""


class AccountWriteRepositoryPort(Protocol):
    """ユーザ更新境界。"""

    def create_user(
        self, user_id: str, user_name: str, password_hash: str, now: datetime
    ) -> None:
        """ユーザを作成する。"""

    def update_user_name(
        self, user_id: str, user_name: str, now: datetime
    ) -> AccountUserData:
        """ユーザ名を更新し、更新後ユーザを返す。"""

    def update_password_hash(
        self, user_id: str, password_hash: str, now: datetime
    ) -> None:
        """パスワードハッシュを更新する。"""

    def mark_user_deleting(self, user_id: str, now: datetime) -> None:
        """ユーザを削除中に更新する。"""

    def mark_user_chats_deleting(self, user_id: str, now: datetime) -> None:
        """ユーザの全チャットを削除中に更新する。"""


class LoginSessionRepositoryPort(Protocol):
    """ログインセッション更新境界。"""

    def create_login_session(
        self, token_hash: str, user_id: str, expires_at: datetime, now: datetime
    ) -> LoginSessionData:
        """ログインセッションを作成する。"""

    def delete_session_by_token_hash(self, token_hash: str) -> int:
        """トークンハッシュに対応するログインセッションを削除する。"""

    def delete_sessions_by_user_id(self, user_id: str) -> int:
        """ユーザの全ログインセッションを削除する。"""

    def delete_expired_sessions(self, now: datetime) -> int:
        """期限切れログインセッションを削除する。"""


class AccountDeletionRepositoryPort(Protocol):
    """アカウント物理削除境界。"""

    def list_deleting_user_ids(self) -> tuple[str, ...]:
        """削除中ユーザIDを返す。"""

    def get_account_deletion_target(self, user_id: str) -> AccountDeletionTarget | None:
        """アカウント物理削除対象を返す。"""

    def delete_account_data(self, user_id: str) -> None:
        """ユーザに紐づくDBデータを削除する。"""


class AccountRepositoryPort(
    AccountReadRepositoryPort,
    AccountWriteRepositoryPort,
    LoginSessionRepositoryPort,
    AccountDeletionRepositoryPort,
    Protocol,
):
    """アカウント永続化を行うRepository境界。"""


class AcceptedRunStateRepositoryPort(Protocol):
    """受付済みrunの状態更新境界。"""

    def set_run_state(
        self,
        chat_id: UUID,
        run_id: UUID,
        state: RunState,
        user_message: str | None = None,
    ) -> None:
        """runの状態と利用者向けメッセージを更新する。"""


class StartChatRepositoryPort(AcceptedRunStateRepositoryPort, Protocol):
    """新規チャット受付に必要なRepository境界。"""

    def create_chat_with_first_run(
        self, user_instruction: str, user_id: str = ""
    ) -> AcceptedRun:
        """新規チャット、初回run、初回指示を保存する。"""


class AppendChatRunRepositoryPort(AcceptedRunStateRepositoryPort, Protocol):
    """継続指示受付に必要なRepository境界。"""

    def append_run(
        self, chat_id: UUID, user_instruction: str, user_id: str = ""
    ) -> AcceptedRun:
        """既存チャットへ受付runと指示を追加する。"""


class RecoveryRepositoryPort(Protocol):
    """起動時回復に必要なRepository境界。"""

    def list_unfinished_runs_for_recovery(self) -> tuple[UnfinishedRun, ...]:
        """未完了runを返す。"""

    def set_run_state(
        self,
        chat_id: UUID,
        run_id: UUID,
        state: RunState,
        user_message: str | None = None,
    ) -> None:
        """runの状態と利用者向けメッセージを更新する。"""

    def list_deleting_chats_for_recovery(self) -> tuple[UUID, ...]:
        """起動時に物理削除を再登録する削除中チャットIDを返す。"""


class ChatExecutionRepositoryPort(Protocol):
    """チャット実行処理が利用するRepository境界。"""

    def get_run_instruction(self, chat_id: UUID, run_id: UUID) -> str:
        """runに対応するユーザ指示本文を返す。"""

    def get_run_state(self, chat_id: UUID, run_id: UUID) -> RunState:
        """runの現在状態を返す。"""

    def set_run_state(
        self,
        chat_id: UUID,
        run_id: UUID,
        state: RunState,
        user_message: str | None = None,
    ) -> None:
        """run状態を更新する。"""

    def update_run_state_if_current(
        self,
        chat_id: UUID,
        run_id: UUID,
        expected_states: tuple[RunState, ...],
        state: RunState,
        user_message: str | None = None,
        execution_deadline_at: datetime | None = None,
    ) -> bool:
        """期待状態に一致する場合だけrun状態を更新する。"""

    def add_intermediate_message(self, chat_id: UUID, run_id: UUID, text: str) -> None:
        """中間メッセージを保存する。"""

    def save_completed_answer(
        self,
        chat_id: UUID,
        run_id: UUID,
        answer: AnswerData,
    ) -> None:
        """検証済み回答を保存する。"""


class CancelChatRunRepositoryPort(Protocol):
    """キャンセル受付に必要なRepository境界。"""

    def get_run_state(self, chat_id: UUID, run_id: UUID) -> RunState:
        """対象runの現在状態を返す。"""

    def cancel_run(self, chat_id: UUID, run_id: UUID) -> None:
        """対象runをキャンセルする。"""

    def update_run_state_if_current(
        self,
        chat_id: UUID,
        run_id: UUID,
        expected_states: tuple[RunState, ...],
        state: RunState,
        user_message: str | None = None,
    ) -> bool:
        """期待状態に一致する場合だけrun状態を更新する。"""


class ChatRuntimeRepositoryPort(Protocol):
    """Codex実行に必要なチャット実行コンテキスト境界。"""

    def get_chat_runtime_context(self, chat_id: UUID) -> ChatRuntimeContext:
        """チャット単位のCodex実行コンテキストを返す。"""

    def save_generation_conversation_id(
        self, chat_id: UUID, codex_conversation_id: str
    ) -> None:
        """生成用Codex側resume IDを保存する。"""

    def save_validation_conversation_id(
        self, chat_id: UUID, codex_conversation_id: str
    ) -> None:
        """検証用Codex側resume IDを保存する。"""


class ChatReadRepositoryPort(Protocol):
    """チャット表示情報と配信メタ情報の取得境界。"""

    def list_histories(self, user_id: str = "") -> tuple[HistoryItem, ...]:
        """履歴一覧を返す。"""

    def get_chat_detail(self, chat_id: UUID, user_id: str = "") -> ChatDetail:
        """チャット詳細を返す。"""

    def get_reference(self, reference_id: UUID) -> DisplayReferenceData:
        """参照元配信メタ情報を返す。"""

    def get_artifact(self, artifact_id: UUID) -> ArtifactData:
        """成果物配信メタ情報を返す。"""


class ChatDeletionRepositoryPort(Protocol):
    """チャット削除に必要なRepository境界。"""

    def mark_chat_deleting(self, chat_id: UUID, user_id: str = "") -> DeleteChatResult:
        """対象チャットを削除中へ更新する。"""

    def get_chat_deletion_target(self, chat_id: UUID) -> ChatDeletionTarget:
        """物理削除に必要な対象情報を返す。"""

    def set_run_state(
        self,
        chat_id: UUID,
        run_id: UUID,
        state: RunState,
        user_message: str | None = None,
    ) -> None:
        """run状態を更新する。"""

    def delete_chat_cascade(self, chat_id: UUID) -> None:
        """対象チャット一式をDBから削除する。"""


class ChatRepositoryPort(
    StartChatRepositoryPort,
    AppendChatRunRepositoryPort,
    RecoveryRepositoryPort,
    ChatExecutionRepositoryPort,
    CancelChatRunRepositoryPort,
    ChatRuntimeRepositoryPort,
    ChatReadRepositoryPort,
    ChatDeletionRepositoryPort,
    Protocol,
):
    """チャット永続化と参照を行うRepository境界。"""

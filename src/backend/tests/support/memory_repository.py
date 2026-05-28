from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from uuid import UUID, uuid4

from backend.application.ports.database.dto import (
    SHARED_LOCAL_USER_ID,
    AcceptedRun,
    AccountDeletionTarget,
    AccountUserData,
    AnswerBlockData,
    AnswerData,
    ArtifactData,
    ChatDeletionRun,
    ChatDeletionTarget,
    ChatDetail,
    ChatRuntimeContext,
    DeleteChatResult,
    DisplayReferenceData,
    HistoryItem,
    IntermediateMessageData,
    LoginSessionData,
    RunDetail,
    UnfinishedRun,
)
from backend.domain.account.user_state import UserState
from backend.domain.chat.chat_state import ChatState
from backend.domain.chat.chat_title_policy import ChatTitlePolicy
from backend.domain.chat.user_instruction import (
    InvalidUserInstructionError,
    UserInstruction,
)
from backend.domain.execution.run_state import RunState
from backend.domain.execution.run_state_policy import RunStatePolicy
from backend.domain.references.source_type import SourceType
from backend.shared.errors.errors import (
    ActiveRunConflictError,
    ArtifactNotFoundError,
    CancelNotAllowedError,
    ChatDeletingError,
    ChatNotFoundError,
    ReferenceNotFoundError,
    RunNotFoundError,
    UserInstructionRequiredError,
)
from backend.shared.user_messages import (
    CANCEL_REQUESTED_MESSAGE,
    CANCELED_MESSAGE,
)


@dataclass(slots=True)
class _RunRecord:
    id: UUID
    chat_id: UUID
    state: RunState
    started_at: datetime
    user_instruction: str
    execution_deadline_at: datetime | None = None
    user_message: str | None = None
    intermediate_messages: list[IntermediateMessageData] = field(default_factory=list)
    answer: AnswerData | None = None


@dataclass(slots=True)
class _ChatRecord:
    id: UUID
    user_id: str
    local_user_id: UUID
    session_id: UUID
    title: str
    updated_at: datetime
    generation_conversation_id: str | None = None
    validation_conversation_id: str | None = None
    chat_state: ChatState = ChatState.ACTIVE
    run_ids: list[UUID] = field(default_factory=list)


class InMemoryChatRepository:
    """チャット関連データをメモリ上に保持するRepository実装。"""

    def __init__(self, now_values: Iterable[datetime] = ()) -> None:
        self._now_values = list(now_values)
        self._chats: dict[UUID, _ChatRecord] = {}
        self._runs: dict[UUID, _RunRecord] = {}
        self._references: dict[UUID, DisplayReferenceData] = {}
        self._artifacts: dict[UUID, ArtifactData] = {}
        self._reference_chat_ids: dict[UUID, UUID] = {}
        self._artifact_chat_ids: dict[UUID, UUID] = {}
        self._latest_artifact_id: UUID | None = None
        self._users: dict[str, AccountUserData] = {}
        self._sessions: dict[str, LoginSessionData] = {}
        self._next_session_id = 0
        self._lock = RLock()

    def create_user(
        self, user_id: str, user_name: str, password_hash: str, now: datetime
    ) -> None:
        """アカウントユーザを保存する。"""
        _ = now
        with self._lock:
            self._users[user_id] = AccountUserData(
                user_id=user_id,
                user_name=user_name,
                password_hash=password_hash,
                user_state=UserState.ACTIVE,
            )

    def get_user_for_login(self, user_id: str) -> AccountUserData | None:
        """ログイン検証用ユーザを返す。"""
        with self._lock:
            return self._users.get(user_id)

    def update_user_name(
        self, user_id: str, user_name: str, now: datetime
    ) -> AccountUserData:
        """ユーザ名を更新する。"""
        _ = now
        with self._lock:
            user = self._get_user_locked(user_id)
            updated = AccountUserData(
                user_id=user.user_id,
                user_name=user_name,
                password_hash=user.password_hash,
                user_state=user.user_state,
            )
            self._users[user_id] = updated
            return updated

    def update_password_hash(
        self, user_id: str, password_hash: str, now: datetime
    ) -> None:
        """パスワードハッシュを更新する。"""
        _ = now
        with self._lock:
            user = self._get_user_locked(user_id)
            self._users[user_id] = AccountUserData(
                user_id=user.user_id,
                user_name=user.user_name,
                password_hash=password_hash,
                user_state=user.user_state,
            )

    def create_login_session(
        self, token_hash: str, user_id: str, expires_at: datetime, now: datetime
    ) -> LoginSessionData:
        """ログインセッションを保存する。"""
        _ = now
        with self._lock:
            user = self._get_user_locked(user_id)
            self._next_session_id += 1
            session = LoginSessionData(
                session_id=self._next_session_id,
                token_hash=token_hash,
                user_id=user.user_id,
                user_name=user.user_name,
                user_state=user.user_state,
                expires_at=expires_at,
            )
            self._sessions[token_hash] = session
            return session

    def find_session_by_token_hash(self, token_hash: str) -> LoginSessionData | None:
        """トークンハッシュに対応するログインセッションを返す。"""
        with self._lock:
            session = self._sessions.get(token_hash)
            if session is None:
                return None
            user = self._users.get(session.user_id)
            if user is None:
                return None
            return LoginSessionData(
                session_id=session.session_id,
                token_hash=session.token_hash,
                user_id=user.user_id,
                user_name=user.user_name,
                user_state=user.user_state,
                expires_at=session.expires_at,
            )

    def delete_session_by_token_hash(self, token_hash: str) -> int:
        """トークンハッシュに対応するセッションを削除する。"""
        with self._lock:
            existed = token_hash in self._sessions
            self._sessions.pop(token_hash, None)
            return 1 if existed else 0

    def delete_sessions_by_user_id(self, user_id: str) -> int:
        """ユーザの全ログインセッションを削除する。"""
        with self._lock:
            target_hashes = [
                token_hash
                for token_hash, session in self._sessions.items()
                if session.user_id == user_id
            ]
            for token_hash in target_hashes:
                self._sessions.pop(token_hash, None)
            return len(target_hashes)

    def delete_expired_sessions(self, now: datetime) -> int:
        """期限切れログインセッションを削除する。"""
        with self._lock:
            target_hashes = [
                token_hash
                for token_hash, session in self._sessions.items()
                if session.expires_at <= now
            ]
            for token_hash in target_hashes:
                self._sessions.pop(token_hash, None)
            return len(target_hashes)

    def mark_user_deleting(self, user_id: str, now: datetime) -> None:
        """ユーザを削除中へ更新する。"""
        _ = now
        with self._lock:
            user = self._get_user_locked(user_id)
            self._users[user_id] = AccountUserData(
                user_id=user.user_id,
                user_name=user.user_name,
                password_hash=user.password_hash,
                user_state=UserState.DELETING,
            )

    def mark_user_chats_deleting(self, user_id: str, now: datetime) -> None:
        """ユーザの全チャットを削除中へ更新する。"""
        _ = now
        with self._lock:
            for chat in self._chats.values():
                if chat.user_id == user_id:
                    chat.chat_state = ChatState.DELETING

    def list_deleting_user_ids(self) -> tuple[str, ...]:
        """削除中ユーザIDを返す。"""
        with self._lock:
            return tuple(
                user.user_id
                for user in self._users.values()
                if user.user_state is UserState.DELETING
            )

    def get_account_deletion_target(self, user_id: str) -> AccountDeletionTarget | None:
        """アカウント物理削除対象を返す。"""
        with self._lock:
            if user_id not in self._users:
                return None
            unfinished_runs = tuple(
                ChatDeletionRun(run_id=run.id, state=run.state)
                for run in self._runs.values()
                if self._chats[run.chat_id].user_id == user_id
                and RunStatePolicy.is_unfinished(run.state)
            )
            return AccountDeletionTarget(
                user_id=user_id, unfinished_runs=unfinished_runs
            )

    def delete_account_data(self, user_id: str) -> None:
        """ユーザとログインセッションを削除する。"""
        with self._lock:
            self.delete_sessions_by_user_id(user_id)
            chat_ids = tuple(
                chat.id for chat in self._chats.values() if chat.user_id == user_id
            )
            for chat_id in chat_ids:
                self.delete_chat_cascade(chat_id)
            self._users.pop(user_id, None)

    def create_chat_with_first_run(
        self, user_instruction: str, user_id: str = ""
    ) -> AcceptedRun:
        """新規チャット、初回run、初回指示を同時に保存する。"""
        instruction = _user_instruction(user_instruction)
        now = self._now()
        chat_id = uuid4()
        run_id = uuid4()
        chat = _ChatRecord(
            id=chat_id,
            user_id=user_id,
            local_user_id=SHARED_LOCAL_USER_ID,
            session_id=uuid4(),
            title=ChatTitlePolicy.make_title(instruction),
            updated_at=now,
            run_ids=[run_id],
        )
        run = _RunRecord(
            id=run_id,
            chat_id=chat_id,
            state=RunState.ACCEPTED,
            started_at=now,
            user_instruction=instruction.body,
        )
        with self._lock:
            self._chats[chat_id] = chat
            self._runs[run_id] = run
        return AcceptedRun(chat_id=chat_id, run_id=run_id, state=RunState.ACCEPTED)

    def append_run(
        self, chat_id: UUID, user_instruction: str, user_id: str = ""
    ) -> AcceptedRun:
        """既存チャットへ受付runと指示を追加する。"""
        instruction = _user_instruction(user_instruction)
        now = self._now()
        run_id = uuid4()
        with self._lock:
            chat = self._get_active_chat_locked(chat_id, user_id=user_id)
            for existing_run_id in chat.run_ids:
                if RunStatePolicy.is_unfinished(self._runs[existing_run_id].state):
                    raise ActiveRunConflictError()
            run = _RunRecord(
                id=run_id,
                chat_id=chat_id,
                state=RunState.ACCEPTED,
                started_at=now,
                user_instruction=instruction.body,
            )
            chat.run_ids.append(run_id)
            chat.updated_at = now
            self._runs[run_id] = run
        return AcceptedRun(chat_id=chat_id, run_id=run_id, state=RunState.ACCEPTED)

    def list_histories(self, user_id: str = "") -> tuple[HistoryItem, ...]:
        """チャット履歴を更新日時降順で返す。"""
        with self._lock:
            histories = [
                self._to_history_item(chat)
                for chat in self._chats.values()
                if len(chat.run_ids) > 0
                and chat.chat_state is ChatState.ACTIVE
                and (not user_id or chat.user_id == user_id)
            ]
        return tuple(sorted(histories, key=lambda item: item.updated_at, reverse=True))

    def list_unfinished_runs_for_recovery(self) -> tuple[UnfinishedRun, ...]:
        """起動時回復対象の未完了runを開始日時順で返す。"""
        with self._lock:
            runs = [
                run
                for run in self._runs.values()
                if RunStatePolicy.is_unfinished(run.state)
                and self._chats[run.chat_id].chat_state is ChatState.ACTIVE
            ]
        return tuple(
            UnfinishedRun(chat_id=run.chat_id, run_id=run.id, state=run.state)
            for run in sorted(runs, key=lambda item: (item.started_at, str(item.id)))
        )

    def get_chat_detail(self, chat_id: UUID, user_id: str = "") -> ChatDetail:
        """指定チャットの詳細を返す。"""
        with self._lock:
            chat = self._get_active_chat_locked(chat_id, user_id=user_id)
            runs = tuple(
                self._to_run_detail(self._runs[run_id]) for run_id in chat.run_ids
            )
            return ChatDetail(chat_id=chat.id, title=chat.title, runs=runs)

    def get_chat_runtime_context(self, chat_id: UUID) -> ChatRuntimeContext:
        """Codex実行に必要なチャット単位の内部コンテキストを返す。"""
        with self._lock:
            chat = self._get_active_chat_locked(chat_id)
            return ChatRuntimeContext(
                chat_id=chat.id,
                user_id=chat.user_id or str(chat.local_user_id),
                local_user_id=chat.local_user_id,
                session_id=chat.session_id,
                generation_conversation_id=chat.generation_conversation_id,
                validation_conversation_id=chat.validation_conversation_id,
            )

    def save_generation_conversation_id(
        self, chat_id: UUID, codex_conversation_id: str
    ) -> None:
        """生成用Codex側resume IDを保存する。"""
        with self._lock:
            chat = self._get_chat_locked(chat_id)
            chat.generation_conversation_id = codex_conversation_id

    def save_validation_conversation_id(
        self, chat_id: UUID, codex_conversation_id: str
    ) -> None:
        """検証用Codex側resume IDを保存する。"""
        with self._lock:
            chat = self._get_chat_locked(chat_id)
            chat.validation_conversation_id = codex_conversation_id

    def get_run_state(self, chat_id: UUID, run_id: UUID) -> RunState:
        """SSE初期通知用に現在状態を返す。"""
        with self._lock:
            run = self._get_run_locked(chat_id, run_id)
            return run.state

    def get_run_instruction(self, chat_id: UUID, run_id: UUID) -> str:
        """実行対象runのユーザ指示を返す。"""
        with self._lock:
            run = self._get_run_locked(chat_id, run_id)
            return run.user_instruction

    def set_run_state(
        self,
        chat_id: UUID,
        run_id: UUID,
        state: RunState,
        user_message: str | None = None,
    ) -> None:
        """実行対象runの状態と利用者向けメッセージを更新する。"""
        now = self._now()
        with self._lock:
            run = self._get_run_locked(chat_id, run_id)
            run.state = state
            run.user_message = user_message
            self._chats[chat_id].updated_at = now

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
        now = self._now()
        with self._lock:
            run = self._get_run_locked(chat_id, run_id)
            if run.state not in expected_states:
                return False
            run.state = state
            run.user_message = user_message
            if execution_deadline_at is not None:
                run.execution_deadline_at = execution_deadline_at
            self._chats[chat_id].updated_at = now
            return True

    def add_intermediate_message(self, chat_id: UUID, run_id: UUID, text: str) -> None:
        """実行対象runへ中間メッセージを追加する。"""
        now = self._now()
        with self._lock:
            run = self._get_run_locked(chat_id, run_id)
            run.intermediate_messages.append(IntermediateMessageData(text=text))
            self._chats[chat_id].updated_at = now

    def save_completed_answer(
        self,
        chat_id: UUID,
        run_id: UUID,
        answer: AnswerData,
    ) -> None:
        """実行対象runへ検証済み回答を保存する。"""
        now = self._now()
        with self._lock:
            run = self._get_run_locked(chat_id, run_id)
            run.answer = answer
            for block in answer.blocks:
                for reference in block.references:
                    self._references[reference.reference_id] = reference
                    self._reference_chat_ids[reference.reference_id] = chat_id
                for artifact in block.artifacts:
                    self._artifacts[artifact.artifact_id] = artifact
                    self._artifact_chat_ids[artifact.artifact_id] = chat_id
                    self._latest_artifact_id = artifact.artifact_id
            self._chats[chat_id].updated_at = now

    def cancel_run(self, chat_id: UUID, run_id: UUID) -> None:
        """対象runをキャンセル要求中経由でキャンセル済みにする。"""
        now = self._now()
        with self._lock:
            run = self._get_run_locked(chat_id, run_id)
            if not RunStatePolicy.is_cancelable(run.state):
                raise CancelNotAllowedError()
            run.state = RunState.CANCEL_REQUESTED
            run.user_message = CANCEL_REQUESTED_MESSAGE
            run.state = RunState.CANCELED
            run.user_message = CANCELED_MESSAGE
            self._chats[chat_id].updated_at = now

    def get_reference(self, reference_id: UUID) -> DisplayReferenceData:
        """参照元IDに対応する配信メタ情報を返す。"""
        reference = self._references.get(reference_id)
        if reference is None:
            raise ReferenceNotFoundError()
        self._raise_if_deleting(self._reference_chat_ids[reference_id])
        return reference

    def get_artifact(self, artifact_id: UUID) -> ArtifactData:
        """成果物IDに対応する配信メタ情報を返す。"""
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            raise ArtifactNotFoundError()
        self._raise_if_deleting(self._artifact_chat_ids[artifact_id])
        return artifact

    def mark_chat_deleting(self, chat_id: UUID, user_id: str = "") -> DeleteChatResult:
        """対象チャットを削除中にする。"""
        with self._lock:
            chat = self._get_chat_locked(chat_id, user_id=user_id)
            chat.chat_state = ChatState.DELETING
            return DeleteChatResult(chat_id=chat_id, chat_state=ChatState.DELETING)

    def list_deleting_chats_for_recovery(self) -> tuple[UUID, ...]:
        """削除中チャットIDを返す。"""
        with self._lock:
            return tuple(
                chat.id
                for chat in self._chats.values()
                if chat.chat_state is ChatState.DELETING
            )

    def get_chat_deletion_target(self, chat_id: UUID) -> ChatDeletionTarget:
        """物理削除に必要な対象情報を返す。"""
        with self._lock:
            chat = self._get_chat_locked(chat_id)
            unfinished_runs = tuple(
                ChatDeletionRun(run_id=run_id, state=self._runs[run_id].state)
                for run_id in chat.run_ids
                if RunStatePolicy.is_unfinished(self._runs[run_id].state)
            )
            artifact_storage_paths = tuple(
                artifact.relative_path
                for artifact_id, artifact in self._artifacts.items()
                if self._artifact_chat_ids.get(artifact_id) == chat_id
            )
            return ChatDeletionTarget(
                chat_id=chat.id,
                user_id=chat.user_id or str(chat.local_user_id),
                local_user_id=chat.local_user_id,
                session_id=chat.session_id,
                unfinished_runs=unfinished_runs,
                artifact_storage_paths=artifact_storage_paths,
            )

    def delete_chat_cascade(self, chat_id: UUID) -> None:
        """対象チャット一式をメモリ上から削除する。"""
        with self._lock:
            chat = self._get_chat_locked(chat_id)
            for run_id in chat.run_ids:
                self._runs.pop(run_id, None)
            for reference_id, parent_chat_id in tuple(self._reference_chat_ids.items()):
                if parent_chat_id == chat_id:
                    self._reference_chat_ids.pop(reference_id, None)
                    self._references.pop(reference_id, None)
            for artifact_id, parent_chat_id in tuple(self._artifact_chat_ids.items()):
                if parent_chat_id == chat_id:
                    self._artifact_chat_ids.pop(artifact_id, None)
                    self._artifacts.pop(artifact_id, None)
                    if self._latest_artifact_id == artifact_id:
                        self._latest_artifact_id = None
            self._chats.pop(chat_id, None)

    def chat_state_for_test(self, chat_id: UUID) -> ChatState:
        """テストでチャット状態を返す。"""
        with self._lock:
            return self._get_chat_locked(chat_id).chat_state

    def save_completed_answer_for_test(
        self,
        markdown: str,
        reference_relative_path: str,
        artifact_relative_path: str,
        artifact_mime_type: str,
        user_id: str = "demo-user",
    ) -> UUID:
        """テスト用に採用済み回答、参照元、成果物メタ情報を登録する。"""
        with self._lock:
            accepted = self.create_chat_with_first_run("回答済み確認", user_id=user_id)
            run = self._runs[accepted.run_id]
            reference_id = uuid4()
            artifact_id = uuid4()
            reference = DisplayReferenceData(
                reference_id=reference_id,
                source_type=SourceType.PDF,
                label="資料",
                relative_path=reference_relative_path,
                page_start=1,
                page_end=1,
            )
            artifact = ArtifactData(
                artifact_id=artifact_id,
                mime_type=artifact_mime_type,
                relative_path=artifact_relative_path,
            )
            run.state = RunState.COMPLETED
            run.answer = AnswerData(
                blocks=(
                    AnswerBlockData(
                        markdown=markdown,
                        references=(reference,),
                        artifacts=(artifact,),
                    ),
                ),
            )
            self._references[reference_id] = reference
            self._artifacts[artifact_id] = artifact
            self._reference_chat_ids[reference_id] = accepted.chat_id
            self._artifact_chat_ids[artifact_id] = accepted.chat_id
            self._latest_artifact_id = artifact_id
            return reference_id

    def latest_artifact_id_for_test(self) -> UUID:
        """テストで直近登録した成果物IDを返す。"""
        if self._latest_artifact_id is None:
            raise ArtifactNotFoundError()
        return self._latest_artifact_id

    def run_execution_deadline_for_test(
        self, chat_id: UUID, run_id: UUID
    ) -> datetime | None:
        """テストでrunの実行deadlineを返す。"""
        with self._lock:
            run = self._get_run_locked(chat_id, run_id)
            return run.execution_deadline_at

    def _to_history_item(self, chat: _ChatRecord) -> HistoryItem:
        latest_run = max(
            (self._runs[run_id] for run_id in chat.run_ids),
            key=lambda run: run.started_at,
        )
        return HistoryItem(
            chat_id=chat.id,
            title=chat.title,
            latest_run_id=latest_run.id,
            latest_state=latest_run.state,
            updated_at=chat.updated_at,
        )

    def _to_run_detail(self, run: _RunRecord) -> RunDetail:
        return RunDetail(
            run_id=run.id,
            state=run.state,
            user_instruction=run.user_instruction,
            intermediate_messages=tuple(run.intermediate_messages),
            answer=run.answer,
            user_message=run.user_message,
        )

    def _get_chat_locked(self, chat_id: UUID, user_id: str = "") -> _ChatRecord:
        chat = self._chats.get(chat_id)
        if chat is None or (user_id and chat.user_id != user_id):
            raise ChatNotFoundError()
        return chat

    def _get_user_locked(self, user_id: str) -> AccountUserData:
        user = self._users.get(user_id)
        if user is None:
            raise ChatNotFoundError()
        return user

    def _get_active_chat_locked(self, chat_id: UUID, user_id: str = "") -> _ChatRecord:
        chat = self._get_chat_locked(chat_id, user_id=user_id)
        if chat.chat_state is ChatState.DELETING:
            raise ChatDeletingError()
        return chat

    def _raise_if_deleting(self, chat_id: UUID) -> None:
        chat = self._get_chat_locked(chat_id)
        if chat.chat_state is ChatState.DELETING:
            raise ChatDeletingError()

    def _get_run_locked(self, chat_id: UUID, run_id: UUID) -> _RunRecord:
        self._get_chat_locked(chat_id)
        run = self._runs.get(run_id)
        if run is None or run.chat_id != chat_id:
            raise RunNotFoundError()
        return run

    def _now(self) -> datetime:
        if self._now_values:
            return self._now_values.pop(0)
        return datetime.now(UTC)


def _user_instruction(user_instruction: str) -> UserInstruction:
    try:
        return UserInstruction(user_instruction)
    except InvalidUserInstructionError as exc:
        raise UserInstructionRequiredError() from exc

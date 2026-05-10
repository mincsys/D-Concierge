from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from uuid import UUID, uuid4

from backend.application.ports.database.dto import (
    SHARED_LOCAL_USER_ID,
    AcceptedRun,
    AnswerBlockData,
    AnswerData,
    ArtifactData,
    ChatDetail,
    ChatRuntimeContext,
    DisplayReferenceData,
    HistoryItem,
    IntermediateMessageData,
    RunDetail,
    UnfinishedRun,
)
from backend.domain.execution.run_state_policy import RunState, RunStatePolicy
from backend.shared.errors import AppError, ErrorClass


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
    local_user_id: UUID
    session_id: UUID
    title: str
    updated_at: datetime
    generation_conversation_id: str | None = None
    validation_conversation_id: str | None = None
    run_ids: list[UUID] = field(default_factory=list)


class InMemoryChatRepository:
    """チャット関連データをメモリ上に保持するRepository実装。"""

    def __init__(self, now_values: Iterable[datetime] = ()) -> None:
        self._now_values = list(now_values)
        self._chats: dict[UUID, _ChatRecord] = {}
        self._runs: dict[UUID, _RunRecord] = {}
        self._references: dict[UUID, DisplayReferenceData] = {}
        self._artifacts: dict[UUID, ArtifactData] = {}
        self._latest_artifact_id: UUID | None = None
        self._lock = RLock()

    def create_chat_with_first_run(self, user_instruction: str) -> AcceptedRun:
        """新規チャット、初回run、初回指示を同時に保存する。"""
        instruction = _normalize_instruction(user_instruction)
        now = self._now()
        chat_id = uuid4()
        run_id = uuid4()
        chat = _ChatRecord(
            id=chat_id,
            local_user_id=SHARED_LOCAL_USER_ID,
            session_id=uuid4(),
            title=_make_title(instruction),
            updated_at=now,
            run_ids=[run_id],
        )
        run = _RunRecord(
            id=run_id,
            chat_id=chat_id,
            state="受付",
            started_at=now,
            user_instruction=instruction,
        )
        with self._lock:
            self._chats[chat_id] = chat
            self._runs[run_id] = run
        return AcceptedRun(chat_id=chat_id, run_id=run_id, state="受付")

    def append_run(self, chat_id: UUID, user_instruction: str) -> AcceptedRun:
        """既存チャットへ受付runと指示を追加する。"""
        instruction = _normalize_instruction(user_instruction)
        now = self._now()
        run_id = uuid4()
        with self._lock:
            chat = self._get_chat_locked(chat_id)
            for existing_run_id in chat.run_ids:
                if RunStatePolicy.is_unfinished(self._runs[existing_run_id].state):
                    raise AppError(
                        ErrorClass.CONFLICT, "実行中の処理があるため送信できません。"
                    )
            run = _RunRecord(
                id=run_id,
                chat_id=chat_id,
                state="受付",
                started_at=now,
                user_instruction=instruction,
            )
            chat.run_ids.append(run_id)
            chat.updated_at = now
            self._runs[run_id] = run
        return AcceptedRun(chat_id=chat_id, run_id=run_id, state="受付")

    def list_histories(self) -> tuple[HistoryItem, ...]:
        """チャット履歴を更新日時降順で返す。"""
        with self._lock:
            histories = [
                self._to_history_item(chat)
                for chat in self._chats.values()
                if len(chat.run_ids) > 0
            ]
        return tuple(sorted(histories, key=lambda item: item.updated_at, reverse=True))

    def list_unfinished_runs_for_recovery(self) -> tuple[UnfinishedRun, ...]:
        """起動時回復対象の未完了runを開始日時順で返す。"""
        with self._lock:
            runs = [
                run
                for run in self._runs.values()
                if RunStatePolicy.is_unfinished(run.state)
            ]
        return tuple(
            UnfinishedRun(chat_id=run.chat_id, run_id=run.id, state=run.state)
            for run in sorted(runs, key=lambda item: (item.started_at, str(item.id)))
        )

    def get_chat_detail(self, chat_id: UUID) -> ChatDetail:
        """指定チャットの詳細を返す。"""
        with self._lock:
            chat = self._get_chat_locked(chat_id)
            runs = tuple(
                self._to_run_detail(self._runs[run_id])
                for run_id in sorted(
                    chat.run_ids,
                    key=lambda item: (self._runs[item].started_at, str(item)),
                )
            )
            return ChatDetail(chat_id=chat.id, title=chat.title, runs=runs)

    def get_chat_runtime_context(self, chat_id: UUID) -> ChatRuntimeContext:
        """Codex実行に必要なチャット単位の内部コンテキストを返す。"""
        with self._lock:
            chat = self._get_chat_locked(chat_id)
            return ChatRuntimeContext(
                chat_id=chat.id,
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
                for artifact in block.artifacts:
                    self._artifacts[artifact.artifact_id] = artifact
                    self._latest_artifact_id = artifact.artifact_id
            self._chats[chat_id].updated_at = now

    def cancel_run(self, chat_id: UUID, run_id: UUID) -> None:
        """対象runをキャンセル要求中経由でキャンセル済みにする。"""
        now = self._now()
        with self._lock:
            run = self._get_run_locked(chat_id, run_id)
            if not RunStatePolicy.is_cancelable(run.state):
                raise AppError(ErrorClass.CONFLICT, "この処理はキャンセルできません。")
            run.state = "キャンセル要求中"
            run.user_message = "処理をキャンセルしています。"
            run.state = "キャンセル済み"
            run.user_message = "処理をキャンセルしました。"
            self._chats[chat_id].updated_at = now

    def get_reference(self, reference_id: UUID) -> DisplayReferenceData:
        """参照元IDに対応する配信メタ情報を返す。"""
        reference = self._references.get(reference_id)
        if reference is None:
            raise AppError(ErrorClass.NOT_FOUND, "対象の参照元が見つかりません。")
        return reference

    def get_artifact(self, artifact_id: UUID) -> ArtifactData:
        """成果物IDに対応する配信メタ情報を返す。"""
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            raise AppError(ErrorClass.NOT_FOUND, "対象の成果物が見つかりません。")
        return artifact

    def save_completed_answer_for_test(
        self,
        markdown: str,
        reference_relative_path: str,
        artifact_relative_path: str,
        artifact_mime_type: str,
    ) -> UUID:
        """テスト用に採用済み回答、参照元、成果物メタ情報を登録する。"""
        with self._lock:
            accepted = self.create_chat_with_first_run("回答済み確認")
            run = self._runs[accepted.run_id]
            reference_id = uuid4()
            artifact_id = uuid4()
            reference = DisplayReferenceData(
                reference_id=reference_id,
                source_type="pdf",
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
            run.state = "完了"
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
            self._latest_artifact_id = artifact_id
            return reference_id

    def latest_artifact_id_for_test(self) -> UUID:
        """テストで直近登録した成果物IDを返す。"""
        if self._latest_artifact_id is None:
            raise AppError(ErrorClass.NOT_FOUND, "対象の成果物が見つかりません。")
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

    def _get_chat_locked(self, chat_id: UUID) -> _ChatRecord:
        chat = self._chats.get(chat_id)
        if chat is None:
            raise AppError(ErrorClass.NOT_FOUND, "対象のチャットが見つかりません。")
        return chat

    def _get_run_locked(self, chat_id: UUID, run_id: UUID) -> _RunRecord:
        self._get_chat_locked(chat_id)
        run = self._runs.get(run_id)
        if run is None or run.chat_id != chat_id:
            raise AppError(ErrorClass.NOT_FOUND, "対象の実行処理が見つかりません。")
        return run

    def _now(self) -> datetime:
        if self._now_values:
            return self._now_values.pop(0)
        return datetime.now(UTC)


def _normalize_instruction(user_instruction: str) -> str:
    instruction = user_instruction.strip()
    if instruction == "":
        raise AppError(ErrorClass.INPUT, "ユーザ指示を入力してください。")
    return instruction


def _make_title(user_instruction: str) -> str:
    normalized = " ".join(user_instruction.split())
    return normalized[:50]

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

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
from backend.application.ports.runtime.interface import ClockPort, IdGeneratorPort
from backend.domain.chat.chat_title_policy import ChatTitlePolicy
from backend.domain.chat.user_instruction import (
    InvalidUserInstructionError,
    UserInstruction,
)
from backend.domain.execution.run_state import RunState
from backend.domain.execution.run_state_policy import (
    UNFINISHED_STATES,
    RunStatePolicy,
)
from backend.domain.references.source_type import SourceType
from backend.infrastructure.database.models.answer import (
    AnswerBlockModel,
    ArtifactModel,
    ReferenceModel,
)
from backend.infrastructure.database.models.chat import (
    ChatModel,
    ChatRunModel,
    IntermediateMessageModel,
    LocalUserModel,
    UserInstructionModel,
)
from backend.infrastructure.runtime.system_clock import SystemClock
from backend.infrastructure.runtime.uuid_generator import UuidGenerator
from backend.shared.error_class import ErrorClass
from backend.shared.errors import AppError
from backend.shared.user_messages import (
    CANCEL_NOT_ALLOWED_MESSAGE,
    CANCELED_MESSAGE,
    USER_INSTRUCTION_REQUIRED_MESSAGE,
)


class SqlAlchemySessionProvider(Protocol):
    """現在のSQLAlchemy Sessionを提供する境界。"""

    def current_session(self) -> Session:
        """開始済みトランザクションのSessionを返す。"""


class SqlAlchemyChatRepository:
    """SQLAlchemyでチャット関連データを永続化するRepository実装。"""

    def __init__(
        self,
        session_provider: SqlAlchemySessionProvider,
        clock: ClockPort | None = None,
        id_generator: IdGeneratorPort | None = None,
    ) -> None:
        self._session_provider = session_provider
        self._clock = clock if clock is not None else SystemClock()
        self._id_generator = (
            id_generator if id_generator is not None else UuidGenerator()
        )

    def _session(self) -> Session:
        return self._session_provider.current_session()

    def create_chat_with_first_run(self, user_instruction: str) -> AcceptedRun:
        """新規チャット、初回run、初回指示を同一トランザクションで保存する。"""
        instruction = _user_instruction(user_instruction)
        now = self._clock.now()
        chat_id = self._id_generator.new_uuid()
        run_id = self._id_generator.new_uuid()
        session = self._session()
        self._ensure_shared_user(session)
        session.flush()
        session.add(
            ChatModel(
                id=chat_id,
                local_user_id=SHARED_LOCAL_USER_ID,
                session_id=self._id_generator.new_uuid(),
                title=ChatTitlePolicy.make_title(instruction),
                updated_at=now,
            )
        )
        session.flush()
        session.add(
            ChatRunModel(
                id=run_id,
                chat_id=chat_id,
                state=RunState.ACCEPTED.value,
                started_at=now,
            )
        )
        session.flush()
        session.add(
            UserInstructionModel(
                id=self._id_generator.new_uuid(),
                run_id=run_id,
                body=instruction.body,
            )
        )
        return AcceptedRun(chat_id=chat_id, run_id=run_id, state=RunState.ACCEPTED)

    def append_run(self, chat_id: UUID, user_instruction: str) -> AcceptedRun:
        """既存チャットへ受付runと指示を追加する。"""
        instruction = _user_instruction(user_instruction)
        now = self._clock.now()
        run_id = self._id_generator.new_uuid()
        session = self._session()
        chat = self._get_chat(session, chat_id)
        unfinished = session.scalar(
            sa.select(ChatRunModel).where(
                ChatRunModel.chat_id == chat_id,
                ChatRunModel.state.in_(
                    tuple(state.value for state in UNFINISHED_STATES)
                ),
            )
        )
        if unfinished is not None:
            raise AppError(
                ErrorClass.CONFLICT,
                "実行中の処理があるため送信できません。",
            )
        chat.updated_at = now
        session.add(
            ChatRunModel(
                id=run_id,
                chat_id=chat_id,
                state=RunState.ACCEPTED.value,
                started_at=now,
            )
        )
        session.flush()
        session.add(
            UserInstructionModel(
                id=self._id_generator.new_uuid(),
                run_id=run_id,
                body=instruction.body,
            )
        )
        return AcceptedRun(chat_id=chat_id, run_id=run_id, state=RunState.ACCEPTED)

    def list_histories(self) -> tuple[HistoryItem, ...]:
        """チャット履歴を更新日時降順で返す。"""
        session = self._session()
        chats = session.scalars(
            sa.select(ChatModel).order_by(ChatModel.updated_at.desc())
        ).all()
        histories = [self._to_history_item(session, chat) for chat in chats]
        return tuple(
            history for history in histories if history.latest_run_id is not None
        )

    def list_unfinished_runs_for_recovery(self) -> tuple[UnfinishedRun, ...]:
        """起動時回復対象の未完了runを開始日時順で返す。"""
        session = self._session()
        runs = session.scalars(
            sa.select(ChatRunModel)
            .where(
                ChatRunModel.state.in_(
                    tuple(state.value for state in UNFINISHED_STATES)
                )
            )
            .order_by(ChatRunModel.started_at, ChatRunModel.id)
        ).all()
        return tuple(
            UnfinishedRun(chat_id=run.chat_id, run_id=run.id, state=_run_state(run))
            for run in runs
        )

    def get_chat_detail(self, chat_id: UUID) -> ChatDetail:
        """指定チャットの詳細を返す。"""
        session = self._session()
        chat = self._get_chat(session, chat_id)
        runs = session.scalars(
            sa.select(ChatRunModel)
            .where(ChatRunModel.chat_id == chat_id)
            .order_by(ChatRunModel.started_at, ChatRunModel.id)
        ).all()
        return ChatDetail(
            chat_id=chat.id,
            title=chat.title,
            runs=tuple(self._to_run_detail(session, run) for run in runs),
        )

    def get_chat_runtime_context(self, chat_id: UUID) -> ChatRuntimeContext:
        """Codex実行に必要なチャット単位の内部コンテキストを返す。"""
        session = self._session()
        chat = self._get_chat(session, chat_id)
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
        session = self._session()
        chat = self._get_chat(session, chat_id)
        chat.generation_conversation_id = codex_conversation_id

    def save_validation_conversation_id(
        self, chat_id: UUID, codex_conversation_id: str
    ) -> None:
        """検証用Codex側resume IDを保存する。"""
        session = self._session()
        chat = self._get_chat(session, chat_id)
        chat.validation_conversation_id = codex_conversation_id

    def get_run_state(self, chat_id: UUID, run_id: UUID) -> RunState:
        """SSE初期通知用に現在状態を返す。"""
        session = self._session()
        run = self._get_run(session, chat_id, run_id)
        return _run_state(run)

    def get_run_instruction(self, chat_id: UUID, run_id: UUID) -> str:
        """実行対象runのユーザ指示を返す。"""
        session = self._session()
        self._get_run(session, chat_id, run_id)
        return self._get_instruction(session, run_id).body

    def set_run_state(
        self,
        chat_id: UUID,
        run_id: UUID,
        state: RunState,
        user_message: str | None = None,
    ) -> None:
        """実行対象runの状態と利用者向けメッセージを更新する。"""
        now = self._clock.now()
        session = self._session()
        run = self._get_run(session, chat_id, run_id)
        run.state = state.value
        run.user_message = user_message
        if RunStatePolicy.is_terminal(state):
            run.ended_at = now
        chat = self._get_chat(session, chat_id)
        chat.updated_at = now

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
        now = self._clock.now()
        session = self._session()
        run = self._get_run(session, chat_id, run_id)
        if _run_state(run) not in expected_states:
            return False
        run.state = state.value
        run.user_message = user_message
        if execution_deadline_at is not None:
            run.execution_deadline_at = execution_deadline_at
        if RunStatePolicy.is_terminal(state):
            run.ended_at = now
        chat = self._get_chat(session, chat_id)
        chat.updated_at = now
        return True

    def add_intermediate_message(self, chat_id: UUID, run_id: UUID, text: str) -> None:
        """実行対象runへ中間メッセージを追加する。"""
        now = self._clock.now()
        session = self._session()
        self._get_run(session, chat_id, run_id)
        session.add(
            IntermediateMessageModel(
                id=self._id_generator.new_uuid(),
                run_id=run_id,
                body=text,
                created_at=now,
            )
        )
        chat = self._get_chat(session, chat_id)
        chat.updated_at = now

    def save_completed_answer(
        self,
        chat_id: UUID,
        run_id: UUID,
        answer: AnswerData,
    ) -> None:
        """実行対象runへ検証済み回答と表示用メタ情報を保存する。"""
        now = self._clock.now()
        session = self._session()
        self._get_run(session, chat_id, run_id)
        for block_position, block in enumerate(answer.blocks, start=1):
            block_id = self._id_generator.new_uuid()
            session.add(
                AnswerBlockModel(
                    id=block_id,
                    run_id=run_id,
                    position=block_position,
                    markdown=block.markdown,
                )
            )
            session.flush()
            for reference_position, reference in enumerate(
                block.references,
                start=1,
            ):
                session.add(
                    ReferenceModel(
                        id=reference.reference_id,
                        answer_block_id=block_id,
                        position=reference_position,
                        source_type=reference.source_type.value,
                        label=reference.label,
                        locator={
                            "path": reference.relative_path,
                            "page_start": reference.page_start,
                            "page_end": reference.page_end,
                        },
                    )
                )
            for artifact in block.artifacts:
                session.add(
                    ArtifactModel(
                        id=artifact.artifact_id,
                        answer_block_id=block_id,
                        mime_type=artifact.mime_type,
                        storage_path=artifact.relative_path,
                        created_at=now,
                    )
                )
        chat = self._get_chat(session, chat_id)
        chat.updated_at = now

    def cancel_run(self, chat_id: UUID, run_id: UUID) -> None:
        """対象runをキャンセル要求中経由でキャンセル済みにする。"""
        now = self._clock.now()
        session = self._session()
        run = self._get_run(session, chat_id, run_id)
        if not RunStatePolicy.is_cancelable(_run_state(run)):
            raise AppError(ErrorClass.CONFLICT, CANCEL_NOT_ALLOWED_MESSAGE)
        run.state = RunState.CANCELED.value
        run.user_message = CANCELED_MESSAGE
        chat = self._get_chat(session, chat_id)
        chat.updated_at = now

    def get_reference(self, reference_id: UUID) -> DisplayReferenceData:
        """参照元IDに対応する配信メタ情報を返す。"""
        session = self._session()
        reference = session.get(ReferenceModel, reference_id)
        if reference is None:
            raise AppError(ErrorClass.NOT_FOUND, "対象の参照元が見つかりません。")
        path_value = reference.locator.get("path")
        page_start_value = reference.locator.get("page_start")
        page_end_value = reference.locator.get("page_end")
        if (
            not isinstance(path_value, str)
            or not isinstance(page_start_value, int)
            or not isinstance(page_end_value, int)
        ):
            raise AppError(ErrorClass.SYSTEM, "参照元データが不整合です。")
        return DisplayReferenceData(
            reference_id=reference.id,
            source_type=_source_type(reference.source_type),
            label=reference.label,
            relative_path=path_value,
            page_start=page_start_value,
            page_end=page_end_value,
        )

    def get_artifact(self, artifact_id: UUID) -> ArtifactData:
        """成果物IDに対応する配信メタ情報を返す。"""
        session = self._session()
        artifact = session.get(ArtifactModel, artifact_id)
        if artifact is None:
            raise AppError(ErrorClass.NOT_FOUND, "対象の成果物が見つかりません。")
        return ArtifactData(
            artifact_id=artifact.id,
            mime_type=artifact.mime_type,
            relative_path=artifact.storage_path,
        )

    def _to_history_item(self, session: Session, chat: ChatModel) -> HistoryItem:
        latest_run = session.scalar(
            sa.select(ChatRunModel)
            .where(ChatRunModel.chat_id == chat.id)
            .order_by(ChatRunModel.started_at.desc(), ChatRunModel.id.desc())
        )
        return HistoryItem(
            chat_id=chat.id,
            title=chat.title,
            latest_run_id=latest_run.id if latest_run is not None else None,
            latest_state=(
                _run_state(latest_run) if latest_run is not None else RunState.ACCEPTED
            ),
            updated_at=chat.updated_at,
        )

    def _to_run_detail(self, session: Session, run: ChatRunModel) -> RunDetail:
        instruction = self._get_instruction(session, run.id)
        messages = session.scalars(
            sa.select(IntermediateMessageModel)
            .where(IntermediateMessageModel.run_id == run.id)
            .order_by(IntermediateMessageModel.created_at, IntermediateMessageModel.id)
        ).all()
        blocks = session.scalars(
            sa.select(AnswerBlockModel)
            .where(AnswerBlockModel.run_id == run.id)
            .order_by(AnswerBlockModel.position, AnswerBlockModel.id)
        ).all()
        return RunDetail(
            run_id=run.id,
            state=_run_state(run),
            user_instruction=instruction.body,
            intermediate_messages=tuple(
                IntermediateMessageData(text=message.body) for message in messages
            ),
            answer=self._to_answer_data(session, blocks) if blocks else None,
            user_message=run.user_message,
        )

    def _to_answer_data(
        self,
        session: Session,
        blocks: Sequence[AnswerBlockModel],
    ) -> AnswerData:
        return AnswerData(
            blocks=tuple(
                self._to_answer_block_data(session, block) for block in blocks
            ),
        )

    def _to_answer_block_data(
        self,
        session: Session,
        block: AnswerBlockModel,
    ) -> AnswerBlockData:
        references = session.scalars(
            sa.select(ReferenceModel)
            .where(ReferenceModel.answer_block_id == block.id)
            .order_by(ReferenceModel.position, ReferenceModel.id)
        ).all()
        artifacts = session.scalars(
            sa.select(ArtifactModel)
            .where(ArtifactModel.answer_block_id == block.id)
            .order_by(ArtifactModel.created_at, ArtifactModel.id)
        ).all()
        return AnswerBlockData(
            markdown=block.markdown,
            references=tuple(
                self._to_reference_data(reference) for reference in references
            ),
            artifacts=tuple(
                ArtifactData(
                    artifact_id=artifact.id,
                    mime_type=artifact.mime_type,
                    relative_path=artifact.storage_path,
                )
                for artifact in artifacts
            ),
        )

    def _to_reference_data(self, reference: ReferenceModel) -> DisplayReferenceData:
        path_value = reference.locator.get("path")
        page_start_value = reference.locator.get("page_start")
        page_end_value = reference.locator.get("page_end")
        if (
            not isinstance(path_value, str)
            or not isinstance(page_start_value, int)
            or not isinstance(page_end_value, int)
        ):
            raise AppError(ErrorClass.SYSTEM, "参照元データが不整合です。")
        return DisplayReferenceData(
            reference_id=reference.id,
            source_type=_source_type(reference.source_type),
            label=reference.label,
            relative_path=path_value,
            page_start=page_start_value,
            page_end=page_end_value,
        )

    def _ensure_shared_user(self, session: Session) -> None:
        user = session.get(LocalUserModel, SHARED_LOCAL_USER_ID)
        if user is None:
            session.add(
                LocalUserModel(
                    id=SHARED_LOCAL_USER_ID,
                    display_name="共有利用者",
                    is_active=True,
                )
            )

    def _get_chat(self, session: Session, chat_id: UUID) -> ChatModel:
        chat = session.get(ChatModel, chat_id)
        if chat is None:
            raise AppError(ErrorClass.NOT_FOUND, "対象のチャットが見つかりません。")
        return chat

    def _get_run(self, session: Session, chat_id: UUID, run_id: UUID) -> ChatRunModel:
        self._get_chat(session, chat_id)
        run = session.get(ChatRunModel, run_id)
        if run is None or run.chat_id != chat_id:
            raise AppError(ErrorClass.NOT_FOUND, "対象の実行処理が見つかりません。")
        return run

    def _get_instruction(self, session: Session, run_id: UUID) -> UserInstructionModel:
        instruction = session.scalar(
            sa.select(UserInstructionModel).where(UserInstructionModel.run_id == run_id)
        )
        if instruction is None:
            raise AppError(ErrorClass.SYSTEM, "履歴データが不整合です。")
        return instruction


def _user_instruction(user_instruction: str) -> UserInstruction:
    try:
        return UserInstruction(user_instruction)
    except InvalidUserInstructionError as exc:
        raise AppError(ErrorClass.INPUT, USER_INSTRUCTION_REQUIRED_MESSAGE) from exc


def _run_state(run: ChatRunModel) -> RunState:
    try:
        return RunState(run.state)
    except ValueError as exc:
        raise AppError(ErrorClass.SYSTEM, "履歴データが不整合です。") from exc


def _source_type(value: str) -> SourceType:
    try:
        return SourceType(value)
    except ValueError as exc:
        raise AppError(ErrorClass.SYSTEM, "参照元データが不整合です。") from exc

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid7

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.application.ports.database.dto import (
    AcceptedRun,
    AnswerBlockData,
    AnswerData,
    ArtifactData,
    CancelRunTarget,
    ChatDeletionTarget,
    ChatDetail,
    ChatRunData,
    ChatRuntimeContext,
    DisplayReferenceData,
    HistoryItem,
    IntermediateMessageData,
    SseRunSnapshot,
    UnfinishedRun,
)
from backend.domain.chat.chat_state import ChatState
from backend.domain.execution.run_state import RunState
from backend.infrastructure.database.models.answer import (
    AnswerBlockModel,
    ArtifactModel,
    ReferenceModel,
)
from backend.infrastructure.database.models.chat import (
    ChatModel,
    ChatRunModel,
    IntermediateMessageModel,
    UserInstructionModel,
)
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.shared.user_messages import SYSTEM_ERROR

UNFINISHED_RUN_STATES = (
    RunState.ACCEPTED.value,
    RunState.RUNNING.value,
    RunState.VALIDATING.value,
    RunState.CANCEL_REQUESTED.value,
)


@dataclass(slots=True)
class SqlAlchemyChatRepository:
    """チャット関連RepositoryのSQLAlchemy実装。"""

    session: Session

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
    ) -> AcceptedRun:
        try:
            chat = ChatModel(
                id=chat_id,
                user_id=user_id,
                session_id=session_id,
                chat_state=ChatState.ACTIVE.value,
                title=title,
                generation_conversation_id=None,
                validation_conversation_id=None,
                updated_at=started_at,
            )
            run = ChatRunModel(
                id=run_id,
                chat_id=chat_id,
                state=RunState.ACCEPTED.value,
                started_at=started_at,
                execution_deadline_at=None,
                ended_at=None,
                user_message=None,
            )
            instruction = UserInstructionModel(
                id=session_id,
                run_id=run_id,
                body=user_instruction,
            )
            self.session.add_all([chat, run, instruction])
            self.session.flush()
        except IntegrityError as error:
            raise _integrity_error(error) from error
        return AcceptedRun(
            run_id=run_id,
            chat_id=chat_id,
            user_id=user_id,
            session_id=session_id,
            state=RunState.ACCEPTED.value,
            started_at=started_at,
        )

    def append_run(
        self,
        user_id: str,
        chat_id: UUID,
        run_id: UUID,
        user_instruction: str,
        trace_id: str,
        started_at: datetime,
    ) -> AcceptedRun:
        chat = self.session.get(ChatModel, chat_id)
        if chat is None or chat.user_id != user_id:
            raise AppError(
                error_type=ErrorType.NOT_FOUND,
                trace=False,
                diagnostic_message="対象チャットが見つかりません。",
            )
        if chat.chat_state == ChatState.DELETING.value:
            raise AppError(
                error_type=ErrorType.CONFLICT,
                trace=False,
                diagnostic_message="削除中のチャットです。",
            )
        if self._has_unfinished_run(chat_id):
            raise AppError(
                error_type=ErrorType.CONFLICT,
                trace=False,
                diagnostic_message="未完了のチャット実行処理があります。",
            )

        try:
            run = ChatRunModel(
                id=run_id,
                chat_id=chat_id,
                state=RunState.ACCEPTED.value,
                started_at=started_at,
                execution_deadline_at=None,
                ended_at=None,
                user_message=None,
            )
            instruction = UserInstructionModel(
                id=run_id,
                run_id=run_id,
                body=user_instruction,
            )
            chat.updated_at = started_at
            self.session.add_all([run, instruction])
            self.session.flush()
        except IntegrityError as error:
            raise _integrity_error(error) from error
        return AcceptedRun(
            run_id=run_id,
            chat_id=chat_id,
            user_id=user_id,
            session_id=chat.session_id,
            state=RunState.ACCEPTED.value,
            started_at=started_at,
        )

    def mark_run_error(self, run_id: UUID, diagnostic_message: str) -> None:
        run = self.session.get(ChatRunModel, run_id)
        if run is None:
            return
        run.state = RunState.ERROR.value
        run.user_message = diagnostic_message or SYSTEM_ERROR
        run.ended_at = datetime.now(UTC)
        self.session.flush()

    def mark_run_running(
        self,
        run_id: UUID,
        execution_deadline_at: datetime | None = None,
    ) -> None:
        run = self.session.get(ChatRunModel, run_id)
        if run is None:
            return
        run.state = RunState.RUNNING.value
        run.execution_deadline_at = execution_deadline_at
        self.session.flush()

    def mark_run_validating(self, run_id: UUID) -> None:
        run = self.session.get(ChatRunModel, run_id)
        if run is None:
            return
        run.state = RunState.VALIDATING.value
        self.session.flush()

    def mark_run_completed(self, run_id: UUID) -> None:
        run = self.session.get(ChatRunModel, run_id)
        if run is None:
            return
        run.state = RunState.COMPLETED.value
        run.ended_at = datetime.now(UTC)
        self.session.flush()

    def mark_run_timed_out(self, run_id: UUID) -> None:
        run = self.session.get(ChatRunModel, run_id)
        if run is None:
            return
        run.state = RunState.TIMED_OUT.value
        run.user_message = "処理がタイムアウトしました。"
        run.ended_at = datetime.now(UTC)
        self.session.flush()

    def save_intermediate_message(self, run_id: UUID, text: str) -> None:
        self.session.add(
            IntermediateMessageModel(
                id=uuid7(),
                run_id=run_id,
                body=text,
                created_at=datetime.now(UTC),
            )
        )
        self.session.flush()

    def save_conversation_ids(
        self,
        chat_id: UUID,
        generation_conversation_id: str | None,
        validation_conversation_id: str | None,
    ) -> None:
        chat = self.session.get(ChatModel, chat_id)
        if chat is None:
            return
        chat.generation_conversation_id = generation_conversation_id
        chat.validation_conversation_id = validation_conversation_id
        self.session.flush()

    def load_runtime_context(self, chat_id: UUID) -> ChatRuntimeContext | None:
        row = self.session.execute(
            select(ChatRunModel, ChatModel, UserInstructionModel)
            .join(ChatModel, ChatModel.id == ChatRunModel.chat_id)
            .join(UserInstructionModel, UserInstructionModel.run_id == ChatRunModel.id)
            .where(ChatModel.id == chat_id)
            .order_by(ChatRunModel.started_at.desc(), ChatRunModel.id.desc())
            .limit(1)
        ).one_or_none()
        if row is None:
            return None
        _run, chat, instruction = row
        return ChatRuntimeContext(
            chat_id=chat.id,
            user_id=chat.user_id,
            session_id=chat.session_id,
            generation_conversation_id=chat.generation_conversation_id,
            validation_conversation_id=chat.validation_conversation_id,
            user_instruction=instruction.body,
        )

    def save_answers(self, run_id: UUID, answers: tuple[AnswerData, ...]) -> None:
        for answer in answers:
            for block in answer.blocks:
                self.session.add(
                    AnswerBlockModel(
                        id=block.answer_block_id,
                        run_id=run_id,
                        position=block.position,
                        markdown=block.markdown,
                    )
                )
                for reference in block.references:
                    self.session.add(
                        ReferenceModel(
                            id=reference.reference_id,
                            answer_block_id=block.answer_block_id,
                            position=reference.position,
                            source_type=reference.source_type,
                            label=reference.label,
                            locator={
                                "path": reference.path,
                                "page_start": reference.page_start,
                                "page_end": reference.page_end,
                            },
                        )
                    )
                for artifact in block.artifacts:
                    self.session.add(
                        ArtifactModel(
                            id=artifact.artifact_id,
                            answer_block_id=block.answer_block_id,
                            mime_type=artifact.mime_type,
                            storage_path=artifact.storage_path,
                            created_at=artifact.created_at,
                        )
                    )
        self.session.flush()

    def list_unfinished_runs(self) -> tuple[UnfinishedRun, ...]:
        return self.list_unfinished_runs_for_recovery()

    def list_unfinished_runs_for_recovery(self) -> tuple[UnfinishedRun, ...]:
        rows = self.session.execute(
            select(ChatRunModel, ChatModel)
            .join(ChatModel, ChatModel.id == ChatRunModel.chat_id)
            .where(
                ChatRunModel.state.in_(UNFINISHED_RUN_STATES),
                ChatModel.chat_state == ChatState.ACTIVE.value,
            )
            .order_by(ChatRunModel.started_at, ChatRunModel.id)
        ).all()
        return tuple(
            UnfinishedRun(
                run_id=run.id,
                chat_id=chat.id,
                user_id=chat.user_id,
                session_id=chat.session_id,
                state=run.state,
                started_at=run.started_at,
            )
            for run, chat in rows
        )

    def get_cancel_target(
        self,
        user_id: str,
        chat_id: UUID,
        run_id: UUID,
    ) -> CancelRunTarget | None:
        row = self.session.execute(
            select(ChatRunModel, ChatModel)
            .join(ChatModel, ChatModel.id == ChatRunModel.chat_id)
            .where(
                ChatModel.user_id == user_id,
                ChatModel.id == chat_id,
                ChatRunModel.id == run_id,
            )
            .limit(1)
        ).one_or_none()
        if row is None:
            return None
        run, chat = row
        return CancelRunTarget(
            user_id=chat.user_id,
            chat_id=chat.id,
            run_id=run.id,
            state=run.state,
            chat_state=chat.chat_state,
        )

    def update_run_state_if_current(
        self,
        run_id: UUID,
        expected_state: str,
        next_state: str,
        user_message: str | None = None,
    ) -> bool:
        run = self.session.execute(
            select(ChatRunModel)
            .where(ChatRunModel.id == run_id, ChatRunModel.state == expected_state)
            .limit(1)
        ).scalar_one_or_none()
        if run is None:
            return False
        run.state = next_state
        run.user_message = user_message
        self.session.flush()
        return True

    def request_cancel(self, run_id: UUID) -> bool:
        return self.update_run_state_if_current(
            run_id,
            RunState.RUNNING.value,
            RunState.CANCEL_REQUESTED.value,
        )

    def mark_chat_deleting(
        self,
        user_id: str,
        chat_id: UUID,
        updated_at: datetime,
    ) -> str | None:
        chat = self.session.get(ChatModel, chat_id)
        if chat is None or chat.user_id != user_id:
            return None
        chat.chat_state = ChatState.DELETING.value
        chat.updated_at = updated_at
        self.session.flush()
        return ChatState.DELETING.value

    def get_chat_deletion_target(self, chat_id: UUID) -> ChatDeletionTarget | None:
        chat = self.session.get(ChatModel, chat_id)
        if chat is None or chat.chat_state != ChatState.DELETING.value:
            return None
        unfinished_run_ids = tuple(
            self.session.execute(
                select(ChatRunModel.id)
                .where(
                    ChatRunModel.chat_id == chat_id,
                    ChatRunModel.state.in_(UNFINISHED_RUN_STATES),
                )
                .order_by(ChatRunModel.started_at, ChatRunModel.id)
            ).scalars()
        )
        storage_paths = tuple(
            self.session.execute(
                select(ArtifactModel.storage_path)
                .join(
                    AnswerBlockModel,
                    AnswerBlockModel.id == ArtifactModel.answer_block_id,
                )
                .join(ChatRunModel, ChatRunModel.id == AnswerBlockModel.run_id)
                .where(ChatRunModel.chat_id == chat_id)
                .order_by(ArtifactModel.created_at, ArtifactModel.id)
            ).scalars()
        )
        return ChatDeletionTarget(
            chat_id=chat.id,
            user_id=chat.user_id,
            session_id=chat.session_id,
            storage_paths=storage_paths,
            unfinished_run_ids=unfinished_run_ids,
        )

    def list_deleting_chats_for_recovery(self) -> tuple[UUID, ...]:
        return tuple(
            self.session.execute(
                select(ChatModel.id)
                .where(ChatModel.chat_state == ChatState.DELETING.value)
                .order_by(ChatModel.updated_at, ChatModel.id)
            ).scalars()
        )

    def delete_chat_cascade(self, chat_id: UUID) -> None:
        chat = self.session.get(ChatModel, chat_id)
        if chat is None:
            return
        try:
            self.session.delete(chat)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def list_histories(self, user_id: str) -> tuple[HistoryItem, ...]:
        chats = tuple(
            self.session.execute(
                select(ChatModel)
                .where(
                    ChatModel.user_id == user_id,
                    ChatModel.chat_state == ChatState.ACTIVE.value,
                )
                .order_by(ChatModel.updated_at.desc())
            ).scalars()
        )
        return tuple(self._history_item(chat) for chat in chats)

    def get_chat_detail(self, user_id: str, chat_id: UUID) -> ChatDetail | None:
        chat = self.session.get(ChatModel, chat_id)
        if chat is None or chat.user_id != user_id:
            return None
        if chat.chat_state == ChatState.DELETING.value:
            raise AppError(
                error_type=ErrorType.CONFLICT,
                trace=False,
                diagnostic_message="削除中のチャットです。",
            )
        runs = tuple(
            self.session.execute(
                select(ChatRunModel)
                .where(ChatRunModel.chat_id == chat_id)
                .order_by(ChatRunModel.started_at, ChatRunModel.id)
            ).scalars()
        )
        return ChatDetail(
            chat_id=chat.id,
            title=chat.title,
            runs=tuple(self._chat_run_data(run) for run in runs),
        )

    def get_run_state_for_sse(
        self,
        user_id: str,
        chat_id: UUID,
        run_id: UUID,
    ) -> SseRunSnapshot | None:
        row = self.session.execute(
            select(ChatRunModel, ChatModel)
            .join(ChatModel, ChatModel.id == ChatRunModel.chat_id)
            .where(
                ChatModel.user_id == user_id,
                ChatModel.id == chat_id,
                ChatRunModel.id == run_id,
            )
            .limit(1)
        ).one_or_none()
        if row is None:
            return None
        run, chat = row
        if chat.chat_state == ChatState.DELETING.value:
            raise AppError(
                error_type=ErrorType.CONFLICT,
                trace=False,
                diagnostic_message="削除中のチャットです。",
            )
        return SseRunSnapshot(
            chat_id=chat.id,
            run_id=run.id,
            state=run.state,
            chat_state=chat.chat_state,
            answer=self._answer_data(run.id),
            user_message=run.user_message,
        )

    def get_reference_for_delivery(
        self,
        user_id: str,
        reference_id: UUID,
    ) -> DisplayReferenceData | None:
        row = self.session.execute(
            select(ReferenceModel, ChatModel)
            .join(
                AnswerBlockModel,
                AnswerBlockModel.id == ReferenceModel.answer_block_id,
            )
            .join(ChatRunModel, ChatRunModel.id == AnswerBlockModel.run_id)
            .join(ChatModel, ChatModel.id == ChatRunModel.chat_id)
            .where(
                ReferenceModel.id == reference_id,
                ChatModel.user_id == user_id,
            )
            .limit(1)
        ).one_or_none()
        if row is None:
            return None
        reference, chat = row
        if chat.chat_state == ChatState.DELETING.value:
            raise AppError(
                error_type=ErrorType.CONFLICT,
                trace=False,
                diagnostic_message="削除中のチャットです。",
            )
        return _reference_data(reference)

    def get_artifact_for_delivery(
        self,
        user_id: str,
        artifact_id: UUID,
    ) -> ArtifactData | None:
        row = self.session.execute(
            select(ArtifactModel, ChatModel)
            .join(
                AnswerBlockModel,
                AnswerBlockModel.id == ArtifactModel.answer_block_id,
            )
            .join(ChatRunModel, ChatRunModel.id == AnswerBlockModel.run_id)
            .join(ChatModel, ChatModel.id == ChatRunModel.chat_id)
            .where(
                ArtifactModel.id == artifact_id,
                ChatModel.user_id == user_id,
            )
            .limit(1)
        ).one_or_none()
        if row is None:
            return None
        artifact, chat = row
        if chat.chat_state == ChatState.DELETING.value:
            raise AppError(
                error_type=ErrorType.CONFLICT,
                trace=False,
                diagnostic_message="削除中のチャットです。",
            )
        return ArtifactData(
            artifact_id=artifact.id,
            mime_type=artifact.mime_type,
            storage_path=artifact.storage_path,
            created_at=artifact.created_at,
        )

    def list_intermediate_messages_for_sse(
        self,
        run_id: UUID,
    ) -> tuple[IntermediateMessageData, ...]:
        messages = tuple(
            self.session.execute(
                select(IntermediateMessageModel)
                .where(IntermediateMessageModel.run_id == run_id)
                .order_by(
                    IntermediateMessageModel.created_at,
                    IntermediateMessageModel.id,
                )
            ).scalars()
        )
        return tuple(
            IntermediateMessageData(text=message.body, created_at=message.created_at)
            for message in messages
        )

    def _has_unfinished_run(self, chat_id: UUID) -> bool:
        run_id = self.session.execute(
            select(ChatRunModel.id)
            .where(
                ChatRunModel.chat_id == chat_id,
                ChatRunModel.state.in_(UNFINISHED_RUN_STATES),
            )
            .limit(1)
        ).scalar_one_or_none()
        return run_id is not None

    def _history_item(self, chat: ChatModel) -> HistoryItem:
        latest_run = self.session.execute(
            select(ChatRunModel)
            .where(ChatRunModel.chat_id == chat.id)
            .order_by(ChatRunModel.started_at.desc(), ChatRunModel.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        return HistoryItem(
            chat_id=chat.id,
            title=chat.title,
            latest_run_id=latest_run.id if latest_run is not None else None,
            latest_state=latest_run.state if latest_run is not None else "",
            updated_at=chat.updated_at,
        )

    def _chat_run_data(self, run: ChatRunModel) -> ChatRunData:
        instruction = self.session.execute(
            select(UserInstructionModel)
            .where(UserInstructionModel.run_id == run.id)
            .limit(1)
        ).scalar_one()
        messages = tuple(
            self.session.execute(
                select(IntermediateMessageModel)
                .where(IntermediateMessageModel.run_id == run.id)
                .order_by(
                    IntermediateMessageModel.created_at,
                    IntermediateMessageModel.id,
                )
            ).scalars()
        )
        answer = self._answer_data(run.id)
        return ChatRunData(
            run_id=run.id,
            state=run.state,
            user_instruction=instruction.body,
            started_at=run.started_at,
            intermediate_messages=tuple(
                IntermediateMessageData(
                    text=message.body,
                    created_at=message.created_at,
                )
                for message in messages
            ),
            answer=answer,
            user_message=run.user_message,
        )

    def _answer_data(self, run_id: UUID) -> AnswerData | None:
        blocks = tuple(
            self.session.execute(
                select(AnswerBlockModel)
                .where(AnswerBlockModel.run_id == run_id)
                .order_by(AnswerBlockModel.position)
            ).scalars()
        )
        if not blocks:
            return None
        return AnswerData(
            blocks=tuple(self._answer_block_data(block) for block in blocks),
        )

    def _answer_block_data(self, block: AnswerBlockModel) -> AnswerBlockData:
        references = tuple(
            self.session.execute(
                select(ReferenceModel)
                .where(ReferenceModel.answer_block_id == block.id)
                .order_by(ReferenceModel.position)
            ).scalars()
        )
        artifacts = tuple(
            self.session.execute(
                select(ArtifactModel)
                .where(ArtifactModel.answer_block_id == block.id)
                .order_by(ArtifactModel.created_at, ArtifactModel.id)
            ).scalars()
        )
        return AnswerBlockData(
            answer_block_id=block.id,
            position=block.position,
            markdown=block.markdown,
            references=tuple(_reference_data(reference) for reference in references),
            artifacts=tuple(
                ArtifactData(
                    artifact_id=artifact.id,
                    mime_type=artifact.mime_type,
                    storage_path=artifact.storage_path,
                    created_at=artifact.created_at,
                )
                for artifact in artifacts
            ),
        )


def _reference_data(reference: ReferenceModel) -> DisplayReferenceData:
    locator = reference.locator
    path = locator.get("path")
    page_start = locator.get("page_start")
    page_end = locator.get("page_end")
    if (
        not isinstance(path, str)
        or not isinstance(page_start, int)
        or not isinstance(
            page_end,
            int,
        )
    ):
        raise AppError(
            error_type=ErrorType.SYSTEM,
            trace=True,
            diagnostic_message="参照元locatorの形式が不正です。",
        )
    return DisplayReferenceData(
        reference_id=reference.id,
        position=reference.position,
        source_type=reference.source_type,
        label=reference.label,
        path=path,
        page_start=page_start,
        page_end=page_end,
    )


def _integrity_error(error: IntegrityError) -> AppError:
    message = str(error.orig)
    if "chat_runs_one_unfinished_per_chat" in message:
        return AppError(
            error_type=ErrorType.CONFLICT,
            trace=False,
            diagnostic_message="未完了のチャット実行処理があります。",
        )
    return AppError(
        error_type=ErrorType.SYSTEM,
        trace=True,
        diagnostic_message=message,
        cause=error,
    )

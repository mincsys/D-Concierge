from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

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
from backend.application.ports.runtime.interface import ClockPort, IdGeneratorPort
from backend.domain.account.user_state import UserState
from backend.domain.chat.chat_state import ChatState
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
    LoginSessionModel,
    UserInstructionModel,
    UserModel,
)
from backend.infrastructure.runtime.system_clock import SystemClock
from backend.infrastructure.runtime.uuid_generator import UuidGenerator
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import (
    ActiveRunConflictError,
    AppError,
    ArtifactNotFoundError,
    CancelNotAllowedError,
    ChatDeletingError,
    ChatNotFoundError,
    ReferenceNotFoundError,
    RunNotFoundError,
    UserInstructionRequiredError,
)
from backend.shared.user_messages import (
    CANCELED_MESSAGE,
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

    def create_user(
        self, user_id: str, user_name: str, password_hash: str, now: datetime
    ) -> None:
        """アカウントユーザを作成する。"""
        self._session().add(
            UserModel(
                id=user_id,
                user_name=user_name,
                password_hash=password_hash,
                user_state=UserState.ACTIVE.value,
                created_at=now,
                updated_at=now,
            )
        )

    def get_user_for_login(self, user_id: str) -> AccountUserData | None:
        """ログイン検証用ユーザ情報を返す。"""
        user = self._session().get(UserModel, user_id)
        if user is None:
            return None
        return _account_user_data(user)

    def update_user_name(
        self, user_id: str, user_name: str, now: datetime
    ) -> AccountUserData:
        """ユーザ名を更新する。"""
        user = self._get_user(user_id)
        user.user_name = user_name
        user.updated_at = now
        return _account_user_data(user)

    def update_password_hash(
        self, user_id: str, password_hash: str, now: datetime
    ) -> None:
        """パスワードハッシュを更新する。"""
        user = self._get_user(user_id)
        user.password_hash = password_hash
        user.updated_at = now

    def create_login_session(
        self, token_hash: str, user_id: str, expires_at: datetime, now: datetime
    ) -> LoginSessionData:
        """ログインセッションを作成する。"""
        session = self._session()
        user = self._get_user(user_id)
        login_session = LoginSessionModel(
            token_hash=token_hash,
            user_id=user_id,
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
        )
        session.add(login_session)
        session.flush()
        return _login_session_data(login_session, user)

    def find_session_by_token_hash(self, token_hash: str) -> LoginSessionData | None:
        """ログインセッションと所有ユーザを返す。"""
        session = self._session()
        login_session = session.scalar(
            sa.select(LoginSessionModel).where(
                LoginSessionModel.token_hash == token_hash
            )
        )
        if login_session is None:
            return None
        user = session.get(UserModel, login_session.user_id)
        if user is None:
            return None
        return _login_session_data(login_session, user)

    def delete_session_by_token_hash(self, token_hash: str) -> int:
        """現在セッションを削除する。"""
        session = self._session()
        session_ids = tuple(
            session.scalars(
                sa.select(LoginSessionModel.id).where(
                    LoginSessionModel.token_hash == token_hash
                )
            ).all()
        )
        if not session_ids:
            return 0
        session.execute(
            sa.delete(LoginSessionModel).where(LoginSessionModel.id.in_(session_ids))
        )
        return len(session_ids)

    def delete_sessions_by_user_id(self, user_id: str) -> int:
        """ユーザの全ログインセッションを削除する。"""
        session = self._session()
        session_ids = tuple(
            session.scalars(
                sa.select(LoginSessionModel.id).where(
                    LoginSessionModel.user_id == user_id
                )
            ).all()
        )
        if not session_ids:
            return 0
        session.execute(
            sa.delete(LoginSessionModel).where(LoginSessionModel.id.in_(session_ids))
        )
        return len(session_ids)

    def delete_expired_sessions(self, now: datetime) -> int:
        """期限切れログインセッションを削除する。"""
        session = self._session()
        session_ids = tuple(
            session.scalars(
                sa.select(LoginSessionModel.id).where(
                    LoginSessionModel.expires_at <= now
                )
            ).all()
        )
        if not session_ids:
            return 0
        session.execute(
            sa.delete(LoginSessionModel).where(LoginSessionModel.id.in_(session_ids))
        )
        return len(session_ids)

    def mark_user_deleting(self, user_id: str, now: datetime) -> None:
        """ユーザを削除中へ更新する。"""
        user = self._get_user(user_id)
        user.user_state = UserState.DELETING.value
        user.updated_at = now

    def mark_user_chats_deleting(self, user_id: str, now: datetime) -> None:
        """ユーザの全チャットを削除中へ更新する。"""
        self._session().execute(
            sa.update(ChatModel)
            .where(ChatModel.user_id == user_id)
            .values(chat_state=ChatState.DELETING.value, updated_at=now)
        )

    def list_deleting_user_ids(self) -> tuple[str, ...]:
        """削除中ユーザIDを返す。"""
        return tuple(
            self._session()
            .scalars(
                sa.select(UserModel.id)
                .where(UserModel.user_state == UserState.DELETING.value)
                .order_by(UserModel.updated_at, UserModel.id)
            )
            .all()
        )

    def get_account_deletion_target(self, user_id: str) -> AccountDeletionTarget | None:
        """アカウント物理削除対象を返す。"""
        session = self._session()
        if session.get(UserModel, user_id) is None:
            return None
        unfinished_runs = tuple(
            ChatDeletionRun(run_id=run.id, state=_run_state(run))
            for run in session.scalars(
                sa.select(ChatRunModel)
                .join(ChatModel, ChatModel.id == ChatRunModel.chat_id)
                .where(
                    ChatModel.user_id == user_id,
                    ChatRunModel.state.in_(
                        tuple(state.value for state in UNFINISHED_STATES)
                    ),
                )
                .order_by(ChatRunModel.started_at, ChatRunModel.id)
            ).all()
        )
        return AccountDeletionTarget(user_id=user_id, unfinished_runs=unfinished_runs)

    def delete_account_data(self, user_id: str) -> None:
        """アカウント関連DBデータを削除する。"""
        session = self._session()
        self.delete_sessions_by_user_id(user_id)
        chat_ids = tuple(
            session.scalars(
                sa.select(ChatModel.id).where(ChatModel.user_id == user_id)
            ).all()
        )
        for chat_id in chat_ids:
            self.delete_chat_cascade(chat_id)
        session.execute(sa.delete(UserModel).where(UserModel.id == user_id))

    def create_chat_with_first_run(
        self, user_instruction: str, user_id: str = ""
    ) -> AcceptedRun:
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
                user_id=user_id or None,
                local_user_id=SHARED_LOCAL_USER_ID,
                session_id=self._id_generator.new_uuid(),
                title=ChatTitlePolicy.make_title(instruction),
                chat_state=ChatState.ACTIVE.value,
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

    def append_run(
        self, chat_id: UUID, user_instruction: str, user_id: str = ""
    ) -> AcceptedRun:
        """既存チャットへ受付runと指示を追加する。"""
        instruction = _user_instruction(user_instruction)
        now = self._clock.now()
        run_id = self._id_generator.new_uuid()
        session = self._session()
        chat = self._get_active_chat(session, chat_id, user_id=user_id)
        unfinished = session.scalar(
            sa.select(ChatRunModel).where(
                ChatRunModel.chat_id == chat_id,
                ChatRunModel.state.in_(
                    tuple(state.value for state in UNFINISHED_STATES)
                ),
            )
        )
        if unfinished is not None:
            raise ActiveRunConflictError()
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

    def list_histories(self, user_id: str = "") -> tuple[HistoryItem, ...]:
        """チャット履歴を更新日時降順で返す。"""
        session = self._session()
        query = (
            sa.select(ChatModel)
            .where(ChatModel.chat_state == ChatState.ACTIVE.value)
            .order_by(ChatModel.updated_at.desc())
        )
        if user_id:
            query = query.where(ChatModel.user_id == user_id)
        chats = session.scalars(query).all()
        histories = [self._to_history_item(session, chat) for chat in chats]
        return tuple(
            history for history in histories if history.latest_run_id is not None
        )

    def list_unfinished_runs_for_recovery(self) -> tuple[UnfinishedRun, ...]:
        """起動時回復対象の未完了runを開始日時順で返す。"""
        session = self._session()
        runs = session.scalars(
            sa.select(ChatRunModel)
            .join(ChatModel, ChatModel.id == ChatRunModel.chat_id)
            .where(
                ChatRunModel.state.in_(
                    tuple(state.value for state in UNFINISHED_STATES)
                ),
                ChatModel.chat_state == ChatState.ACTIVE.value,
            )
            .order_by(ChatRunModel.started_at, ChatRunModel.id)
        ).all()
        return tuple(
            UnfinishedRun(chat_id=run.chat_id, run_id=run.id, state=_run_state(run))
            for run in runs
        )

    def get_chat_detail(self, chat_id: UUID, user_id: str = "") -> ChatDetail:
        """指定チャットの詳細を返す。"""
        session = self._session()
        chat = self._get_active_chat(session, chat_id, user_id=user_id)
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
        chat = self._get_active_chat(session, chat_id)
        return ChatRuntimeContext(
            chat_id=chat.id,
            user_id=_chat_user_id(chat),
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
            raise CancelNotAllowedError()
        run.state = RunState.CANCELED.value
        run.user_message = CANCELED_MESSAGE
        chat = self._get_chat(session, chat_id)
        chat.updated_at = now

    def get_reference(
        self, reference_id: UUID, user_id: str = ""
    ) -> DisplayReferenceData:
        """参照元IDに対応する配信メタ情報を返す。"""
        session = self._session()
        row = session.execute(
            self._reference_delivery_query(reference_id, user_id)
        ).first()
        if row is None:
            raise ReferenceNotFoundError()
        reference, chat_state = row
        if chat_state == ChatState.DELETING.value:
            raise ChatDeletingError()
        path_value = reference.locator.get("path")
        page_start_value = reference.locator.get("page_start")
        page_end_value = reference.locator.get("page_end")
        if (
            not isinstance(path_value, str)
            or not isinstance(page_start_value, int)
            or not isinstance(page_end_value, int)
        ):
            raise _system_error("参照元データが不整合です。")
        return DisplayReferenceData(
            reference_id=reference.id,
            source_type=_source_type(reference.source_type),
            label=reference.label,
            relative_path=path_value,
            page_start=page_start_value,
            page_end=page_end_value,
        )

    def get_artifact(self, artifact_id: UUID, user_id: str = "") -> ArtifactData:
        """成果物IDに対応する配信メタ情報を返す。"""
        session = self._session()
        row = session.execute(
            self._artifact_delivery_query(artifact_id, user_id)
        ).first()
        if row is None:
            raise ArtifactNotFoundError()
        artifact, chat_state = row
        if chat_state == ChatState.DELETING.value:
            raise ChatDeletingError()
        return ArtifactData(
            artifact_id=artifact.id,
            mime_type=artifact.mime_type,
            relative_path=artifact.storage_path,
        )

    def mark_chat_deleting(self, chat_id: UUID, user_id: str = "") -> DeleteChatResult:
        """対象チャットを削除中へ更新する。"""
        session = self._session()
        chat = self._get_chat(session, chat_id, user_id=user_id)
        chat.chat_state = ChatState.DELETING.value
        chat.updated_at = self._clock.now()
        return DeleteChatResult(chat_id=chat_id, chat_state=ChatState.DELETING)

    def list_deleting_chats_for_recovery(self) -> tuple[UUID, ...]:
        """起動時再登録対象の削除中チャットIDを返す。"""
        session = self._session()
        return tuple(
            session.scalars(
                sa.select(ChatModel.id)
                .where(ChatModel.chat_state == ChatState.DELETING.value)
                .order_by(ChatModel.updated_at, ChatModel.id)
            ).all()
        )

    def get_chat_deletion_target(self, chat_id: UUID) -> ChatDeletionTarget:
        """物理削除対象のチャット関連情報を返す。"""
        session = self._session()
        chat = self._get_chat(session, chat_id)
        unfinished_runs = tuple(
            ChatDeletionRun(run_id=run.id, state=_run_state(run))
            for run in session.scalars(
                sa.select(ChatRunModel)
                .where(
                    ChatRunModel.chat_id == chat_id,
                    ChatRunModel.state.in_(
                        tuple(state.value for state in UNFINISHED_STATES)
                    ),
                )
                .order_by(ChatRunModel.started_at, ChatRunModel.id)
            ).all()
        )
        artifact_storage_paths = tuple(
            session.scalars(
                sa.select(ArtifactModel.storage_path)
                .select_from(ArtifactModel)
                .join(
                    AnswerBlockModel,
                    AnswerBlockModel.id == ArtifactModel.answer_block_id,
                )
                .join(ChatRunModel, ChatRunModel.id == AnswerBlockModel.run_id)
                .where(ChatRunModel.chat_id == chat_id)
                .order_by(ArtifactModel.created_at, ArtifactModel.id)
            ).all()
        )
        return ChatDeletionTarget(
            chat_id=chat.id,
            user_id=_chat_user_id(chat),
            local_user_id=chat.local_user_id,
            session_id=chat.session_id,
            unfinished_runs=unfinished_runs,
            artifact_storage_paths=artifact_storage_paths,
        )

    def delete_chat_cascade(self, chat_id: UUID) -> None:
        """対象チャット一式をDBから削除する。"""
        session = self._session()
        self._get_chat(session, chat_id)
        run_ids = tuple(
            session.scalars(
                sa.select(ChatRunModel.id).where(ChatRunModel.chat_id == chat_id)
            ).all()
        )
        block_ids: tuple[UUID, ...] = ()
        if run_ids:
            block_ids = tuple(
                session.scalars(
                    sa.select(AnswerBlockModel.id).where(
                        AnswerBlockModel.run_id.in_(run_ids)
                    )
                ).all()
            )
        if block_ids:
            session.execute(
                sa.delete(ReferenceModel).where(
                    ReferenceModel.answer_block_id.in_(block_ids)
                )
            )
            session.execute(
                sa.delete(ArtifactModel).where(
                    ArtifactModel.answer_block_id.in_(block_ids)
                )
            )
            session.execute(
                sa.delete(AnswerBlockModel).where(AnswerBlockModel.id.in_(block_ids))
            )
        if run_ids:
            session.execute(
                sa.delete(IntermediateMessageModel).where(
                    IntermediateMessageModel.run_id.in_(run_ids)
                )
            )
            session.execute(
                sa.delete(UserInstructionModel).where(
                    UserInstructionModel.run_id.in_(run_ids)
                )
            )
            session.execute(sa.delete(ChatRunModel).where(ChatRunModel.id.in_(run_ids)))
        session.execute(sa.delete(ChatModel).where(ChatModel.id == chat_id))

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
            raise _system_error("参照元データが不整合です。")
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

    def _get_user(self, user_id: str) -> UserModel:
        user = self._session().get(UserModel, user_id)
        if user is None:
            raise ChatNotFoundError()
        return user

    def _get_chat(
        self, session: Session, chat_id: UUID, user_id: str = ""
    ) -> ChatModel:
        chat = session.get(ChatModel, chat_id)
        if chat is None or (user_id and chat.user_id != user_id):
            raise ChatNotFoundError()
        return chat

    def _get_active_chat(
        self, session: Session, chat_id: UUID, user_id: str = ""
    ) -> ChatModel:
        chat = self._get_chat(session, chat_id, user_id=user_id)
        if chat.chat_state == ChatState.DELETING.value:
            raise ChatDeletingError()
        return chat

    def _get_run(self, session: Session, chat_id: UUID, run_id: UUID) -> ChatRunModel:
        self._get_chat(session, chat_id)
        run = session.get(ChatRunModel, run_id)
        if run is None or run.chat_id != chat_id:
            raise RunNotFoundError()
        return run

    def _get_instruction(self, session: Session, run_id: UUID) -> UserInstructionModel:
        instruction = session.scalar(
            sa.select(UserInstructionModel).where(UserInstructionModel.run_id == run_id)
        )
        if instruction is None:
            raise _system_error("履歴データが不整合です。")
        return instruction

    def _reference_delivery_query(
        self, reference_id: UUID, user_id: str = ""
    ) -> sa.Select[tuple[ReferenceModel, str]]:
        statement = (
            sa.select(ReferenceModel, ChatModel.chat_state)
            .select_from(ReferenceModel)
            .join(
                AnswerBlockModel,
                AnswerBlockModel.id == ReferenceModel.answer_block_id,
            )
            .join(ChatRunModel, ChatRunModel.id == AnswerBlockModel.run_id)
            .join(ChatModel, ChatModel.id == ChatRunModel.chat_id)
            .where(ReferenceModel.id == reference_id)
        )
        if user_id:
            statement = statement.where(ChatModel.user_id == user_id)
        return statement

    def _artifact_delivery_query(
        self, artifact_id: UUID, user_id: str = ""
    ) -> sa.Select[tuple[ArtifactModel, str]]:
        statement = (
            sa.select(ArtifactModel, ChatModel.chat_state)
            .select_from(ArtifactModel)
            .join(
                AnswerBlockModel,
                AnswerBlockModel.id == ArtifactModel.answer_block_id,
            )
            .join(ChatRunModel, ChatRunModel.id == AnswerBlockModel.run_id)
            .join(ChatModel, ChatModel.id == ChatRunModel.chat_id)
            .where(ArtifactModel.id == artifact_id)
        )
        if user_id:
            statement = statement.where(ChatModel.user_id == user_id)
        return statement


def _user_instruction(user_instruction: str) -> UserInstruction:
    try:
        return UserInstruction(user_instruction)
    except InvalidUserInstructionError as exc:
        raise UserInstructionRequiredError() from exc


def _run_state(run: ChatRunModel) -> RunState:
    try:
        return RunState(run.state)
    except ValueError as exc:
        raise _system_error("履歴データが不整合です。", exc) from exc


def _source_type(value: str) -> SourceType:
    try:
        return SourceType(value)
    except ValueError as exc:
        raise _system_error("参照元データが不整合です。", exc) from exc


def _chat_user_id(chat: ChatModel) -> str:
    return chat.user_id if chat.user_id is not None else str(chat.local_user_id)


def _account_user_data(user: UserModel) -> AccountUserData:
    return AccountUserData(
        user_id=user.id,
        user_name=user.user_name,
        password_hash=user.password_hash,
        user_state=_user_state(user.user_state),
    )


def _login_session_data(
    login_session: LoginSessionModel, user: UserModel
) -> LoginSessionData:
    return LoginSessionData(
        session_id=login_session.id,
        token_hash=login_session.token_hash,
        user_id=user.id,
        user_name=user.user_name,
        user_state=_user_state(user.user_state),
        expires_at=login_session.expires_at,
    )


def _user_state(value: str) -> UserState:
    try:
        return UserState(value)
    except ValueError as exc:
        raise _system_error("ユーザデータが不整合です。", exc) from exc


def _system_error(diagnostic_message: str, cause: Exception | None = None) -> AppError:
    return AppError(
        ErrorType.SYSTEM,
        trace=True,
        diagnostic_message=diagnostic_message,
        cause=cause,
    )

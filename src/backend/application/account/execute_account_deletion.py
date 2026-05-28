from backend.application.ports.codex.interface import CancelRequesterPort
from backend.application.ports.database.interface import (
    AccountRepositoryPort,
    TransactionManagerPort,
)
from backend.application.ports.filesystem.interface import (
    UserSavedArtifactDeletionPort,
    UserWorkdirCleanupPort,
)
from backend.application.transactions import NoopTransactionManager
from backend.domain.execution.run_state_policy import RunStatePolicy


class ExecuteAccountDeletionUseCase:
    """削除中アカウントの物理削除を実行する。"""

    def __init__(
        self,
        repository: AccountRepositoryPort,
        cancel_requester: CancelRequesterPort | None,
        session_workdir_cleanup: UserWorkdirCleanupPort,
        artifact_deletion: UserSavedArtifactDeletionPort,
        transaction_manager: TransactionManagerPort | None = None,
    ) -> None:
        self._repository = repository
        self._cancel_requester = cancel_requester
        self._session_workdir_cleanup = session_workdir_cleanup
        self._artifact_deletion = artifact_deletion
        self._transaction_manager = (
            transaction_manager
            if transaction_manager is not None
            else NoopTransactionManager()
        )

    def execute(self, user_id: str, trace_id: str = "") -> None:
        """未完了runがなければファイルとDBを削除する。"""
        with self._transaction_manager.transaction():
            target = self._repository.get_account_deletion_target(user_id)
        if target is None:
            return
        has_unfinished_run = False
        for run in target.unfinished_runs:
            if RunStatePolicy.is_unfinished(run.state):
                has_unfinished_run = True
                if self._cancel_requester is not None:
                    self._cancel_requester.request_cancel(run.run_id)
        if has_unfinished_run:
            return

        self._session_workdir_cleanup.delete_user_workdirs(user_id)
        self._artifact_deletion.delete_user_artifacts(user_id)
        with self._transaction_manager.transaction():
            self._repository.delete_account_data(user_id)

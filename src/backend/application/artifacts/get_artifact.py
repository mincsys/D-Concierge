from uuid import UUID

from backend.application.ports.database.interface import (
    ChatReadRepositoryPort,
    TransactionManagerPort,
)
from backend.application.ports.filesystem.dto import OpenedArtifactFile
from backend.application.ports.filesystem.interface import ArtifactStorePort
from backend.application.transactions import NoopTransactionManager


class GetArtifactUseCase:
    """保存済みCodex成果物の配信情報取得を調停する。"""

    def __init__(
        self,
        repository: ChatReadRepositoryPort,
        artifact_store: ArtifactStorePort,
        transaction_manager: TransactionManagerPort | None = None,
    ) -> None:
        self._repository = repository
        self._artifact_store = artifact_store
        self._transaction_manager = (
            transaction_manager
            if transaction_manager is not None
            else NoopTransactionManager()
        )

    def execute(self, artifact_id: UUID, user_id: str = "") -> OpenedArtifactFile:
        """成果物IDから保存済みファイルを開く。"""
        with self._transaction_manager.transaction():
            artifact = self._repository.get_artifact(artifact_id, user_id=user_id)
        return self._artifact_store.open_saved_file(
            relative_path=artifact.relative_path,
            mime_type=artifact.mime_type,
        )

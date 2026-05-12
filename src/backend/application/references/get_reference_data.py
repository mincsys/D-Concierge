from uuid import UUID

from backend.application.ports.database.interface import (
    ChatReadRepositoryPort,
    TransactionManagerPort,
)
from backend.application.ports.filesystem.dto import OpenedReferenceFile
from backend.application.ports.filesystem.interface import ReferenceStorePort
from backend.application.transactions import NoopTransactionManager
from backend.domain.references.source_type import SourceType
from backend.shared.errors.errors import ReferenceNotDisplayableError


class GetReferenceDataUseCase:
    """参照元PDFの配信情報取得を調停する。"""

    def __init__(
        self,
        repository: ChatReadRepositoryPort,
        reference_store: ReferenceStorePort,
        transaction_manager: TransactionManagerPort | None = None,
    ) -> None:
        self._repository = repository
        self._reference_store = reference_store
        self._transaction_manager = (
            transaction_manager
            if transaction_manager is not None
            else NoopTransactionManager()
        )

    def execute(self, reference_id: UUID) -> OpenedReferenceFile:
        """参照元IDからPDFファイルを開く。"""
        with self._transaction_manager.transaction():
            reference = self._repository.get_reference(reference_id)
        if reference.source_type is not SourceType.PDF:
            raise ReferenceNotDisplayableError()
        return self._reference_store.open_reference_file(reference.relative_path)

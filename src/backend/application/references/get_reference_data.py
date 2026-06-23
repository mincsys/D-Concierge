from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from backend.application.ports.database.interface import ReferenceDeliveryRepositoryPort
from backend.application.ports.filesystem.interface import ReferenceStorePort
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.shared.tracing.trace_id import TraceId

PDF_SOURCE_TYPE = "pdf"


@dataclass(frozen=True, slots=True)
class GetReferenceDataCommand:
    """参照元PDF取得要求。"""

    user_id: str
    reference_id: UUID
    trace_id: TraceId | str


@dataclass(frozen=True, slots=True)
class GetReferenceDataResult:
    """参照元PDF取得結果。"""

    file_path: Path
    mime_type: str


@dataclass(frozen=True, slots=True)
class GetReferenceDataUseCase:
    """保存済み回答の参照元PDFを配信用ファイルへ解決する。"""

    repository: ReferenceDeliveryRepositoryPort
    reference_store: ReferenceStorePort

    def execute(self, command: GetReferenceDataCommand) -> GetReferenceDataResult:
        reference = self.repository.get_reference_for_delivery(
            command.user_id,
            command.reference_id,
        )
        if reference is None:
            raise AppError(
                error_type=ErrorType.NOT_FOUND,
                trace=False,
                diagnostic_message="参照元が見つかりません。",
            )
        if reference.source_type != PDF_SOURCE_TYPE:
            raise AppError(
                error_type=ErrorType.FORBIDDEN,
                trace=False,
                diagnostic_message="PDF以外の参照元は配信できません。",
            )

        opened = self.reference_store.open_reference_file(reference.path)
        return GetReferenceDataResult(
            file_path=opened.file_path,
            mime_type=opened.mime_type,
        )

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import UUID

from backend.application.ports.database.interface import ArtifactDeliveryRepositoryPort
from backend.application.ports.filesystem.interface import ArtifactStorePort
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.shared.tracing.trace_id import TraceId

ARTIFACT_MIME_TYPES_BY_SUFFIX = {
    ".csv": "text/csv",
    ".html": "text/html",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
}
ALLOWED_ARTIFACT_MIME_TYPES = frozenset(ARTIFACT_MIME_TYPES_BY_SUFFIX.values())


@dataclass(frozen=True, slots=True)
class GetArtifactCommand:
    """Codex成果物取得要求。"""

    user_id: str
    artifact_id: UUID
    trace_id: TraceId | str


@dataclass(frozen=True, slots=True)
class GetArtifactResult:
    """Codex成果物取得結果。"""

    file_path: Path
    mime_type: str


@dataclass(frozen=True, slots=True)
class GetArtifactUseCase:
    """採用済みCodex成果物を配信用ファイルへ解決する。"""

    repository: ArtifactDeliveryRepositoryPort
    artifact_store: ArtifactStorePort

    def execute(self, command: GetArtifactCommand) -> GetArtifactResult:
        artifact = self.repository.get_artifact_for_delivery(
            command.user_id,
            command.artifact_id,
        )
        if artifact is None:
            raise AppError(
                error_type=ErrorType.NOT_FOUND,
                trace=False,
                diagnostic_message="成果物が見つかりません。",
            )
        if artifact.mime_type not in ALLOWED_ARTIFACT_MIME_TYPES:
            raise AppError(
                error_type=ErrorType.FORBIDDEN,
                trace=False,
                diagnostic_message="配信できない成果物MIMEタイプです。",
            )
        if _mime_type_for_storage_path(artifact.storage_path) != artifact.mime_type:
            raise AppError(
                error_type=ErrorType.FORBIDDEN,
                trace=False,
                diagnostic_message="成果物のMIMEタイプと拡張子が一致しません。",
            )

        opened = self.artifact_store.open_saved_file(artifact)
        return GetArtifactResult(file_path=opened.file_path, mime_type=opened.mime_type)


def _mime_type_for_storage_path(storage_path: str) -> str | None:
    suffix = PurePosixPath(storage_path.replace("\\", "/")).suffix.lower()
    return ARTIFACT_MIME_TYPES_BY_SUFFIX.get(suffix)

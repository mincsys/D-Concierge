from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse

from backend.application.artifacts.get_artifact import (
    GetArtifactCommand,
    GetArtifactUseCase,
)
from backend.application.references.get_reference_data import (
    GetReferenceDataCommand,
    GetReferenceDataUseCase,
)
from backend.infrastructure.config.settings import AppSettings
from backend.infrastructure.database.repositories.chat import SqlAlchemyChatRepository
from backend.infrastructure.filesystem.artifact_store import FileArtifactStore
from backend.infrastructure.filesystem.reference_store import FileReferenceStore
from backend.presentation.errors.http import trace_id_from_request
from backend.presentation.rest.dependencies import (
    AuthenticatedUser,
    get_authenticated_user,
    get_session_factory,
    get_settings,
)
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError

router = APIRouter()


@router.get("/api/references/{reference_id}")
async def get_reference_data(
    request: Request,
    reference_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
) -> FileResponse:
    """保存済み回答の参照元PDFを配信する。"""

    settings = await get_settings(request)
    session_factory = get_session_factory(request)
    with session_factory() as session:
        use_case = GetReferenceDataUseCase(
            repository=SqlAlchemyChatRepository(session),
            reference_store=FileReferenceStore(settings.data_source.dir),
        )
        result = use_case.execute(
            GetReferenceDataCommand(
                user_id=authenticated_user.user_id,
                reference_id=reference_id,
                trace_id=trace_id_from_request(request),
            )
        )
    return _file_response(result.file_path, result.mime_type)


@router.get("/api/artifacts/{artifact_id}")
async def get_artifact(
    request: Request,
    artifact_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
) -> FileResponse:
    """採用済みCodex成果物を保存済みMIMEタイプで配信する。"""

    settings = await get_settings(request)
    session_factory = get_session_factory(request)
    with session_factory() as session:
        use_case = GetArtifactUseCase(
            repository=SqlAlchemyChatRepository(session),
            artifact_store=FileArtifactStore(_saved_artifacts_dir(settings)),
        )
        result = use_case.execute(
            GetArtifactCommand(
                user_id=authenticated_user.user_id,
                artifact_id=artifact_id,
                trace_id=trace_id_from_request(request),
            )
        )
    return _file_response(result.file_path, result.mime_type)


def _saved_artifacts_dir(settings: AppSettings) -> Path:
    saved_artifacts_dir = settings.generator.saved_artifacts_dir
    if saved_artifacts_dir is None:
        raise AppError(
            error_type=ErrorType.CONFIGURATION,
            trace=True,
            diagnostic_message="保存済み成果物ディレクトリが設定されていません。",
        )
    return saved_artifacts_dir


def _file_response(file_path: Path, mime_type: str) -> FileResponse:
    return FileResponse(
        path=file_path,
        media_type=mime_type,
        headers={"x-content-type-options": "nosniff"},
    )

from __future__ import annotations

import mimetypes
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid7

from backend.application.ports.database.dto import ArtifactData
from backend.application.ports.filesystem.dto import (
    AdoptedArtifactSaveRequest,
    AdoptedArtifactSaveResult,
    OpenedArtifactFile,
)
from backend.infrastructure.filesystem.path_security import PathSecurityService
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError

DELIVERABLE_ARTIFACT_SUFFIXES = (".csv", ".html", ".jpeg", ".jpg", ".png", ".svg")


@dataclass(frozen=True, slots=True)
class FileArtifactStore:
    """採用済みCodex成果物を保存領域へコピーする。"""

    saved_artifacts_root: Path
    path_security: PathSecurityService = field(default_factory=PathSecurityService)

    def save_adopted_artifact(
        self,
        source: AdoptedArtifactSaveRequest,
    ) -> AdoptedArtifactSaveResult:
        source_path = source.artifacts_dir / source.relative_path.removeprefix(
            "artifacts/",
        )
        if not source_path.is_file():
            raise AppError(
                error_type=ErrorType.SYSTEM,
                trace=True,
                diagnostic_message=(
                    f"成果物候補ファイルが見つかりません: {source.relative_path}"
                ),
            )
        artifact_id = uuid7()
        suffix = source_path.suffix.lower()
        storage_path = f"{source.user_id}/{source.session_id}/{artifact_id}{suffix}"
        destination = self.saved_artifacts_root / storage_path
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)
        except OSError as error:
            raise AppError(
                error_type=ErrorType.SYSTEM,
                trace=True,
                diagnostic_message="採用済み成果物を保存できません。",
                cause=error,
            ) from error
        return AdoptedArtifactSaveResult(
            artifact_id=str(artifact_id),
            storage_path=storage_path,
            public_url=f"/api/artifacts/{artifact_id}",
            mime_type=_mime_type(destination),
        )

    def open_saved_file(self, artifact: ArtifactData) -> OpenedArtifactFile:
        """保存済み成果物を配信用ファイルとして開く。"""

        file_path = self.path_security.resolve_under_root(
            self.saved_artifacts_root,
            artifact.storage_path,
            DELIVERABLE_ARTIFACT_SUFFIXES,
        )
        if not file_path.is_file():
            raise AppError(
                error_type=ErrorType.NOT_FOUND,
                trace=True,
                diagnostic_message="保存済み成果物ファイルが見つかりません。",
            )
        try:
            with file_path.open("rb"):
                pass
        except OSError as error:
            raise AppError(
                error_type=ErrorType.SYSTEM,
                trace=True,
                diagnostic_message="保存済み成果物ファイルを読み取れません。",
                cause=error,
            ) from error
        return OpenedArtifactFile(file_path=file_path, mime_type=artifact.mime_type)

    def delete_saved_files(self, storage_paths: tuple[str, ...]) -> tuple[str, ...]:
        """保存済み成果物ファイルと空の親セッションディレクトリを削除する。"""

        deleted_paths: list[str] = []
        for storage_path in storage_paths:
            file_path = self._resolve_artifact_path_for_deletion(storage_path)
            if not file_path.exists():
                deleted_paths.append(storage_path)
                continue
            if not file_path.is_file():
                raise RuntimeError(
                    f"保存済み成果物を削除できません: {storage_path}",
                )
            try:
                file_path.unlink()
                self._remove_empty_parents(file_path.parent)
            except OSError as error:
                raise RuntimeError(
                    f"保存済み成果物を削除できません: {storage_path}: {error}",
                ) from error
            deleted_paths.append(storage_path)
        return tuple(deleted_paths)

    def delete_user_saved_artifacts(self, user_id: str) -> None:
        """ユーザ単位の保存済み成果物ディレクトリを削除する。"""

        user_dir = self.path_security.resolve_under_root(
            self.saved_artifacts_root,
            user_id,
        )
        if not user_dir.exists():
            return
        try:
            shutil.rmtree(user_dir)
        except OSError as error:
            raise RuntimeError(
                f"保存済み成果物ディレクトリを削除できません: {user_dir}: {error}",
            ) from error

    def _resolve_artifact_path_for_deletion(self, storage_path: str) -> Path:
        try:
            return self.path_security.resolve_under_root(
                self.saved_artifacts_root,
                storage_path,
                DELIVERABLE_ARTIFACT_SUFFIXES,
            )
        except AppError as error:
            raise RuntimeError(
                f"保存済み成果物のstorage_pathが不正です: {storage_path}",
            ) from error

    def _remove_empty_parents(self, directory: Path) -> None:
        root_path = self.saved_artifacts_root.resolve()
        current = directory.resolve()
        while current != root_path and root_path in current.parents:
            try:
                current.rmdir()
            except OSError:
                return
            current = current.parent


def _mime_type(path: Path) -> str:
    guessed = mimetypes.guess_type(path.name)[0]
    return guessed or "application/octet-stream"

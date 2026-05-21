from pathlib import Path, PurePosixPath
from shutil import copy2
from uuid import UUID

from backend.application.ports.filesystem.dto import (
    OpenedArtifactFile,
    SavedArtifactFile,
)
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import (
    AppError,
    ArtifactAlreadySavedError,
    ArtifactNotDisplayableError,
    ArtifactNotFoundError,
)

_MIME_TYPE_BY_SUFFIX = {
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".html": "text/html",
    ".csv": "text/csv",
}
_DEFAULT_ALLOWED_MIME_TYPES = tuple(_MIME_TYPE_BY_SUFFIX.values())


class FileArtifactStore:
    """セッション内成果物を保存済み領域へコピーし、配信用に開く。"""

    def __init__(
        self,
        saved_artifacts_dir: Path,
        allowed_mime_types: tuple[str, ...] = _DEFAULT_ALLOWED_MIME_TYPES,
    ) -> None:
        self._saved_artifacts_dir = saved_artifacts_dir
        self._allowed_mime_types = allowed_mime_types

    def save_adopted_file(
        self,
        session_workdir: Path,
        candidate_relative_path: str,
        run_id: UUID,
        artifact_id: UUID,
    ) -> SavedArtifactFile:
        """セッション内 `artifacts/` 配下の成果物を保存済み領域へコピーする。"""
        candidate_path = _candidate_path(candidate_relative_path)
        mime_type = self._mime_type(candidate_path)
        artifacts_root = (session_workdir / "artifacts").resolve()
        source_path = (session_workdir / candidate_path).resolve()
        if not source_path.is_relative_to(artifacts_root):
            raise ArtifactNotDisplayableError()
        if not source_path.exists() or not source_path.is_file():
            raise ArtifactNotFoundError()

        saved_relative_path = _saved_relative_path(run_id, artifact_id, candidate_path)
        saved_path = self._resolve_saved_output_path(saved_relative_path)
        if saved_path.exists():
            raise ArtifactAlreadySavedError()

        try:
            saved_path.parent.mkdir(parents=True, exist_ok=True)
            copy2(source_path, saved_path)
        except OSError as exc:
            raise AppError(
                ErrorType.SYSTEM,
                trace=True,
                diagnostic_message="成果物の保存に失敗しました。",
                cause=exc,
            ) from exc

        return SavedArtifactFile(
            artifact_id=artifact_id,
            mime_type=mime_type,
            relative_path=saved_relative_path.as_posix(),
        )

    def open_saved_file(self, relative_path: str, mime_type: str) -> OpenedArtifactFile:
        """保存済み成果物領域内のファイルを配信用に開く。"""
        saved_relative_path = _safe_relative_path(relative_path)
        if len(saved_relative_path.parts) != 2:
            raise ArtifactNotDisplayableError()
        expected_mime_type = self._mime_type(saved_relative_path)
        if mime_type != expected_mime_type:
            raise ArtifactNotDisplayableError()

        saved_path = self._resolve_saved_output_path(saved_relative_path)
        if not saved_path.exists() or not saved_path.is_file():
            raise ArtifactNotFoundError()
        return OpenedArtifactFile(path=saved_path, mime_type=mime_type)

    def delete_saved_artifacts(self, storage_paths: tuple[str, ...]) -> None:
        """保存済み成果物実体と空の親runディレクトリを削除する。"""
        for storage_path in storage_paths:
            saved_relative_path = _safe_relative_path(storage_path)
            if len(saved_relative_path.parts) != 2:
                raise ArtifactNotDisplayableError()
            saved_path = self._resolve_saved_output_path(saved_relative_path)
            try:
                saved_path.unlink(missing_ok=True)
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise AppError(
                    ErrorType.SYSTEM,
                    trace=True,
                    diagnostic_message="保存済み成果物の削除に失敗しました。",
                    cause=exc,
                ) from exc

            try:
                saved_path.parent.rmdir()
            except FileNotFoundError:
                continue
            except OSError as exc:
                if saved_path.parent.exists() and any(saved_path.parent.iterdir()):
                    continue
                raise AppError(
                    ErrorType.SYSTEM,
                    trace=True,
                    diagnostic_message="保存済み成果物の削除に失敗しました。",
                    cause=exc,
                ) from exc

    def _mime_type(self, relative_path: PurePosixPath) -> str:
        mime_type = _MIME_TYPE_BY_SUFFIX.get(relative_path.suffix.lower())
        if mime_type is None or mime_type not in self._allowed_mime_types:
            raise ArtifactNotDisplayableError()
        return mime_type

    def _resolve_saved_output_path(self, relative_path: PurePosixPath) -> Path:
        saved_root = self._saved_artifacts_dir.resolve()
        saved_path = (saved_root / Path(*relative_path.parts)).resolve()
        if not saved_path.is_relative_to(saved_root):
            raise ArtifactNotDisplayableError()
        return saved_path


def _candidate_path(candidate_relative_path: str) -> PurePosixPath:
    relative_path = _safe_relative_path(candidate_relative_path)
    if len(relative_path.parts) < 2 or relative_path.parts[0].lower() != "artifacts":
        raise ArtifactNotDisplayableError()
    return relative_path


def _safe_relative_path(relative_path: str) -> PurePosixPath:
    if "\x00" in relative_path:
        raise ArtifactNotDisplayableError()
    normalized = relative_path.replace("\\", "/")
    if normalized.startswith("//") or _has_windows_drive(normalized):
        raise ArtifactNotDisplayableError()
    posix_path = PurePosixPath(normalized)
    if posix_path.is_absolute():
        raise ArtifactNotDisplayableError()
    if any(part in {"", ".", ".."} for part in posix_path.parts):
        raise ArtifactNotDisplayableError()
    return posix_path


def _has_windows_drive(path: str) -> bool:
    return len(path) >= 2 and path[1] == ":" and path[0].isalpha()


def _saved_relative_path(
    run_id: UUID,
    artifact_id: UUID,
    candidate_path: PurePosixPath,
) -> PurePosixPath:
    return PurePosixPath(str(run_id), f"{artifact_id}{candidate_path.suffix.lower()}")

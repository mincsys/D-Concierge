from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from shutil import copy2
from uuid import UUID

from backend.shared.errors import AppError, ErrorClass

_MIME_TYPE_BY_SUFFIX = {
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".html": "text/html",
    ".csv": "text/csv",
}
_DEFAULT_ALLOWED_MIME_TYPES = tuple(_MIME_TYPE_BY_SUFFIX.values())


@dataclass(frozen=True, slots=True)
class SavedArtifactFile:
    """保存済みCodex成果物のDB保存用メタ情報。"""

    artifact_id: UUID
    mime_type: str
    relative_path: str


@dataclass(frozen=True, slots=True)
class OpenedArtifactFile:
    """配信可能な保存済みCodex成果物ファイル。"""

    path: Path
    mime_type: str


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
            raise AppError(ErrorClass.FORBIDDEN, "対象の成果物は表示できません。")
        if not source_path.exists() or not source_path.is_file():
            raise AppError(ErrorClass.NOT_FOUND, "対象の成果物が見つかりません。")

        saved_relative_path = _saved_relative_path(run_id, artifact_id, candidate_path)
        saved_path = self._resolve_saved_output_path(saved_relative_path)
        if saved_path.exists():
            raise AppError(ErrorClass.CONFLICT, "対象の成果物は保存済みです。")

        try:
            saved_path.parent.mkdir(parents=True, exist_ok=True)
            copy2(source_path, saved_path)
        except OSError as exc:
            raise AppError(ErrorClass.SYSTEM, "成果物の保存に失敗しました。") from exc

        return SavedArtifactFile(
            artifact_id=artifact_id,
            mime_type=mime_type,
            relative_path=saved_relative_path.as_posix(),
        )

    def open_saved_file(self, relative_path: str, mime_type: str) -> OpenedArtifactFile:
        """保存済み成果物領域内のファイルを配信用に開く。"""
        saved_relative_path = _safe_relative_path(relative_path)
        if len(saved_relative_path.parts) != 2:
            raise AppError(ErrorClass.FORBIDDEN, "対象の成果物は表示できません。")
        expected_mime_type = self._mime_type(saved_relative_path)
        if mime_type != expected_mime_type:
            raise AppError(ErrorClass.FORBIDDEN, "対象の成果物は表示できません。")

        saved_path = self._resolve_saved_output_path(saved_relative_path)
        if not saved_path.exists() or not saved_path.is_file():
            raise AppError(ErrorClass.NOT_FOUND, "対象の成果物が見つかりません。")
        return OpenedArtifactFile(path=saved_path, mime_type=mime_type)

    def _mime_type(self, relative_path: PurePosixPath) -> str:
        mime_type = _MIME_TYPE_BY_SUFFIX.get(relative_path.suffix.lower())
        if mime_type is None or mime_type not in self._allowed_mime_types:
            raise AppError(ErrorClass.FORBIDDEN, "対象の成果物は表示できません。")
        return mime_type

    def _resolve_saved_output_path(self, relative_path: PurePosixPath) -> Path:
        saved_root = self._saved_artifacts_dir.resolve()
        saved_path = (saved_root / Path(*relative_path.parts)).resolve()
        if not saved_path.is_relative_to(saved_root):
            raise AppError(ErrorClass.FORBIDDEN, "対象の成果物は表示できません。")
        return saved_path


def _candidate_path(candidate_relative_path: str) -> PurePosixPath:
    relative_path = _safe_relative_path(candidate_relative_path)
    if len(relative_path.parts) < 2 or relative_path.parts[0].lower() != "artifacts":
        raise AppError(ErrorClass.FORBIDDEN, "対象の成果物は表示できません。")
    return relative_path


def _safe_relative_path(relative_path: str) -> PurePosixPath:
    if "\x00" in relative_path:
        raise AppError(ErrorClass.FORBIDDEN, "対象の成果物は表示できません。")
    normalized = relative_path.replace("\\", "/")
    if normalized.startswith("//") or _has_windows_drive(normalized):
        raise AppError(ErrorClass.FORBIDDEN, "対象の成果物は表示できません。")
    posix_path = PurePosixPath(normalized)
    if posix_path.is_absolute():
        raise AppError(ErrorClass.FORBIDDEN, "対象の成果物は表示できません。")
    if any(part in {"", ".", ".."} for part in posix_path.parts):
        raise AppError(ErrorClass.FORBIDDEN, "対象の成果物は表示できません。")
    return posix_path


def _has_windows_drive(path: str) -> bool:
    return len(path) >= 2 and path[1] == ":" and path[0].isalpha()


def _saved_relative_path(
    run_id: UUID,
    artifact_id: UUID,
    candidate_path: PurePosixPath,
) -> PurePosixPath:
    return PurePosixPath(str(run_id), f"{artifact_id}{candidate_path.suffix.lower()}")

from pathlib import Path
from shutil import rmtree
from uuid import UUID

from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError


class CodexSessionWorkdirCleanup:
    """生成用・検証用Codexセッション作業領域を削除する。"""

    def __init__(self, generation_workdir: Path, validation_workdir: Path) -> None:
        self._generation_workdir = generation_workdir
        self._validation_workdir = validation_workdir

    def delete_session_workdirs(self, user_id: str, session_id: UUID) -> None:
        """対象利用者・セッションの作業領域を削除する。"""
        for base_workdir in (self._generation_workdir, self._validation_workdir):
            self._delete_one(base_workdir, user_id, session_id)

    def delete_user_workdirs(self, user_id: str) -> None:
        """対象ユーザの作業領域を削除する。"""
        for base_workdir in (self._generation_workdir, self._validation_workdir):
            self._delete_user_one(base_workdir, user_id)

    def _delete_one(self, base_workdir: Path, user_id: str, session_id: UUID) -> None:
        base = base_workdir.resolve()
        session_dir = (base_workdir / user_id / str(session_id)).resolve()
        if not session_dir.is_relative_to(base):
            raise AppError(
                ErrorType.SYSTEM,
                trace=True,
                diagnostic_message="Codex作業領域の削除対象パスが不正です。",
            )
        if not session_dir.exists():
            return
        try:
            rmtree(session_dir)
        except OSError as exc:
            raise AppError(
                ErrorType.SYSTEM,
                trace=True,
                diagnostic_message="Codex作業領域の削除に失敗しました。",
                cause=exc,
            ) from exc

    def _delete_user_one(self, base_workdir: Path, user_id: str) -> None:
        base = base_workdir.resolve()
        user_dir = (base_workdir / user_id).resolve()
        if not user_dir.is_relative_to(base):
            raise AppError(
                ErrorType.SYSTEM,
                trace=True,
                diagnostic_message="Codex作業領域の削除対象パスが不正です。",
            )
        if not user_dir.exists():
            return
        try:
            rmtree(user_dir)
        except OSError as exc:
            raise AppError(
                ErrorType.SYSTEM,
                trace=True,
                diagnostic_message="Codex作業領域の削除に失敗しました。",
                cause=exc,
            ) from exc

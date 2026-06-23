from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from backend.infrastructure.filesystem.path_security import PathSecurityService


@dataclass(frozen=True, slots=True)
class CodexSessionWorkdirCleanup:
    """生成用・検証用Codex作業領域を削除する。"""

    generator_workdir_root: Path
    validator_workdir_root: Path
    path_security: PathSecurityService = PathSecurityService()

    def delete_session_workdirs(self, user_id: str, session_id: UUID) -> None:
        """ユーザ配下のセッション単位作業領域を削除する。"""

        relative_path = f"{user_id}/{session_id}"
        self._delete_directory_if_exists(self.generator_workdir_root, relative_path)
        self._delete_directory_if_exists(self.validator_workdir_root, relative_path)
        self._remove_empty_user_dir(self.generator_workdir_root, user_id)
        self._remove_empty_user_dir(self.validator_workdir_root, user_id)

    def delete_user_workdirs(self, user_id: str) -> None:
        """ユーザ単位作業領域を削除する。"""

        self._delete_directory_if_exists(self.generator_workdir_root, user_id)
        self._delete_directory_if_exists(self.validator_workdir_root, user_id)

    def _delete_directory_if_exists(self, root: Path, relative_path: str) -> None:
        target = self.path_security.resolve_under_root(root, relative_path)
        if not target.exists():
            return
        if not target.is_dir():
            raise RuntimeError(f"Codex作業領域を削除できません: {target}")
        try:
            shutil.rmtree(target)
        except OSError as error:
            raise RuntimeError(
                f"Codex作業領域を削除できません: {target}: {error}",
            ) from error

    def _remove_empty_user_dir(self, root: Path, user_id: str) -> None:
        user_dir = self.path_security.resolve_under_root(root, user_id)
        try:
            user_dir.rmdir()
        except OSError:
            return

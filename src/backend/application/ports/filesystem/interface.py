from pathlib import Path
from typing import Protocol
from uuid import UUID

from backend.application.ports.filesystem.dto import (
    OpenedArtifactFile,
    OpenedReferenceFile,
    SavedArtifactFile,
)


class AdoptedArtifactStorePort(Protocol):
    """採用済み成果物ファイル保存境界。"""

    def save_adopted_file(
        self,
        session_workdir: Path,
        candidate_relative_path: str,
        artifact_id: UUID,
    ) -> SavedArtifactFile:
        """成果物候補を保存済み領域へコピーする。"""


class ArtifactStorePort(AdoptedArtifactStorePort, Protocol):
    """採用済み成果物ファイル保存・読込境界。"""

    def open_saved_file(self, relative_path: str, mime_type: str) -> OpenedArtifactFile:
        """保存済み成果物領域内のファイルを配信用に開く。"""

    def delete_saved_artifacts(self, storage_paths: tuple[str, ...]) -> None:
        """保存済み成果物実体と空の親セッションディレクトリを削除する。"""


class SavedArtifactDeletionPort(Protocol):
    """保存済み成果物実体の削除境界。"""

    def delete_saved_artifacts(self, storage_paths: tuple[str, ...]) -> None:
        """保存済み成果物実体と空の親セッションディレクトリを削除する。"""


class UserSavedArtifactDeletionPort(Protocol):
    """ユーザ単位の保存済み成果物削除境界。"""

    def delete_user_artifacts(self, user_id: str) -> None:
        """ユーザ単位の保存済み成果物領域を削除する。"""


class ReferenceStorePort(Protocol):
    """参照元PDFファイル読込境界。"""

    def open_reference_file(self, relative_path: str) -> OpenedReferenceFile:
        """共有データソース領域内のPDFを配信用に開く。"""


class SessionWorkdirCleanupPort(Protocol):
    """チャット単位のCodex作業領域削除境界。"""

    def delete_session_workdirs(self, user_id: str, session_id: UUID) -> None:
        """生成用・検証用セッション作業領域を削除する。"""


class UserWorkdirCleanupPort(Protocol):
    """ユーザ単位のCodex作業領域削除境界。"""

    def delete_user_workdirs(self, user_id: str) -> None:
        """生成用・検証用のユーザ単位作業領域を削除する。"""

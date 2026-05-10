from pathlib import Path
from typing import Protocol
from uuid import UUID

from backend.application.ports.filesystem.dto import (
    OpenedArtifactFile,
    SavedArtifactFile,
)


class AdoptedArtifactStorePort(Protocol):
    """採用済み成果物ファイル保存境界。"""

    def save_adopted_file(
        self,
        session_workdir: Path,
        candidate_relative_path: str,
        run_id: UUID,
        artifact_id: UUID,
    ) -> SavedArtifactFile:
        """成果物候補を保存済み領域へコピーする。"""


class ArtifactStorePort(AdoptedArtifactStorePort, Protocol):
    """採用済み成果物ファイル保存・読込境界。"""

    def open_saved_file(self, relative_path: str, mime_type: str) -> OpenedArtifactFile:
        """保存済み成果物領域内のファイルを配信用に開く。"""

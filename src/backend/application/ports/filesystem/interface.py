from __future__ import annotations

from typing import Protocol

from backend.application.ports.database.dto import ArtifactData
from backend.application.ports.filesystem.dto import (
    AdoptedArtifactSaveRequest,
    AdoptedArtifactSaveResult,
    OpenedArtifactFile,
    OpenedReferenceFile,
)


class AdoptedArtifactStorePort(Protocol):
    """採用済み成果物のファイル保存境界。"""

    def save_adopted_artifact(
        self,
        source: AdoptedArtifactSaveRequest,
    ) -> AdoptedArtifactSaveResult: ...


class ReferenceStorePort(Protocol):
    """共有データソース内の参照元PDF配信境界。"""

    def open_reference_file(self, relative_path: str) -> OpenedReferenceFile: ...


class ArtifactStorePort(Protocol):
    """保存済みCodex成果物の配信境界。"""

    def open_saved_file(self, artifact: ArtifactData) -> OpenedArtifactFile: ...


class SavedArtifactDeletionPort(Protocol):
    """保存済みCodex成果物の削除境界。"""

    def delete_saved_files(self, storage_paths: tuple[str, ...]) -> tuple[str, ...]: ...

    def delete_user_saved_artifacts(self, user_id: str) -> None: ...

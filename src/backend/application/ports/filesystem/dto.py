from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AdoptedArtifactSaveRequest:
    """採用済み成果物保存要求DTO。"""

    user_id: str
    session_id: UUID
    artifacts_dir: Path
    relative_path: str


@dataclass(frozen=True, slots=True)
class AdoptedArtifactSaveResult:
    """採用済み成果物保存結果DTO。"""

    artifact_id: str
    storage_path: str
    public_url: str
    mime_type: str


@dataclass(frozen=True, slots=True)
class OpenedReferenceFile:
    """参照元PDF配信用に開いたファイルDTO。"""

    file_path: Path
    mime_type: str


@dataclass(frozen=True, slots=True)
class OpenedArtifactFile:
    """Codex成果物配信用に開いたファイルDTO。"""

    file_path: Path
    mime_type: str


@dataclass(frozen=True, slots=True)
class SavedArtifactFile:
    """保存済みCodex成果物ファイルDTO。"""

    storage_path: str
    mime_type: str

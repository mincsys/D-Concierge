from dataclasses import dataclass
from pathlib import Path
from uuid import UUID


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


@dataclass(frozen=True, slots=True)
class OpenedReferenceFile:
    """配信可能な参照元PDFファイル。"""

    path: Path
    mime_type: str

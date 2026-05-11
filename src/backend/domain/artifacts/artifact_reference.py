from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import UUID


class InvalidArtifactReferenceError(ValueError):
    """成果物参照が成立しないことを示すドメインエラー。"""


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    """保存済みCodex成果物の参照情報。"""

    artifact_id: UUID
    mime_type: str
    relative_path: str

    def __post_init__(self) -> None:
        if self.mime_type.strip() == "":
            raise InvalidArtifactReferenceError("成果物MIMEタイプが不正です。")
        if "\x00" in self.relative_path or "\\" in self.relative_path:
            raise InvalidArtifactReferenceError("成果物pathが不正です。")
        path = PurePosixPath(self.relative_path)
        if (
            path.is_absolute()
            or len(path.parts) == 0
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise InvalidArtifactReferenceError("成果物pathが不正です。")

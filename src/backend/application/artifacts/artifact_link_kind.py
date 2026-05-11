from enum import Enum


class ArtifactLinkKind(Enum):
    """回答本文内の成果物リンク種別。"""

    IMAGE = "image"
    LINK = "link"

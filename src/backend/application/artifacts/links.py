from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ArtifactLinkKind(StrEnum):
    """回答本文内の成果物リンク種別。"""

    IMAGE = "image"
    LINK = "link"


@dataclass(frozen=True, slots=True)
class ArtifactLink:
    """回答本文から抽出した成果物リンク。"""

    original: str
    relative_path: str
    kind: ArtifactLinkKind


_MARKDOWN_LINK_PATTERN = re.compile(r"(!)?\[[^\]]*]\(([^)\s]+)\)")
_HTML_ATTRIBUTE_PATTERN = re.compile(
    r"""\b(href|src)\s*=\s*["']([^"'\s]+)["']""",
    re.IGNORECASE,
)
_IMAGE_SUFFIXES = frozenset({".svg", ".png", ".jpg", ".jpeg"})
_LINK_SUFFIXES = frozenset({".svg", ".png", ".jpg", ".jpeg", ".html", ".csv"})


def extract_artifact_links(markdown: str) -> tuple[ArtifactLink, ...]:
    """Markdown/HTML内の成果物候補リンクを抽出する。"""

    links: list[ArtifactLink] = []
    for match in _MARKDOWN_LINK_PATTERN.finditer(markdown):
        original = match.group(2)
        kind = ArtifactLinkKind.IMAGE if match.group(1) else ArtifactLinkKind.LINK
        if _is_artifact_candidate(original):
            links.append(
                ArtifactLink(
                    original=original,
                    relative_path=original.removeprefix("./"),
                    kind=kind,
                )
            )
    for match in _HTML_ATTRIBUTE_PATTERN.finditer(markdown):
        attribute = match.group(1).lower()
        original = match.group(2)
        kind = ArtifactLinkKind.IMAGE if attribute == "src" else ArtifactLinkKind.LINK
        if _is_artifact_candidate(original):
            links.append(
                ArtifactLink(
                    original=original,
                    relative_path=original.removeprefix("./"),
                    kind=kind,
                )
            )
    return tuple(links)


def normalize_artifact_path(link: ArtifactLink) -> str | None:
    """成果物リンクを保存可能な相対パスへ正規化する。"""

    if "://" in link.original:
        return None
    normalized = link.original.replace("\\", "/").removeprefix("./")
    path = Path(normalized)
    if path.is_absolute() or ".." in path.parts:
        return None
    if not normalized.startswith("artifacts/"):
        return None
    if path.suffix.lower() not in _allowed_suffixes(link.kind):
        return None
    return normalized


def artifact_diagnostics(
    artifacts_dir: Path,
    links: tuple[ArtifactLink, ...],
) -> tuple[str, ...]:
    """固定検証で不正と判断した成果物リンクを返す。"""

    diagnostics: list[str] = []
    for link in links:
        normalized = normalize_artifact_path(link)
        if normalized is None:
            diagnostics.append(link.original)
            continue
        candidate = artifacts_dir / normalized.removeprefix("artifacts/")
        try:
            if not candidate.resolve().is_relative_to(artifacts_dir.resolve()):
                diagnostics.append(link.original)
                continue
        except OSError:
            diagnostics.append(link.original)
            continue
        if not candidate.is_file():
            diagnostics.append(link.original)
    return tuple(diagnostics)


def _is_artifact_candidate(value: str) -> bool:
    normalized = value.removeprefix("./")
    return normalized.startswith("artifacts/") or value.startswith(
        ("../", "/", "http"),
    )


def _allowed_suffixes(kind: ArtifactLinkKind) -> frozenset[str]:
    if kind is ArtifactLinkKind.IMAGE:
        return _IMAGE_SUFFIXES
    return _LINK_SUFFIXES

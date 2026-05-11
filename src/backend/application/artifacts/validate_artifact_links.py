import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from backend.application.artifacts.artifact_link_kind import ArtifactLinkKind

_IMAGE_SUFFIXES = frozenset((".svg", ".png", ".jpg", ".jpeg"))
_LINK_SUFFIXES = frozenset((".svg", ".png", ".jpg", ".jpeg", ".html", ".csv"))

_MARKDOWN_LINK_PATTERN = re.compile(r"(?P<image>!)?\[[^\]\n]*\]\((?P<target>[^)\s]+)\)")
_HTML_LINK_PATTERN = re.compile(
    r"\b(?P<attr>src|href)\s*=\s*[\"'](?P<target>[^\"']+)[\"']",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ArtifactLink:
    """回答本文内の成果物リンク候補。"""

    start: int
    end: int
    raw_target: str
    normalized_target: str | None
    kind: ArtifactLinkKind


@dataclass(frozen=True, slots=True)
class ArtifactLinkValidationResult:
    """成果物リンク固定検証結果。"""

    valid: bool
    has_artifact_links: bool
    regeneration_instruction: str = ""


class ArtifactLinkValidator:
    """回答本文内のCodex成果物リンクを固定検証する。"""

    def validate(
        self,
        markdowns: tuple[str, ...],
        session_workdir: Path | None,
    ) -> ArtifactLinkValidationResult:
        links = tuple(
            link for markdown in markdowns for link in extract_artifact_links(markdown)
        )
        artifact_links = tuple(
            link for link in links if link.normalized_target is not None
        )
        invalid_targets = tuple(
            link.raw_target for link in links if link.normalized_target is None
        )
        missing_targets: list[str] = []
        disallowed_suffix_targets: list[str] = []

        for link in artifact_links:
            target = link.normalized_target
            if target is None:
                continue
            if not _is_allowed_suffix(target, link.kind):
                disallowed_suffix_targets.append(target)
                continue
            if session_workdir is None or not _is_existing_artifact_file(
                session_workdir=session_workdir,
                normalized_target=target,
            ):
                missing_targets.append(target)

        if invalid_targets or missing_targets or disallowed_suffix_targets:
            return ArtifactLinkValidationResult(
                valid=False,
                has_artifact_links=bool(artifact_links),
                regeneration_instruction=_regeneration_instruction(
                    invalid_targets=invalid_targets,
                    missing_targets=tuple(missing_targets),
                    disallowed_suffix_targets=tuple(disallowed_suffix_targets),
                ),
            )

        return ArtifactLinkValidationResult(
            valid=True,
            has_artifact_links=bool(artifact_links),
        )


def extract_artifact_links(markdown: str) -> tuple[ArtifactLink, ...]:
    """回答本文からMarkdown/HTMLのリンク先を抽出する。"""
    links: list[ArtifactLink] = []
    for match in _MARKDOWN_LINK_PATTERN.finditer(markdown):
        links.append(
            ArtifactLink(
                start=match.start("target"),
                end=match.end("target"),
                raw_target=match.group("target"),
                normalized_target=_normalize_artifact_target(match.group("target")),
                kind=ArtifactLinkKind.IMAGE
                if match.group("image")
                else ArtifactLinkKind.LINK,
            )
        )
    for match in _HTML_LINK_PATTERN.finditer(markdown):
        links.append(
            ArtifactLink(
                start=match.start("target"),
                end=match.end("target"),
                raw_target=match.group("target"),
                normalized_target=_normalize_artifact_target(match.group("target")),
                kind=ArtifactLinkKind.IMAGE
                if match.group("attr").lower() == "src"
                else ArtifactLinkKind.LINK,
            )
        )
    return _without_overlaps(
        tuple(sorted(links, key=lambda item: (item.start, item.end)))
    )


def _normalize_artifact_target(target: str) -> str | None:
    if target.startswith("./artifacts/"):
        return target[2:]
    if target.startswith("artifacts/"):
        return target
    return None


def _without_overlaps(links: tuple[ArtifactLink, ...]) -> tuple[ArtifactLink, ...]:
    selected: list[ArtifactLink] = []
    latest_end = -1
    for link in links:
        if link.start >= latest_end:
            selected.append(link)
            latest_end = link.end
    return tuple(selected)


def _is_allowed_suffix(target: str, kind: ArtifactLinkKind) -> bool:
    suffix = PurePosixPath(target).suffix.lower()
    if kind is ArtifactLinkKind.IMAGE:
        return suffix in _IMAGE_SUFFIXES
    return suffix in _LINK_SUFFIXES


def _is_existing_artifact_file(
    *,
    session_workdir: Path,
    normalized_target: str,
) -> bool:
    try:
        relative_path = _safe_artifact_relative_path(normalized_target)
        artifacts_root = (session_workdir / "artifacts").resolve()
        target_path = (session_workdir / Path(*relative_path.parts)).resolve()
    except OSError:
        return False
    return target_path.is_relative_to(artifacts_root) and target_path.is_file()


def _safe_artifact_relative_path(normalized_target: str) -> PurePosixPath:
    posix_path = PurePosixPath(normalized_target.replace("\\", "/"))
    if (
        posix_path.is_absolute()
        or len(posix_path.parts) < 2
        or posix_path.parts[0] != "artifacts"
        or any(part in {"", ".", ".."} for part in posix_path.parts)
    ):
        raise OSError("invalid artifact path")
    return posix_path


def _regeneration_instruction(
    *,
    invalid_targets: tuple[str, ...],
    missing_targets: tuple[str, ...],
    disallowed_suffix_targets: tuple[str, ...],
) -> str:
    lines = [
        "成果物リンクが不正なため、この回答は採用できません。",
    ]
    _append_issue_lines(lines, "許可されていない成果物リンク", invalid_targets)
    _append_issue_lines(lines, "存在しない成果物ファイル", missing_targets)
    _append_issue_lines(
        lines, "許可されていない成果物拡張子", disallowed_suffix_targets
    )
    lines.extend(
        [
            "回答本文は前回同様にユーザ質問へ完全に回答してください。",
            "成果物リンクは `artifacts/...` または `./artifacts/...` 形式で、"
            "生成用Codexの `artifacts/` 配下に存在するファイルだけを指定してください。",
        ]
    )
    return "\n".join(lines)


def _append_issue_lines(
    lines: list[str], heading: str, targets: tuple[str, ...]
) -> None:
    if not targets:
        return
    lines.append(f"{heading}:")
    lines.extend(f"- {target}" for target in targets)

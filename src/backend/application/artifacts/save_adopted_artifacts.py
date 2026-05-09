import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from backend.infrastructure.filesystem.artifacts.file_artifact_store import (
    SavedArtifactFile,
)


@dataclass(frozen=True, slots=True)
class SavedAnswerBlocksArtifacts:
    """成果物URL置換後の回答ブロック本文と保存済み成果物メタ情報。"""

    markdowns: tuple[str, ...]
    artifacts: tuple[SavedArtifactFile, ...]


class ArtifactStore(Protocol):
    """採用済み成果物ファイル保存境界。"""

    def save_adopted_file(
        self,
        session_workdir: Path,
        candidate_relative_path: str,
        run_id: UUID,
        artifact_id: UUID,
    ) -> SavedArtifactFile:
        """成果物候補を保存済み領域へコピーする。"""
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class _ArtifactReferenceSpan:
    start: int
    end: int
    candidate_relative_path: str


@dataclass(frozen=True, slots=True)
class _Replacement:
    start: int
    end: int
    value: str


_MARKDOWN_ARTIFACT_PATTERN = re.compile(
    r"!?\[[^\]\n]*\]\((?P<path>(?:\./)?artifacts/[^)\s]+)\)"
)
_HTML_ARTIFACT_PATTERN = re.compile(
    r"\b(?:src|href)\s*=\s*[\"'](?P<path>(?:\./)?artifacts/[^\"']+)[\"']",
    re.IGNORECASE,
)


class SaveAdoptedArtifactsUseCase:
    """採用済み回答が参照するCodex成果物を保存し、回答URLを置換する。"""

    def __init__(
        self,
        artifact_store: ArtifactStore,
        artifact_id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._artifact_store = artifact_store
        self._artifact_id_factory = artifact_id_factory

    def save_for_answer_blocks(
        self,
        markdowns: tuple[str, ...],
        run_id: UUID,
        session_workdir: Path,
        trace_id: str,
    ) -> SavedAnswerBlocksArtifacts:
        """回答ブロック本文内の一時成果物参照を保存済み成果物URLへ置換する。"""
        _ = trace_id
        saved_by_candidate: dict[str, SavedArtifactFile] = {}
        saved_artifacts: list[SavedArtifactFile] = []
        replaced_markdowns: list[str] = []

        for markdown in markdowns:
            replacements: list[_Replacement] = []
            for span in _extract_artifact_reference_spans(markdown):
                saved = saved_by_candidate.get(span.candidate_relative_path)
                if saved is None:
                    artifact_id = self._artifact_id_factory()
                    saved = self._artifact_store.save_adopted_file(
                        session_workdir=session_workdir,
                        candidate_relative_path=span.candidate_relative_path,
                        run_id=run_id,
                        artifact_id=artifact_id,
                    )
                    saved_by_candidate[span.candidate_relative_path] = saved
                    saved_artifacts.append(saved)
                replacements.append(
                    _Replacement(
                        start=span.start,
                        end=span.end,
                        value=f"/api/artifacts/{saved.artifact_id}",
                    )
                )
            replaced_markdowns.append(_replace_spans(markdown, replacements))

        return SavedAnswerBlocksArtifacts(
            markdowns=tuple(replaced_markdowns),
            artifacts=tuple(saved_artifacts),
        )


def _extract_artifact_reference_spans(
    markdown: str,
) -> tuple[_ArtifactReferenceSpan, ...]:
    spans = [
        _span_from_match(match)
        for pattern in (_MARKDOWN_ARTIFACT_PATTERN, _HTML_ARTIFACT_PATTERN)
        for match in pattern.finditer(markdown)
    ]
    selected: list[_ArtifactReferenceSpan] = []
    latest_end = -1
    for span in sorted(spans, key=lambda item: (item.start, item.end)):
        if span.start >= latest_end:
            selected.append(span)
            latest_end = span.end
    return tuple(selected)


def _span_from_match(match: re.Match[str]) -> _ArtifactReferenceSpan:
    raw_path = match.group("path")
    return _ArtifactReferenceSpan(
        start=match.start("path"),
        end=match.end("path"),
        candidate_relative_path=_normalize_candidate_reference(raw_path),
    )


def _normalize_candidate_reference(raw_path: str) -> str:
    if raw_path.startswith("./"):
        return raw_path[2:]
    return raw_path


def _replace_spans(markdown: str, replacements: list[_Replacement]) -> str:
    current = markdown
    for replacement in sorted(replacements, key=lambda item: item.start, reverse=True):
        current = (
            current[: replacement.start]
            + replacement.value
            + current[replacement.end :]
        )
    return current

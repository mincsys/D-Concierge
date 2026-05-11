from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from backend.application.artifacts.validate_artifact_links import extract_artifact_links
from backend.application.ports.filesystem.dto import (
    SavedArtifactFile,
)
from backend.application.ports.filesystem.interface import AdoptedArtifactStorePort
from backend.application.ports.runtime.interface import IdGeneratorPort


@dataclass(frozen=True, slots=True)
class SavedAnswerBlockArtifacts:
    """成果物URL置換後の回答ブロック本文と保存済み成果物メタ情報。"""

    markdown: str
    artifacts: tuple[SavedArtifactFile, ...]


@dataclass(frozen=True, slots=True)
class SavedAnswerBlocksArtifacts:
    """成果物URL置換後の回答ブロック配列。"""

    blocks: tuple[SavedAnswerBlockArtifacts, ...]


@dataclass(frozen=True, slots=True)
class _Replacement:
    start: int
    end: int
    value: str


class SaveAdoptedArtifactsUseCase:
    """採用済み回答が参照するCodex成果物を保存し、回答URLを置換する。"""

    def __init__(
        self,
        artifact_store: AdoptedArtifactStorePort,
        artifact_id_factory: Callable[[], UUID] | None = None,
        id_generator: IdGeneratorPort | None = None,
    ) -> None:
        self._artifact_store = artifact_store
        if artifact_id_factory is not None:
            self._artifact_id_factory = artifact_id_factory
        elif id_generator is not None:
            self._artifact_id_factory = id_generator.new_uuid
        else:
            raise ValueError("成果物ID発番境界が指定されていません。")

    def save_for_answer_blocks(
        self,
        markdowns: tuple[str, ...],
        run_id: UUID,
        session_workdir: Path,
        trace_id: str,
    ) -> SavedAnswerBlocksArtifacts:
        """回答ブロック本文内の一時成果物参照を保存済み成果物URLへ置換する。"""
        _ = trace_id
        blocks: list[SavedAnswerBlockArtifacts] = []

        for markdown in markdowns:
            replacements: list[_Replacement] = []
            saved_artifacts: list[SavedArtifactFile] = []
            for link in extract_artifact_links(markdown):
                if link.normalized_target is None:
                    continue
                artifact_id = self._artifact_id_factory()
                saved = self._artifact_store.save_adopted_file(
                    session_workdir=session_workdir,
                    candidate_relative_path=link.normalized_target,
                    run_id=run_id,
                    artifact_id=artifact_id,
                )
                saved_artifacts.append(saved)
                replacements.append(
                    _Replacement(
                        start=link.start,
                        end=link.end,
                        value=f"/api/artifacts/{saved.artifact_id}",
                    )
                )
            blocks.append(
                SavedAnswerBlockArtifacts(
                    markdown=_replace_spans(markdown, replacements),
                    artifacts=tuple(saved_artifacts),
                )
            )

        return SavedAnswerBlocksArtifacts(blocks=tuple(blocks))


def _replace_spans(markdown: str, replacements: list[_Replacement]) -> str:
    current = markdown
    for replacement in sorted(replacements, key=lambda item: item.start, reverse=True):
        current = (
            current[: replacement.start]
            + replacement.value
            + current[replacement.end :]
        )
    return current

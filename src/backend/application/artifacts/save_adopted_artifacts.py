from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from backend.application.artifacts.links import (
    ArtifactLink,
    extract_artifact_links,
    normalize_artifact_path,
)
from backend.application.ports.filesystem.dto import (
    AdoptedArtifactSaveRequest,
    AdoptedArtifactSaveResult,
)
from backend.application.ports.filesystem.interface import AdoptedArtifactStorePort
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError


@dataclass(frozen=True, slots=True)
class SaveAdoptedArtifactsCommand:
    """採用済み成果物保存要求。"""

    user_id: str
    session_id: UUID
    artifacts_dir: Path
    markdown_blocks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SavedArtifactMetadata:
    """回答ブロックに紐付ける保存済み成果物メタ情報。"""

    artifact_id: str | UUID
    storage_path: str
    public_url: str
    mime_type: str


@dataclass(frozen=True, slots=True)
class SavedArtifactBlock:
    """成果物リンク置換後の回答ブロック。"""

    markdown: str
    artifacts: tuple[SavedArtifactMetadata, ...]


@dataclass(frozen=True, slots=True)
class SaveAdoptedArtifactsResult:
    """採用済み成果物保存結果。"""

    blocks: tuple[SavedArtifactBlock, ...]


@dataclass(frozen=True, slots=True)
class SaveAdoptedArtifactsUseCase:
    """回答本文内の成果物リンクを保存済みURLへ置換する。"""

    artifact_store: AdoptedArtifactStorePort

    def execute(
        self,
        command: SaveAdoptedArtifactsCommand,
    ) -> SaveAdoptedArtifactsResult:
        blocks: list[SavedArtifactBlock] = []
        for markdown in command.markdown_blocks:
            blocks.append(self._save_block(command, markdown))
        return SaveAdoptedArtifactsResult(blocks=tuple(blocks))

    def _save_block(
        self,
        command: SaveAdoptedArtifactsCommand,
        markdown: str,
    ) -> SavedArtifactBlock:
        artifacts: list[SavedArtifactMetadata] = []
        replaced_markdown = markdown
        for link in extract_artifact_links(markdown):
            relative_path = _normalize_artifact_path(link)
            _ensure_candidate_file(command.artifacts_dir, relative_path)
            saved = self.artifact_store.save_adopted_artifact(
                AdoptedArtifactSaveRequest(
                    user_id=command.user_id,
                    session_id=command.session_id,
                    artifacts_dir=command.artifacts_dir,
                    relative_path=relative_path,
                )
            )
            artifacts.append(_metadata(saved))
            replaced_markdown = replaced_markdown.replace(
                link.original,
                saved.public_url,
                1,
            )
        return SavedArtifactBlock(
            markdown=replaced_markdown,
            artifacts=tuple(artifacts),
        )


def _normalize_artifact_path(link: ArtifactLink) -> str:
    normalized = normalize_artifact_path(link)
    if normalized is None:
        raise _artifact_error(link.original)
    return normalized


def _ensure_candidate_file(artifacts_dir: Path, relative_path: str) -> None:
    relative_inside_artifacts = relative_path.removeprefix("artifacts/")
    candidate = artifacts_dir / relative_inside_artifacts
    try:
        resolved_root = artifacts_dir.resolve()
        resolved_candidate = candidate.resolve()
    except OSError as error:
        raise AppError(
            error_type=ErrorType.SYSTEM,
            trace=True,
            diagnostic_message=f"成果物候補ファイルを確認できません: {relative_path}",
            cause=error,
        ) from error
    if not resolved_candidate.is_relative_to(resolved_root) or not candidate.is_file():
        raise AppError(
            error_type=ErrorType.SYSTEM,
            trace=True,
            diagnostic_message=f"成果物候補ファイルが見つかりません: {relative_path}",
        )


def _metadata(saved: AdoptedArtifactSaveResult) -> SavedArtifactMetadata:
    return SavedArtifactMetadata(
        artifact_id=saved.artifact_id,
        storage_path=saved.storage_path,
        public_url=saved.public_url,
        mime_type=saved.mime_type,
    )


def _artifact_error(path: str) -> AppError:
    return AppError(
        error_type=ErrorType.SYSTEM,
        trace=True,
        diagnostic_message=f"成果物リンクのパスが不正です: {path}",
    )

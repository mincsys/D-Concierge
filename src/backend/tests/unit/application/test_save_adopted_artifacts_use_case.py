from collections import deque
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pytest

from backend.application.artifacts.save_adopted_artifacts import (
    SaveAdoptedArtifactsUseCase,
    SavedAnswerBlockArtifacts,
    SavedAnswerBlocksArtifacts,
)
from backend.application.ports.filesystem.dto import (
    SavedArtifactFile,
)
from backend.domain.artifacts.artifact_reference import ArtifactReference
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError, ArtifactNotFoundError


def test_save_adopted_artifacts_replaces_markdown_and_html_paths() -> None:
    """観点：採用済み成果物保存。確認：回答内成果物参照をAPI URLへ置換する。"""
    run_id = UUID("00000000-0000-0000-0000-000000000501")
    first_artifact_id = UUID("00000000-0000-0000-0000-000000000511")
    second_artifact_id = UUID("00000000-0000-0000-0000-000000000512")
    store = RecordingArtifactStore()
    usecase = SaveAdoptedArtifactsUseCase(
        artifact_store=store,
        artifact_id_factory=IdFactory((first_artifact_id, second_artifact_id)),
    )

    result = usecase.save_for_answer_blocks(
        markdowns=(
            "![図](artifacts/chart.png)\n"
            '<a href="artifacts/report.html">レポート</a>\n'
            "[保存済み](/api/artifacts/00000000-0000-0000-0000-000000000599)",
        ),
        run_id=run_id,
        session_workdir=Path("/sessions/user/session"),
        trace_id="trace-001",
    )

    assert result == SavedAnswerBlocksArtifacts(
        blocks=(
            SavedAnswerBlockArtifacts(
                markdown=(
                    f"![図](/api/artifacts/{first_artifact_id})\n"
                    f'<a href="/api/artifacts/{second_artifact_id}">レポート</a>\n'
                    "[保存済み](/api/artifacts/00000000-0000-0000-0000-000000000599)"
                ),
                artifacts=(
                    ArtifactReference(
                        artifact_id=first_artifact_id,
                        mime_type="image/png",
                        relative_path=f"{run_id}/{first_artifact_id}.png",
                    ),
                    ArtifactReference(
                        artifact_id=second_artifact_id,
                        mime_type="text/html",
                        relative_path=f"{run_id}/{second_artifact_id}.html",
                    ),
                ),
            ),
        )
    )
    assert store.calls == (
        SaveCall("artifacts/chart.png", run_id, first_artifact_id),
        SaveCall("artifacts/report.html", run_id, second_artifact_id),
    )


def test_save_adopted_artifacts_replaces_normalized_backslash_paths() -> None:
    """観点：採用済み成果物保存。

    確認：区切り文字差分を正規化した成果物参照を保存し、回答URLを置換する。
    """
    run_id = UUID("00000000-0000-0000-0000-000000000506")
    first_artifact_id = UUID("00000000-0000-0000-0000-000000000551")
    second_artifact_id = UUID("00000000-0000-0000-0000-000000000552")
    store = RecordingArtifactStore()
    usecase = SaveAdoptedArtifactsUseCase(
        artifact_store=store,
        artifact_id_factory=IdFactory((first_artifact_id, second_artifact_id)),
    )

    result = usecase.save_for_answer_blocks(
        markdowns=(
            "![図](artifacts\\chart.png)\n"
            '<a href=".\\artifacts\\report.html">レポート</a>',
        ),
        run_id=run_id,
        session_workdir=Path("/sessions/user/session"),
        trace_id="trace-006",
    )

    assert tuple(block.markdown for block in result.blocks) == (
        f"![図](/api/artifacts/{first_artifact_id})\n"
        f'<a href="/api/artifacts/{second_artifact_id}">レポート</a>',
    )
    assert store.calls == (
        SaveCall("artifacts/chart.png", run_id, first_artifact_id),
        SaveCall("artifacts/report.html", run_id, second_artifact_id),
    )


def test_save_adopted_artifacts_saves_duplicate_candidate_each_time() -> None:
    """観点：採用済み成果物保存。確認：同じ候補参照も登場ごとに別成果物として保存する。"""
    run_id = UUID("00000000-0000-0000-0000-000000000502")
    first_artifact_id = UUID("00000000-0000-0000-0000-000000000521")
    second_artifact_id = UUID("00000000-0000-0000-0000-000000000522")
    store = RecordingArtifactStore()
    usecase = SaveAdoptedArtifactsUseCase(
        artifact_store=store,
        artifact_id_factory=IdFactory((first_artifact_id, second_artifact_id)),
    )

    result = usecase.save_for_answer_blocks(
        markdowns=(
            '![図](artifacts/chart.svg)\n<img src="artifacts/chart.svg" alt="図">',
        ),
        run_id=run_id,
        session_workdir=Path("/sessions/user/session"),
        trace_id="trace-002",
    )

    assert tuple(block.markdown for block in result.blocks) == (
        f"![図](/api/artifacts/{first_artifact_id})\n"
        f'<img src="/api/artifacts/{second_artifact_id}" alt="図">',
    )
    assert len(result.blocks[0].artifacts) == 2
    assert store.calls == (
        SaveCall("artifacts/chart.svg", run_id, first_artifact_id),
        SaveCall("artifacts/chart.svg", run_id, second_artifact_id),
    )


def test_save_adopted_artifacts_saves_duplicate_candidate_each_time_across_blocks() -> (
    None
):
    """観点：採用済み成果物保存。確認：複数回答ブロック間の同じ候補参照も別成果物にする。"""
    run_id = UUID("00000000-0000-0000-0000-000000000505")
    first_artifact_id = UUID("00000000-0000-0000-0000-000000000541")
    second_artifact_id = UUID("00000000-0000-0000-0000-000000000542")
    store = RecordingArtifactStore()
    usecase = SaveAdoptedArtifactsUseCase(
        artifact_store=store,
        artifact_id_factory=IdFactory((first_artifact_id, second_artifact_id)),
    )

    result = usecase.save_for_answer_blocks(
        markdowns=(
            "第一回答 ![図](artifacts/chart.svg)",
            '<img src="artifacts/chart.svg" alt="図">',
        ),
        run_id=run_id,
        session_workdir=Path("/sessions/user/session"),
        trace_id="trace-005",
    )

    assert result == SavedAnswerBlocksArtifacts(
        blocks=(
            SavedAnswerBlockArtifacts(
                markdown=f"第一回答 ![図](/api/artifacts/{first_artifact_id})",
                artifacts=(
                    ArtifactReference(
                        artifact_id=first_artifact_id,
                        mime_type="image/svg+xml",
                        relative_path=f"{run_id}/{first_artifact_id}.svg",
                    ),
                ),
            ),
            SavedAnswerBlockArtifacts(
                markdown=f'<img src="/api/artifacts/{second_artifact_id}" alt="図">',
                artifacts=(
                    ArtifactReference(
                        artifact_id=second_artifact_id,
                        mime_type="image/svg+xml",
                        relative_path=f"{run_id}/{second_artifact_id}.svg",
                    ),
                ),
            ),
        )
    )
    assert store.calls == (
        SaveCall("artifacts/chart.svg", run_id, first_artifact_id),
        SaveCall("artifacts/chart.svg", run_id, second_artifact_id),
    )


def test_save_adopted_artifacts_ignores_non_artifact_links() -> None:
    """観点：採用済み成果物保存。確認：共有データソース参照や外部URLを成果物保存しない。"""
    store = RecordingArtifactStore()
    usecase = SaveAdoptedArtifactsUseCase(
        artifact_store=store,
        artifact_id_factory=IdFactory(()),
    )
    markdown = "[資料](readonly/manual.pdf)\nhttps://example.test/artifacts/chart.png"

    result = usecase.save_for_answer_blocks(
        markdowns=(markdown,),
        run_id=UUID("00000000-0000-0000-0000-000000000503"),
        session_workdir=Path("/sessions/user/session"),
        trace_id="trace-003",
    )

    assert result == SavedAnswerBlocksArtifacts(
        blocks=(SavedAnswerBlockArtifacts(markdown=markdown, artifacts=()),)
    )
    assert store.calls == ()


def test_save_adopted_artifacts_propagates_store_rejection() -> None:
    """観点：採用済み成果物保存。確認：保存不可の参照がある場合は回答採用へ進めない。"""
    usecase = SaveAdoptedArtifactsUseCase(
        artifact_store=RejectingArtifactStore(),
        artifact_id_factory=IdFactory((UUID("00000000-0000-0000-0000-000000000531"),)),
    )

    with pytest.raises(AppError) as error_info:
        usecase.save_for_answer_blocks(
            markdowns=("![図](artifacts/missing.png)",),
            run_id=UUID("00000000-0000-0000-0000-000000000504"),
            session_workdir=Path("/sessions/user/session"),
            trace_id="trace-004",
        )

    assert error_info.value.error_type is ErrorType.NOT_FOUND


@dataclass(frozen=True, slots=True)
class SaveCall:
    candidate_relative_path: str
    run_id: UUID
    artifact_id: UUID


class RecordingArtifactStore:
    def __init__(self) -> None:
        self._calls: list[SaveCall] = []

    @property
    def calls(self) -> tuple[SaveCall, ...]:
        return tuple(self._calls)

    def save_adopted_file(
        self,
        session_workdir: Path,
        candidate_relative_path: str,
        run_id: UUID,
        artifact_id: UUID,
    ) -> SavedArtifactFile:
        _ = session_workdir
        self._calls.append(SaveCall(candidate_relative_path, run_id, artifact_id))
        suffix = Path(candidate_relative_path).suffix
        mime_type = {
            ".html": "text/html",
            ".png": "image/png",
            ".svg": "image/svg+xml",
        }[suffix]
        return SavedArtifactFile(
            artifact_id=artifact_id,
            mime_type=mime_type,
            relative_path=f"{run_id}/{artifact_id}{suffix}",
        )


class RejectingArtifactStore:
    def save_adopted_file(
        self,
        session_workdir: Path,
        candidate_relative_path: str,
        run_id: UUID,
        artifact_id: UUID,
    ) -> SavedArtifactFile:
        _ = (session_workdir, candidate_relative_path, run_id, artifact_id)
        raise ArtifactNotFoundError()


class IdFactory:
    def __init__(self, ids: tuple[UUID, ...]) -> None:
        self._ids: deque[UUID] = deque(ids)

    def __call__(self) -> UUID:
        return self._ids.popleft()

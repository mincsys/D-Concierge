import os
import shutil
from pathlib import Path, PurePosixPath
from typing import TypedDict

from backend.domain.answer.answer_candidate import ParsedAnswerCandidate


class ReadonlyReferencePayload(TypedDict):
    """検証用Codexへ渡す参照元情報。"""

    label: str
    relative_path: str
    readonly_path: str
    page_start: int
    page_end: int


class ReadonlyAnswerCandidatePayload(TypedDict):
    """検証用Codexへ渡す回答候補情報。"""

    blocks: list["ReadonlyAnswerBlockPayload"]


class ReadonlyAnswerBlockPayload(TypedDict):
    """検証用Codexへ渡す回答ブロック情報。"""

    markdown: str
    references: list[ReadonlyReferencePayload]


def prepare_generation_session_readonly(
    *,
    workdir: Path,
    datasource_dir: Path,
) -> None:
    """生成用セッション作業領域へ共有データソースを提示する。"""
    _prepare_session_readonly(
        workdir=workdir,
        datasource_dir=datasource_dir,
        include_artifacts=True,
    )


def prepare_validation_session_readonly(
    *,
    workdir: Path,
    datasource_dir: Path,
) -> None:
    """検証用セッション作業領域へ共有データソースを提示する。"""
    _prepare_session_readonly(
        workdir=workdir,
        datasource_dir=datasource_dir,
        include_artifacts=False,
    )


def _prepare_session_readonly(
    *,
    workdir: Path,
    datasource_dir: Path,
    include_artifacts: bool,
) -> None:
    _ensure_runtime_dirs(workdir, include_artifacts=include_artifacts)
    _link_datasource_children(
        datasource_dir=datasource_dir,
        readonly_dir=workdir / "readonly",
    )


def build_readonly_answer_candidate_payload(
    candidate: ParsedAnswerCandidate,
) -> ReadonlyAnswerCandidatePayload:
    """検証対象候補をCodexへ渡すpayloadへ変換する。"""
    return ReadonlyAnswerCandidatePayload(
        blocks=[
            ReadonlyAnswerBlockPayload(
                markdown=block.markdown,
                references=[
                    ReadonlyReferencePayload(
                        label=reference.label,
                        relative_path=reference.relative_path,
                        readonly_path=_readonly_reference_path(reference.relative_path),
                        page_start=reference.page_start,
                        page_end=reference.page_end,
                    )
                    for reference in block.references
                ],
            )
            for block in candidate.blocks
        ],
    )


def _ensure_runtime_dirs(workdir: Path, *, include_artifacts: bool) -> None:
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "tmp").mkdir(parents=True, exist_ok=True)
    if include_artifacts:
        (workdir / "artifacts").mkdir(parents=True, exist_ok=True)


def _link_datasource_children(*, datasource_dir: Path, readonly_dir: Path) -> None:
    _ensure_real_directory(readonly_dir)
    if not datasource_dir.exists():
        return

    for source_child in datasource_dir.iterdir():
        _replace_with_link_or_copy(
            source=source_child,
            destination=readonly_dir / source_child.name,
        )


def _ensure_real_directory(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    path.mkdir(parents=True, exist_ok=True)


def _replace_with_link_or_copy(*, source: Path, destination: Path) -> None:
    if destination.is_symlink() or destination.is_file():
        destination.unlink()
    elif destination.is_dir():
        shutil.rmtree(destination)

    try:
        destination.symlink_to(
            os.path.relpath(source, destination.parent),
            target_is_directory=source.is_dir(),
        )
    except OSError:
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)


def _readonly_reference_path(relative_path: str) -> str:
    return PurePosixPath("readonly", *PurePosixPath(relative_path).parts).as_posix()

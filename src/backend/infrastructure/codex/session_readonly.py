import os
import shutil
from pathlib import Path

from backend.shared.errors.errors import ValidationWorkspacePreparationError


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


def prepare_validation_session_artifacts(
    *,
    validation_workdir: Path,
    generation_workdir: Path,
    has_artifact_links: bool,
) -> None:
    """検証用セッション作業領域へ生成用成果物を提示する。"""
    if not has_artifact_links:
        return

    source = generation_workdir / "artifacts"
    if not source.is_dir():
        raise ValidationWorkspacePreparationError(
            "生成成果物ディレクトリを検証用作業領域へ提示できません。",
        )

    validation_workdir.mkdir(parents=True, exist_ok=True)
    destination = validation_workdir / "artifacts"
    if destination.is_symlink() or destination.is_file():
        destination.unlink()
    elif destination.is_dir():
        shutil.rmtree(destination)

    try:
        destination.symlink_to(
            os.path.relpath(source, destination.parent),
            target_is_directory=True,
        )
    except OSError as exc:
        raise ValidationWorkspacePreparationError(
            "生成成果物ディレクトリを検証用作業領域へ提示できません。",
        ) from exc


def _prepare_session_readonly(
    *,
    workdir: Path,
    datasource_dir: Path,
    include_artifacts: bool,
) -> None:
    _ensure_runtime_dirs(workdir, include_artifacts=include_artifacts)
    _link_datasource_dir(
        datasource_dir=datasource_dir,
        readonly_dir=workdir / "readonly",
    )


def _ensure_runtime_dirs(workdir: Path, *, include_artifacts: bool) -> None:
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "tmp").mkdir(parents=True, exist_ok=True)
    if include_artifacts:
        (workdir / "artifacts").mkdir(parents=True, exist_ok=True)


def _link_datasource_dir(*, datasource_dir: Path, readonly_dir: Path) -> None:
    if not datasource_dir.is_dir():
        raise ValidationWorkspacePreparationError(
            "共有データソースをCodex作業領域へ提示できません。",
        )

    _remove_existing_path(readonly_dir)

    try:
        readonly_dir.symlink_to(
            os.path.relpath(datasource_dir, readonly_dir.parent),
            target_is_directory=True,
        )
    except OSError as exc:
        raise ValidationWorkspacePreparationError(
            "共有データソースをCodex作業領域へ提示できません。",
        ) from exc


def _remove_existing_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)

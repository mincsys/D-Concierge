from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError


@dataclass(frozen=True, slots=True)
class GenerationWorkspace:
    """生成用Codex作業領域。"""

    workdir: Path
    tmp_dir: Path
    artifacts_dir: Path


@dataclass(frozen=True, slots=True)
class ValidationWorkspace:
    """検証用Codex作業領域。"""

    workdir: Path
    tmp_dir: Path


def prepare_generation_workspace(workdir: Path) -> GenerationWorkspace:
    """生成用のtmp/artifactsディレクトリを準備する。"""

    _ensure_directory(workdir)
    tmp_dir = workdir / "tmp"
    artifacts_dir = workdir / "artifacts"
    _ensure_directory(tmp_dir)
    _ensure_directory(artifacts_dir)
    return GenerationWorkspace(
        workdir=workdir,
        tmp_dir=tmp_dir,
        artifacts_dir=artifacts_dir,
    )


def prepare_validation_workspace(workdir: Path) -> ValidationWorkspace:
    """検証用のtmpディレクトリを準備する。"""

    _ensure_directory(workdir)
    tmp_dir = workdir / "tmp"
    _ensure_directory(tmp_dir)
    return ValidationWorkspace(workdir=workdir, tmp_dir=tmp_dir)


def _ensure_directory(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise _workspace_error(path, error) from error
    if not path.is_dir():
        raise _workspace_error(path, None)


def _workspace_error(path: Path, cause: OSError | None) -> AppError:
    return AppError(
        error_type=ErrorType.SYSTEM,
        trace=True,
        diagnostic_message=f"Codex作業領域を作成できません: {path}",
        cause=cause,
    )

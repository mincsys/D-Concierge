from pathlib import Path

from backend.infrastructure.codex.codex_workspace_preparer import (
    prepare_generation_workspace,
    prepare_validation_workspace,
)


def test_prepare_generation_workspace_creates_runtime_directories(
    tmp_path: Path,
) -> None:
    """観点：生成用Codex作業領域。確認：tmpとartifactsを存在保証する。"""
    workdir = tmp_path / "codex" / "sessions" / "demo-user" / "session-001"

    prepare_generation_workspace(workdir)

    assert workdir.is_dir()
    assert (workdir / "tmp").is_dir()
    assert (workdir / "artifacts").is_dir()
    assert not (workdir / "readonly").exists()


def test_prepare_generation_workspace_recreates_runtime_directories(
    tmp_path: Path,
) -> None:
    """観点：生成用Codex作業領域。確認：Codexが削除したtmpとartifactsを再作成する。"""
    workdir = tmp_path / "codex" / "sessions" / "demo-user" / "session-001"
    workdir.mkdir(parents=True)

    prepare_generation_workspace(workdir)

    assert (workdir / "tmp").is_dir()
    assert (workdir / "artifacts").is_dir()


def test_prepare_validation_workspace_creates_tmp_only(tmp_path: Path) -> None:
    """観点：検証用Codex作業領域。確認：tmpを存在保証し、artifactsは作成しない。"""
    workdir = tmp_path / "codex" / "sessions_validator" / "demo-user" / "session-001"

    prepare_validation_workspace(workdir)

    assert workdir.is_dir()
    assert (workdir / "tmp").is_dir()
    assert not (workdir / "artifacts").exists()
    assert not (workdir / "readonly").exists()

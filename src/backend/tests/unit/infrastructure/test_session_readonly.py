from collections.abc import Callable
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from backend.infrastructure.codex.session_readonly import (
    prepare_generation_session_readonly,
    prepare_validation_session_artifacts,
    prepare_validation_session_readonly,
)
from backend.shared.errors import ValidationWorkspacePreparationError

type ReadonlyPreparer = Callable[[Path, Path], None]


def _prepare_generation(workdir: Path, datasource_dir: Path) -> None:
    prepare_generation_session_readonly(
        workdir=workdir,
        datasource_dir=datasource_dir,
    )


def _prepare_validation(workdir: Path, datasource_dir: Path) -> None:
    prepare_validation_session_readonly(
        workdir=workdir,
        datasource_dir=datasource_dir,
    )


@pytest.mark.parametrize("prepare_readonly", [_prepare_generation, _prepare_validation])
def test_prepare_session_readonly_replaces_existing_readonly_file(
    tmp_path: Path,
    prepare_readonly: ReadonlyPreparer,
) -> None:
    """観点：readonly準備。確認：readonlyファイルを実ディレクトリへ置換する。"""
    datasource_dir = tmp_path / "datasource"
    datasource_dir.mkdir()
    (datasource_dir / "guide.md").write_text("案内", encoding="utf-8")
    workdir = tmp_path / "session"
    workdir.mkdir()
    (workdir / "readonly").write_text("古い内容", encoding="utf-8")

    prepare_readonly(workdir, datasource_dir)

    readonly_dir = workdir / "readonly"
    assert readonly_dir.is_dir()
    assert (readonly_dir / "guide.md").read_text(encoding="utf-8") == "案内"


@pytest.mark.parametrize("prepare_readonly", [_prepare_generation, _prepare_validation])
def test_prepare_session_readonly_replaces_existing_child_directory(
    tmp_path: Path,
    prepare_readonly: ReadonlyPreparer,
) -> None:
    """観点：readonly準備。確認：既存子ディレクトリを同名データで置換する。"""
    datasource_dir = tmp_path / "datasource"
    datasource_dir.mkdir()
    (datasource_dir / "guide.md").write_text("案内", encoding="utf-8")
    workdir = tmp_path / "session"
    existing_child_dir = workdir / "readonly" / "guide.md"
    existing_child_dir.mkdir(parents=True)
    (existing_child_dir / "stale.txt").write_text("古い内容", encoding="utf-8")

    prepare_readonly(workdir, datasource_dir)

    readonly_file = workdir / "readonly" / "guide.md"
    assert readonly_file.is_file()
    assert readonly_file.read_text(encoding="utf-8") == "案内"


@pytest.mark.parametrize("prepare_readonly", [_prepare_generation, _prepare_validation])
def test_prepare_session_readonly_copies_when_symlink_fails(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    prepare_readonly: ReadonlyPreparer,
) -> None:
    """観点：readonly準備。確認：symlink不可環境ではコピーする。"""
    datasource_dir = tmp_path / "datasource"
    datasource_dir.mkdir()
    (datasource_dir / "guide.md").write_text("案内", encoding="utf-8")
    source_dir = datasource_dir / "manuals"
    source_dir.mkdir()
    (source_dir / "page.md").write_text("本文", encoding="utf-8")

    def raise_os_error(
        self: Path,
        target: str,
        target_is_directory: bool = False,
    ) -> None:
        raise OSError("symlink disabled")

    monkeypatch.setattr(Path, "symlink_to", raise_os_error)

    workdir = tmp_path / "session"
    prepare_readonly(workdir, datasource_dir)

    readonly_dir = workdir / "readonly"
    assert (readonly_dir / "guide.md").is_file()
    assert not (readonly_dir / "guide.md").is_symlink()
    assert (readonly_dir / "guide.md").read_text(encoding="utf-8") == "案内"
    assert (readonly_dir / "manuals").is_dir()
    assert not (readonly_dir / "manuals").is_symlink()
    assert (readonly_dir / "manuals" / "page.md").read_text(encoding="utf-8") == "本文"


def test_prepare_validation_session_artifacts_links_generation_artifacts(
    tmp_path: Path,
) -> None:
    """観点：検証用Codex作業領域。確認：生成成果物を検証用artifactsへsymlinkする。"""
    generation_workdir = tmp_path / "generation"
    generation_artifacts = generation_workdir / "artifacts"
    generation_artifacts.mkdir(parents=True)
    (generation_artifacts / "chart.svg").write_text("<svg />", encoding="utf-8")
    validation_workdir = tmp_path / "validation"

    prepare_validation_session_artifacts(
        validation_workdir=validation_workdir,
        generation_workdir=generation_workdir,
        has_artifact_links=True,
    )

    validation_artifacts = validation_workdir / "artifacts"
    assert validation_artifacts.is_symlink()
    assert (validation_artifacts / "chart.svg").read_text(encoding="utf-8") == "<svg />"


def test_prepare_validation_session_artifacts_does_not_create_without_links(
    tmp_path: Path,
) -> None:
    """観点：検証用Codex作業領域。確認：成果物リンクがなければartifactsを作成しない。"""
    validation_workdir = tmp_path / "validation"

    prepare_validation_session_artifacts(
        validation_workdir=validation_workdir,
        generation_workdir=tmp_path / "generation",
        has_artifact_links=False,
    )

    assert not (validation_workdir / "artifacts").exists()


def test_prepare_validation_session_artifacts_raises_when_symlink_fails(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """観点：検証用Codex作業領域。確認：artifactsのsymlink失敗はコピーせずシステムエラーにする。"""
    generation_artifacts = tmp_path / "generation" / "artifacts"
    generation_artifacts.mkdir(parents=True)

    def raise_os_error(
        self: Path,
        target: str,
        target_is_directory: bool = False,
    ) -> None:
        _ = (self, target, target_is_directory)
        raise OSError("symlink disabled")

    monkeypatch.setattr(Path, "symlink_to", raise_os_error)

    with pytest.raises(ValidationWorkspacePreparationError):
        prepare_validation_session_artifacts(
            validation_workdir=tmp_path / "validation",
            generation_workdir=tmp_path / "generation",
            has_artifact_links=True,
        )

    assert not (tmp_path / "validation" / "artifacts").exists()

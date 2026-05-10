from pathlib import Path
from uuid import UUID

import pytest

from backend.infrastructure.filesystem.artifacts.file_artifact_store import (
    FileArtifactStore,
    OpenedArtifactFile,
    SavedArtifactFile,
)
from backend.shared.errors import AppError, ErrorClass


def test_file_artifact_store_copies_candidate_into_saved_area(
    tmp_path: Path,
) -> None:
    """観点：成果物ファイルIF。確認：セッション内成果物を保存済み領域へコピーする。"""
    session_workdir = tmp_path / "sessions" / "user" / "session"
    (session_workdir / "artifacts").mkdir(parents=True)
    candidate = session_workdir / "artifacts" / "chart.svg"
    candidate.write_text("<svg></svg>", encoding="utf-8")
    saved_root = tmp_path / "saved_artifacts"
    run_id = UUID("00000000-0000-0000-0000-000000000601")
    artifact_id = UUID("00000000-0000-0000-0000-000000000611")
    store = FileArtifactStore(saved_artifacts_dir=saved_root)

    saved = store.save_adopted_file(
        session_workdir=session_workdir,
        candidate_relative_path="artifacts/chart.svg",
        run_id=run_id,
        artifact_id=artifact_id,
    )

    assert saved == SavedArtifactFile(
        artifact_id=artifact_id,
        mime_type="image/svg+xml",
        relative_path=f"{run_id}/{artifact_id}.svg",
    )
    assert (saved_root / saved.relative_path).read_text(encoding="utf-8") == (
        "<svg></svg>"
    )


@pytest.mark.parametrize(
    ("candidate_name", "expected_mime_type"),
    [
        ("photo.jpg", "image/jpeg"),
        ("photo.jpeg", "image/jpeg"),
    ],
)
def test_file_artifact_store_allows_jpeg_images(
    tmp_path: Path,
    candidate_name: str,
    expected_mime_type: str,
) -> None:
    """観点：成果物ファイルIF。確認：jpg/jpeg画像を保存対象にできる。"""
    session_workdir = tmp_path / "sessions" / "user" / "session"
    (session_workdir / "artifacts").mkdir(parents=True)
    (session_workdir / "artifacts" / candidate_name).write_bytes(b"jpeg")
    run_id = UUID("00000000-0000-0000-0000-000000000606")
    artifact_id = UUID("00000000-0000-0000-0000-000000000616")
    store = FileArtifactStore(saved_artifacts_dir=tmp_path / "saved_artifacts")

    saved = store.save_adopted_file(
        session_workdir=session_workdir,
        candidate_relative_path=f"artifacts/{candidate_name}",
        run_id=run_id,
        artifact_id=artifact_id,
    )

    assert saved.mime_type == expected_mime_type


def test_file_artifact_store_opens_saved_file(tmp_path: Path) -> None:
    """観点：成果物配信。確認：保存済み領域内のメタ情報だけを配信用に開く。"""
    saved_root = tmp_path / "saved_artifacts"
    saved_file = saved_root / "run-id" / "artifact-id.html"
    saved_file.parent.mkdir(parents=True)
    saved_file.write_text("<main>ok</main>", encoding="utf-8")
    store = FileArtifactStore(saved_artifacts_dir=saved_root)

    opened = store.open_saved_file(
        relative_path="run-id/artifact-id.html",
        mime_type="text/html",
    )

    assert opened == OpenedArtifactFile(path=saved_file, mime_type="text/html")


@pytest.mark.parametrize(
    "candidate_relative_path",
    [
        "../chart.png",
        "/tmp/chart.png",
        "readonly/chart.png",
        "artifacts/../readonly/chart.png",
        "artifacts/chart.txt",
    ],
)
def test_file_artifact_store_rejects_invalid_candidate_path(
    tmp_path: Path,
    candidate_relative_path: str,
) -> None:
    """観点：成果物ファイルIF。確認：許可外パスと許可外拡張子を拒否する。"""
    session_workdir = tmp_path / "sessions" / "user" / "session"
    (session_workdir / "artifacts").mkdir(parents=True)
    store = FileArtifactStore(saved_artifacts_dir=tmp_path / "saved_artifacts")

    with pytest.raises(AppError) as error_info:
        store.save_adopted_file(
            session_workdir=session_workdir,
            candidate_relative_path=candidate_relative_path,
            run_id=UUID("00000000-0000-0000-0000-000000000602"),
            artifact_id=UUID("00000000-0000-0000-0000-000000000612"),
        )

    assert error_info.value.error_class is ErrorClass.FORBIDDEN


def test_file_artifact_store_rejects_missing_candidate(tmp_path: Path) -> None:
    """観点：成果物ファイルIF。確認：候補ファイルなしを回答採用失敗にする。"""
    session_workdir = tmp_path / "sessions" / "user" / "session"
    (session_workdir / "artifacts").mkdir(parents=True)
    store = FileArtifactStore(saved_artifacts_dir=tmp_path / "saved_artifacts")

    with pytest.raises(AppError) as error_info:
        store.save_adopted_file(
            session_workdir=session_workdir,
            candidate_relative_path="artifacts/missing.png",
            run_id=UUID("00000000-0000-0000-0000-000000000603"),
            artifact_id=UUID("00000000-0000-0000-0000-000000000613"),
        )

    assert error_info.value.error_class is ErrorClass.NOT_FOUND


def test_file_artifact_store_rejects_existing_saved_artifact(tmp_path: Path) -> None:
    """観点：成果物ファイルIF。確認：保存先衝突を競合として拒否する。"""
    session_workdir = tmp_path / "sessions" / "user" / "session"
    (session_workdir / "artifacts").mkdir(parents=True)
    (session_workdir / "artifacts" / "chart.png").write_bytes(b"png")
    saved_root = tmp_path / "saved_artifacts"
    run_id = UUID("00000000-0000-0000-0000-000000000605")
    artifact_id = UUID("00000000-0000-0000-0000-000000000615")
    existing = saved_root / str(run_id) / f"{artifact_id}.png"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"existing")
    store = FileArtifactStore(saved_artifacts_dir=saved_root)

    with pytest.raises(AppError) as error_info:
        store.save_adopted_file(
            session_workdir=session_workdir,
            candidate_relative_path="artifacts/chart.png",
            run_id=run_id,
            artifact_id=artifact_id,
        )

    assert error_info.value.error_class is ErrorClass.CONFLICT


def test_file_artifact_store_rejects_symlink_to_outside_candidate(
    tmp_path: Path,
) -> None:
    """観点：成果物ファイルIF。確認：シンボリックリンク解決後の外部参照を拒否する。"""
    session_workdir = tmp_path / "sessions" / "user" / "session"
    artifacts_dir = session_workdir / "artifacts"
    artifacts_dir.mkdir(parents=True)
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"png")
    (artifacts_dir / "outside.png").symlink_to(outside)
    store = FileArtifactStore(saved_artifacts_dir=tmp_path / "saved_artifacts")

    with pytest.raises(AppError) as error_info:
        store.save_adopted_file(
            session_workdir=session_workdir,
            candidate_relative_path="artifacts/outside.png",
            run_id=UUID("00000000-0000-0000-0000-000000000604"),
            artifact_id=UUID("00000000-0000-0000-0000-000000000614"),
        )

    assert error_info.value.error_class is ErrorClass.FORBIDDEN


@pytest.mark.parametrize(
    ("relative_path", "mime_type", "expected_error_class"),
    [
        ("../run/artifact.html", "text/html", ErrorClass.FORBIDDEN),
        ("run/artifact.exe", "application/octet-stream", ErrorClass.FORBIDDEN),
        ("run/deep/artifact.html", "text/html", ErrorClass.FORBIDDEN),
        ("run/artifact.html", "image/png", ErrorClass.FORBIDDEN),
        ("run/missing.png", "image/png", ErrorClass.NOT_FOUND),
        ("run/\x00artifact.png", "image/png", ErrorClass.FORBIDDEN),
        ("C:/run/artifact.png", "image/png", ErrorClass.FORBIDDEN),
    ],
)
def test_file_artifact_store_rejects_invalid_saved_metadata(
    tmp_path: Path,
    relative_path: str,
    mime_type: str,
    expected_error_class: ErrorClass,
) -> None:
    """観点：成果物配信。確認：不正な保存済みメタ情報を拒否する。"""
    store = FileArtifactStore(saved_artifacts_dir=tmp_path / "saved_artifacts")
    saved_html = tmp_path / "saved_artifacts" / "run" / "artifact.html"
    saved_html.parent.mkdir(parents=True)
    saved_html.write_text("<main>ok</main>", encoding="utf-8")

    with pytest.raises(AppError) as error_info:
        store.open_saved_file(
            relative_path=relative_path,
            mime_type=mime_type,
        )

    assert error_info.value.error_class is expected_error_class


def test_file_artifact_store_rejects_saved_symlink_to_outside(
    tmp_path: Path,
) -> None:
    """観点：成果物配信。確認：保存済み領域内シンボリックリンクの外部参照を拒否する。"""
    saved_root = tmp_path / "saved_artifacts"
    outside = tmp_path / "outside"
    outside.mkdir()
    saved_root.mkdir()
    (saved_root / "run").symlink_to(outside)
    store = FileArtifactStore(saved_artifacts_dir=saved_root)

    with pytest.raises(AppError) as error_info:
        store.open_saved_file(
            relative_path="run/artifact.png",
            mime_type="image/png",
        )

    assert error_info.value.error_class is ErrorClass.FORBIDDEN

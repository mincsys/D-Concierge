from pathlib import Path
from uuid import UUID

import pytest

from backend.application.ports.filesystem.dto import (
    OpenedArtifactFile,
    SavedArtifactFile,
)
from backend.infrastructure.filesystem.file_artifact_store import (
    FileArtifactStore,
)
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.tests.support.symlink import require_symlink_support


def test_file_artifact_store_copies_candidate_into_saved_area(
    tmp_path: Path,
) -> None:
    """観点：成果物ファイルIF。確認：セッション内成果物を保存済み領域へコピーする。"""
    session_workdir = tmp_path / "sessions" / "user" / "session"
    (session_workdir / "artifacts").mkdir(parents=True)
    candidate = session_workdir / "artifacts" / "chart.svg"
    candidate.write_text("<svg></svg>", encoding="utf-8")
    saved_root = tmp_path / "saved_artifacts"
    artifact_id = UUID("00000000-0000-0000-0000-000000000611")
    store = FileArtifactStore(saved_artifacts_dir=saved_root)

    saved = store.save_adopted_file(
        session_workdir=session_workdir,
        candidate_relative_path="artifacts/chart.svg",
        artifact_id=artifact_id,
    )

    assert saved == SavedArtifactFile(
        artifact_id=artifact_id,
        mime_type="image/svg+xml",
        relative_path=f"user/session/{artifact_id}.svg",
    )
    assert (saved_root / saved.relative_path).read_text(encoding="utf-8") == (
        "<svg></svg>"
    )


def test_file_artifact_store_saves_multiple_files_under_same_session_dir(
    tmp_path: Path,
) -> None:
    """観点：成果物ファイルIF。確認：同一セッションの成果物を同じセッションディレクトリへ保存する。"""
    session_workdir = tmp_path / "sessions" / "user" / "session"
    (session_workdir / "artifacts").mkdir(parents=True)
    (session_workdir / "artifacts" / "first.svg").write_text(
        "<svg>first</svg>", encoding="utf-8"
    )
    (session_workdir / "artifacts" / "second.svg").write_text(
        "<svg>second</svg>", encoding="utf-8"
    )
    saved_root = tmp_path / "saved_artifacts"
    first_artifact_id = UUID("00000000-0000-0000-0000-000000000621")
    second_artifact_id = UUID("00000000-0000-0000-0000-000000000622")
    store = FileArtifactStore(saved_artifacts_dir=saved_root)

    first = store.save_adopted_file(
        session_workdir=session_workdir,
        candidate_relative_path="artifacts/first.svg",
        artifact_id=first_artifact_id,
    )
    second = store.save_adopted_file(
        session_workdir=session_workdir,
        candidate_relative_path="artifacts/second.svg",
        artifact_id=second_artifact_id,
    )

    assert first.relative_path == f"user/session/{first_artifact_id}.svg"
    assert second.relative_path == f"user/session/{second_artifact_id}.svg"
    assert (saved_root / "user" / "session").is_dir()


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
    artifact_id = UUID("00000000-0000-0000-0000-000000000616")
    store = FileArtifactStore(saved_artifacts_dir=tmp_path / "saved_artifacts")

    saved = store.save_adopted_file(
        session_workdir=session_workdir,
        candidate_relative_path=f"artifacts/{candidate_name}",
        artifact_id=artifact_id,
    )

    assert saved.mime_type == expected_mime_type


def test_file_artifact_store_opens_saved_file(tmp_path: Path) -> None:
    """観点：成果物配信。確認：保存済み領域内のメタ情報だけを配信用に開く。"""
    saved_root = tmp_path / "saved_artifacts"
    saved_file = saved_root / "demo-user" / "session-id" / "artifact-id.html"
    saved_file.parent.mkdir(parents=True)
    saved_file.write_text("<main>ok</main>", encoding="utf-8")
    store = FileArtifactStore(saved_artifacts_dir=saved_root)

    opened = store.open_saved_file(
        relative_path="demo-user/session-id/artifact-id.html",
        mime_type="text/html",
    )

    assert opened == OpenedArtifactFile(path=saved_file, mime_type="text/html")


@pytest.mark.parametrize(
    "candidate_relative_path",
    [
        "../chart.png",
        "/tmp/chart.png",
        "data_source/chart.png",
        "artifacts/../data_source/chart.png",
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
            artifact_id=UUID("00000000-0000-0000-0000-000000000612"),
        )

    assert error_info.value.error_type is ErrorType.FORBIDDEN


def test_file_artifact_store_rejects_missing_candidate(tmp_path: Path) -> None:
    """観点：成果物ファイルIF。確認：候補ファイルなしを回答採用失敗にする。"""
    session_workdir = tmp_path / "sessions" / "user" / "session"
    (session_workdir / "artifacts").mkdir(parents=True)
    store = FileArtifactStore(saved_artifacts_dir=tmp_path / "saved_artifacts")

    with pytest.raises(AppError) as error_info:
        store.save_adopted_file(
            session_workdir=session_workdir,
            candidate_relative_path="artifacts/missing.png",
            artifact_id=UUID("00000000-0000-0000-0000-000000000613"),
        )

    assert error_info.value.error_type is ErrorType.NOT_FOUND


def test_file_artifact_store_rejects_existing_saved_artifact(tmp_path: Path) -> None:
    """観点：成果物ファイルIF。確認：保存先衝突を競合として拒否する。"""
    session_workdir = tmp_path / "sessions" / "user" / "session"
    (session_workdir / "artifacts").mkdir(parents=True)
    (session_workdir / "artifacts" / "chart.png").write_bytes(b"png")
    saved_root = tmp_path / "saved_artifacts"
    artifact_id = UUID("00000000-0000-0000-0000-000000000615")
    existing = saved_root / "user" / "session" / f"{artifact_id}.png"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"existing")
    store = FileArtifactStore(saved_artifacts_dir=saved_root)

    with pytest.raises(AppError) as error_info:
        store.save_adopted_file(
            session_workdir=session_workdir,
            candidate_relative_path="artifacts/chart.png",
            artifact_id=artifact_id,
        )

    assert error_info.value.error_type is ErrorType.CONFLICT


def test_file_artifact_store_rejects_symlink_to_outside_candidate(
    tmp_path: Path,
) -> None:
    """観点：成果物ファイルIF。確認：シンボリックリンク解決後の外部参照を拒否する。"""
    require_symlink_support(tmp_path, target_is_directory=False)
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
            artifact_id=UUID("00000000-0000-0000-0000-000000000614"),
        )

    assert error_info.value.error_type is ErrorType.FORBIDDEN


@pytest.mark.parametrize(
    ("relative_path", "mime_type", "expected_error_type"),
    [
        ("../session/artifact.html", "text/html", ErrorType.FORBIDDEN),
        ("session/artifact.exe", "application/octet-stream", ErrorType.FORBIDDEN),
        ("session/artifact.html", "text/html", ErrorType.FORBIDDEN),
        ("session/deep/too-deep/artifact.html", "text/html", ErrorType.FORBIDDEN),
        ("session/artifact.html", "image/png", ErrorType.FORBIDDEN),
        ("user/session/missing.png", "image/png", ErrorType.NOT_FOUND),
        ("session/\x00artifact.png", "image/png", ErrorType.FORBIDDEN),
        ("C:/session/artifact.png", "image/png", ErrorType.FORBIDDEN),
    ],
)
def test_file_artifact_store_rejects_invalid_saved_metadata(
    tmp_path: Path,
    relative_path: str,
    mime_type: str,
    expected_error_type: ErrorType,
) -> None:
    """観点：成果物配信。確認：不正な保存済みメタ情報を拒否する。"""
    store = FileArtifactStore(saved_artifacts_dir=tmp_path / "saved_artifacts")
    saved_html = tmp_path / "saved_artifacts" / "user" / "session" / "artifact.html"
    saved_html.parent.mkdir(parents=True)
    saved_html.write_text("<main>ok</main>", encoding="utf-8")

    with pytest.raises(AppError) as error_info:
        store.open_saved_file(
            relative_path=relative_path,
            mime_type=mime_type,
        )

    assert error_info.value.error_type is expected_error_type


def test_file_artifact_store_rejects_saved_symlink_to_outside(
    tmp_path: Path,
) -> None:
    """観点：成果物配信。確認：保存済み領域内シンボリックリンクの外部参照を拒否する。"""
    require_symlink_support(tmp_path, target_is_directory=True)
    saved_root = tmp_path / "saved_artifacts"
    outside = tmp_path / "outside"
    outside.mkdir()
    (saved_root / "user").mkdir(parents=True)
    (saved_root / "user" / "session").symlink_to(outside)
    store = FileArtifactStore(saved_artifacts_dir=saved_root)

    with pytest.raises(AppError) as error_info:
        store.open_saved_file(
            relative_path="user/session/artifact.png",
            mime_type="image/png",
        )

    assert error_info.value.error_type is ErrorType.FORBIDDEN


def test_file_artifact_store_deletes_saved_artifacts_and_empty_session_dir(
    tmp_path: Path,
) -> None:
    """観点：成果物ファイルIF。

    確認：保存済み成果物実体と空の親セッションディレクトリだけを削除する。
    """
    saved_root = tmp_path / "saved_artifacts"
    target = saved_root / "demo-user" / "session-target" / "chart.svg"
    other = saved_root / "other-user" / "session-other" / "other.svg"
    target.parent.mkdir(parents=True)
    other.parent.mkdir(parents=True)
    target.write_text("<svg />", encoding="utf-8")
    other.write_text("<svg />", encoding="utf-8")
    store = FileArtifactStore(saved_artifacts_dir=saved_root)

    store.delete_saved_artifacts(("demo-user/session-target/chart.svg",))

    assert target.exists() is False
    assert target.parent.exists() is False
    assert other.read_text(encoding="utf-8") == "<svg />"

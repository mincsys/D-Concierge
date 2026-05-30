from pathlib import Path
from uuid import UUID

from backend.infrastructure.codex.session_workdir_cleanup import (
    CodexSessionWorkdirCleanup,
)
from backend.tests.support.symlink import require_symlink_support


def test_session_workdir_cleanup_removes_generation_and_validation_session_dirs(
    tmp_path: Path,
) -> None:
    """観点：Codex実行IF。

    確認：生成用・検証用セッション作業領域を削除し、data_sourceリンク先実体は保持する。
    """
    require_symlink_support(tmp_path, target_is_directory=True)
    user_id = "demo-user"
    session_id = UUID("00000000-0000-0000-0000-000000000902")
    generation_root = tmp_path / "generator"
    validation_root = tmp_path / "validator"
    data_source = tmp_path / "data_source"
    data_source.mkdir()
    (data_source / "manual.pdf").write_text("pdf", encoding="utf-8")
    generation_session = generation_root / user_id / str(session_id)
    validation_session = validation_root / user_id / str(session_id)
    generation_session.mkdir(parents=True)
    validation_session.mkdir(parents=True)
    (generation_session / "data_source").symlink_to(
        data_source, target_is_directory=True
    )
    (validation_session / "work.txt").write_text("work", encoding="utf-8")
    cleanup = CodexSessionWorkdirCleanup(
        generation_workdir=generation_root,
        validation_workdir=validation_root,
    )

    cleanup.delete_session_workdirs(user_id, session_id)

    assert generation_session.exists() is False
    assert validation_session.exists() is False
    assert (data_source / "manual.pdf").read_text(encoding="utf-8") == "pdf"

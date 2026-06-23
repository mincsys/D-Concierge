from __future__ import annotations

from pathlib import Path

import pytest

from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.tests.support.chat import F003_USER_ID, SESSION_ID_VALUE
from backend.tests.support.codex import (
    ARTIFACT_SOURCE_PATH,
    SAVED_ARTIFACT_URL,
    FakeAdoptedArtifactStore,
)


def test_save_adopted_artifacts_replaces_markdown_links_and_returns_metadata(
    tmp_path: Path,
) -> None:
    """
    観点：採用済み成果物保存ユースケースが回答本文内の成果物リンクを保存済みURLへ置換すること
    確認：画像リンクと通常リンクを保存境界へ渡し、markdownは/api/artifacts/{artifact_id}へ
    置換され、成果物メタ情報が回答ブロックに紐づくこと
    """
    from backend.application.artifacts.save_adopted_artifacts import (
        SaveAdoptedArtifactsCommand,
        SaveAdoptedArtifactsUseCase,
    )

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    (artifacts_dir / "diagram.svg").write_text("<svg />", encoding="utf-8")
    (artifacts_dir / "report.html").write_text("<!doctype html>", encoding="utf-8")
    store = FakeAdoptedArtifactStore()
    use_case = SaveAdoptedArtifactsUseCase(artifact_store=store)

    result = use_case.execute(
        SaveAdoptedArtifactsCommand(
            user_id=F003_USER_ID,
            session_id=SESSION_ID_VALUE,
            artifacts_dir=artifacts_dir,
            markdown_blocks=(
                f"![図]({ARTIFACT_SOURCE_PATH}) と [詳細](./{ARTIFACT_SOURCE_PATH})"
                ' と <a href="artifacts/report.html">HTML</a>',
            ),
        ),
    )

    assert len(store.saved) == 3
    assert store.saved[0].relative_path == ARTIFACT_SOURCE_PATH
    assert store.saved[1].relative_path == ARTIFACT_SOURCE_PATH
    assert store.saved[2].relative_path == "artifacts/report.html"
    assert result.blocks[0].markdown == (
        f"![図]({SAVED_ARTIFACT_URL}) と [詳細]({SAVED_ARTIFACT_URL})"
        f' と <a href="{SAVED_ARTIFACT_URL}">HTML</a>'
    )
    assert len(result.blocks[0].artifacts) == 3
    assert result.blocks[0].artifacts[0].mime_type == "image/svg+xml"
    assert result.blocks[0].artifacts[0].storage_path.endswith(".svg")


@pytest.mark.parametrize(
    "markdown",
    (
        "![図](../secret.svg)",
        "![図](/absolute/secret.svg)",
        "![図](https://example.test/secret.svg)",
        "![図](artifacts/script.exe)",
    ),
)
def test_save_adopted_artifacts_rejects_unsafe_or_disallowed_paths(
    tmp_path: Path,
    markdown: str,
) -> None:
    """
    観点：採用済み成果物保存ユースケースが候補成果物パスの安全性を検証すること
    確認：親ディレクトリ、絶対パス、URL、許可外拡張子はSYSTEMかつtrace対象の
    AppErrorとなり、保存境界を呼び出さないこと
    """
    from backend.application.artifacts.save_adopted_artifacts import (
        SaveAdoptedArtifactsCommand,
        SaveAdoptedArtifactsUseCase,
    )

    store = FakeAdoptedArtifactStore()
    use_case = SaveAdoptedArtifactsUseCase(artifact_store=store)

    with pytest.raises(AppError) as raised:
        use_case.execute(
            SaveAdoptedArtifactsCommand(
                user_id=F003_USER_ID,
                session_id=SESSION_ID_VALUE,
                artifacts_dir=tmp_path,
                markdown_blocks=(markdown,),
            ),
        )

    assert raised.value.error_type is ErrorType.SYSTEM
    assert raised.value.trace is True
    assert store.saved == []


def test_save_adopted_artifacts_rejects_missing_candidate_file(tmp_path: Path) -> None:
    """
    観点：採用済み成果物保存ユースケースが存在しない候補ファイルを採用しないこと
    確認：Markdown内の成果物リンクに対応する生成用ファイルがない場合は
    SYSTEMかつtrace対象のAppErrorとなり、保存済みURLへ置換しないこと
    """
    from backend.application.artifacts.save_adopted_artifacts import (
        SaveAdoptedArtifactsCommand,
        SaveAdoptedArtifactsUseCase,
    )

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    store = FakeAdoptedArtifactStore()
    use_case = SaveAdoptedArtifactsUseCase(artifact_store=store)

    with pytest.raises(AppError) as raised:
        use_case.execute(
            SaveAdoptedArtifactsCommand(
                user_id=F003_USER_ID,
                session_id=SESSION_ID_VALUE,
                artifacts_dir=artifacts_dir,
                markdown_blocks=(f"![図]({ARTIFACT_SOURCE_PATH})",),
            ),
        )

    assert raised.value.error_type is ErrorType.SYSTEM
    assert raised.value.trace is True
    assert "diagram.svg" in raised.value.diagnostic_message
    assert store.saved == []

from pathlib import Path

from backend.application.artifacts.get_artifact import GetArtifactUseCase
from backend.application.references.get_reference_data import GetReferenceDataUseCase
from backend.infrastructure.filesystem.artifacts.file_artifact_store import (
    FileArtifactStore,
)
from backend.infrastructure.filesystem.references.file_reference_store import (
    FileReferenceStore,
)
from backend.tests.support.memory_repository import InMemoryChatRepository


def test_get_reference_data_use_case_opens_pdf(tmp_path: Path) -> None:
    """観点：参照元PDF取得UseCase。確認：参照元メタ情報からPDFファイルを開く。"""
    datasource_dir = tmp_path / "datasource"
    datasource_dir.mkdir()
    pdf_path = datasource_dir / "manual.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    repository = InMemoryChatRepository()
    reference_id = repository.save_completed_answer_for_test(
        markdown="回答",
        reference_relative_path="manual.pdf",
        artifact_relative_path="run/artifact.svg",
        artifact_mime_type="image/svg+xml",
    )
    usecase = GetReferenceDataUseCase(
        repository=repository,
        reference_store=FileReferenceStore(datasource_dir),
    )

    opened = usecase.execute(reference_id)

    assert opened.path == pdf_path
    assert opened.mime_type == "application/pdf"


def test_get_artifact_use_case_allows_jpeg(tmp_path: Path) -> None:
    """観点：Codex成果物配信UseCase。確認：jpg/jpeg成果物をimage/jpegとして開く。"""
    saved_root = tmp_path / "saved_artifacts"
    saved_file = saved_root / "demo-user" / "run-id" / "artifact-id.jpg"
    saved_file.parent.mkdir(parents=True)
    saved_file.write_bytes(b"jpeg")
    repository = InMemoryChatRepository()
    repository.save_completed_answer_for_test(
        markdown="回答",
        reference_relative_path="manual.pdf",
        artifact_relative_path="demo-user/run-id/artifact-id.jpg",
        artifact_mime_type="image/jpeg",
    )
    artifact_id = repository.latest_artifact_id_for_test()
    usecase = GetArtifactUseCase(
        repository=repository,
        artifact_store=FileArtifactStore(saved_root),
    )

    opened = usecase.execute(artifact_id)

    assert opened.path == saved_file
    assert opened.mime_type == "image/jpeg"


def test_get_artifact_use_case_opens_saved_artifact(tmp_path: Path) -> None:
    """観点：Codex成果物配信UseCase。確認：保存済み成果物メタ情報からファイルを開く。"""
    saved_root = tmp_path / "saved_artifacts"
    repository = InMemoryChatRepository()
    repository.save_completed_answer_for_test(
        markdown="回答",
        reference_relative_path="manual.pdf",
        artifact_relative_path="demo-user/run-id/artifact.html",
        artifact_mime_type="text/html",
    )
    saved_file = saved_root / "demo-user" / "run-id" / "artifact.html"
    saved_file.parent.mkdir(parents=True)
    saved_file.write_text("<main>ok</main>", encoding="utf-8")
    usecase = GetArtifactUseCase(
        repository=repository,
        artifact_store=FileArtifactStore(saved_root),
    )

    opened = usecase.execute(repository.latest_artifact_id_for_test())

    assert opened.path == saved_file
    assert opened.mime_type == "text/html"

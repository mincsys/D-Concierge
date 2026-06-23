from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import NotRequired, TypedDict
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import MetaData, Table, create_engine
from sqlalchemy.engine import Engine

from backend.domain.chat.chat_state import ChatState
from backend.domain.execution.run_state import RunState
from backend.tests.support.chat import (
    CHAT_ID_VALUE,
    OTHER_USER_ID,
    RUN_ID_VALUE,
    SESSION_ID_VALUE,
    insert_chat_run,
    seed_chat_user,
)
from backend.tests.support.foundation import (
    LOGIN_SESSION_COOKIE_NAME,
    create_foundation_config,
    foundation_test_database_url,
    prepare_foundation_database,
)

ANSWER_BLOCK_ID_VALUE = UUID("66666666-6666-7666-8666-666666666666")
REFERENCE_ID_VALUE = UUID("77777777-7777-7777-8777-777777777777")
ARTIFACT_ID_VALUE = UUID("88888888-8888-7888-8888-888888888888")
INSTRUCTION_ID_VALUE = UUID("99999999-9999-7999-8999-999999999999")
PDF_BYTES = b"%PDF-1.4\n% f006 reference\n%%EOF\n"
SVG_BYTES = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'
HTML_BYTES = b"<!doctype html><title>artifact</title>"
CSV_BYTES = b"label,value\nartifact,1\n"


class ErrorPayload(TypedDict):
    error: str
    message: str
    field_errors: NotRequired[dict[str, str]]


class PdfLocatorDbPayload(TypedDict):
    path: str
    page_start: int
    page_end: int


@pytest.mark.asyncio
async def test_reference_pdf_api_returns_pdf_for_saved_owner_reference(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-09 参照元データ取得APIがREST、認証、DB、共有データソースを結合すること
    確認：認証ユーザの保存済みPDF参照元だけをapplication/pdfで返し、
    レスポンス本文に内部パスを含めないこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    _seed_completed_delivery_chat(
        database_url,
        user_id=seeded.user_id,
        reference_path="manual/a.pdf",
        artifact_storage_path=f"{seeded.user_id}/{SESSION_ID_VALUE}/{ARTIFACT_ID_VALUE}.svg",
    )
    pdf_path = files.data_source_dir / "manual" / "a.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(PDF_BYTES)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.get(f"/api/references/{REFERENCE_ID_VALUE}")

    assert response.status_code == 200
    assert _content_type(response) == "application/pdf"
    assert response.content == PDF_BYTES
    assert str(pdf_path) not in response.text


@pytest.mark.asyncio
async def test_reference_pdf_api_rejects_traversal_locator_without_file_body(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-09 参照元データ取得APIが保存済みlocatorの許可範囲を検証すること
    確認：DB上の参照元pathが親ディレクトリ参照の場合は403共通エラーとなり、
    共有データソース外ファイルの内容や内部パスを返さないこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    _seed_completed_delivery_chat(
        database_url,
        user_id=seeded.user_id,
        reference_path="../secret.pdf",
        artifact_storage_path=f"{seeded.user_id}/{SESSION_ID_VALUE}/{ARTIFACT_ID_VALUE}.svg",
    )
    secret_path = tmp_path / "secret.pdf"
    secret_path.write_bytes(PDF_BYTES)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.get(f"/api/references/{REFERENCE_ID_VALUE}")

    assert response.status_code == 403
    payload = _error_payload(response)
    assert payload["error"] == "forbidden"
    assert PDF_BYTES not in response.content
    assert str(secret_path) not in response.text


@pytest.mark.asyncio
async def test_delivery_apis_reject_other_user_resources_without_file_body(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-08/09 が認証ユーザ所有外の参照元と成果物を配信しないこと
    確認：別ユーザに紐づくIDは404共通エラーとなり、PDFと成果物本文を返さないこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    seed_chat_user(
        database_url,
        user_id=OTHER_USER_ID,
        user_name="別ユーザ",
        session_token="f006-other-session-token",
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    storage_path = f"{OTHER_USER_ID}/{SESSION_ID_VALUE}/{ARTIFACT_ID_VALUE}.svg"
    _seed_completed_delivery_chat(
        database_url,
        user_id=OTHER_USER_ID,
        reference_path="manual/other.pdf",
        artifact_storage_path=storage_path,
    )
    pdf_path = files.data_source_dir / "manual" / "other.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(PDF_BYTES)
    saved_file = files.saved_artifacts_dir / storage_path
    saved_file.parent.mkdir(parents=True)
    saved_file.write_bytes(SVG_BYTES)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        reference_response = await client.get(f"/api/references/{REFERENCE_ID_VALUE}")
        artifact_response = await client.get(f"/api/artifacts/{ARTIFACT_ID_VALUE}")

    _assert_error_without_body(reference_response, 404, "not_found", PDF_BYTES)
    _assert_error_without_body(artifact_response, 404, "not_found", SVG_BYTES)
    assert str(pdf_path) not in reference_response.text
    assert storage_path not in artifact_response.text


@pytest.mark.asyncio
async def test_delivery_apis_reject_deleting_chat_resources_without_file_body(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    観点：IF-SB-08/09 が削除中チャットに紐づく参照元と成果物を配信しないこと
    確認：deletingチャットのIDは409共通エラーとなり、PDFと成果物本文を返さないこと
    """
    from backend.app.factory import create_app
    from backend.infrastructure.runtime.chat_deletion_dispatcher import (
        DatabaseChatDeletionExecutor,
    )

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    storage_path = f"{seeded.user_id}/{SESSION_ID_VALUE}/{ARTIFACT_ID_VALUE}.svg"
    _seed_completed_delivery_chat(
        database_url,
        user_id=seeded.user_id,
        reference_path="manual/deleting.pdf",
        artifact_storage_path=storage_path,
        chat_state=ChatState.DELETING.value,
    )
    pdf_path = files.data_source_dir / "manual" / "deleting.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(PDF_BYTES)
    saved_file = files.saved_artifacts_dir / storage_path
    saved_file.parent.mkdir(parents=True)
    saved_file.write_bytes(SVG_BYTES)

    def execute_noop(
        self: DatabaseChatDeletionExecutor,
        chat_id: UUID,
        trace_id: str,
    ) -> None:
        return

    monkeypatch.setattr(DatabaseChatDeletionExecutor, "execute", execute_noop)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        reference_response = await client.get(f"/api/references/{REFERENCE_ID_VALUE}")
        artifact_response = await client.get(f"/api/artifacts/{ARTIFACT_ID_VALUE}")

    _assert_error_without_body(reference_response, 409, "conflict", PDF_BYTES)
    _assert_error_without_body(artifact_response, 409, "conflict", SVG_BYTES)
    assert str(pdf_path) not in reference_response.text
    assert storage_path not in artifact_response.text


@pytest.mark.asyncio
async def test_delivery_apis_return_not_found_when_saved_files_are_missing(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-08/09 がDBメタ存在時の配信元ファイル欠損を扱うこと
    確認：実PDFと保存済み成果物がない場合は404共通エラーとなり、内部パスを返さないこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    storage_path = f"{seeded.user_id}/{SESSION_ID_VALUE}/{ARTIFACT_ID_VALUE}.svg"
    _seed_completed_delivery_chat(
        database_url,
        user_id=seeded.user_id,
        reference_path="manual/missing.pdf",
        artifact_storage_path=storage_path,
    )
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        reference_response = await client.get(f"/api/references/{REFERENCE_ID_VALUE}")
        artifact_response = await client.get(f"/api/artifacts/{ARTIFACT_ID_VALUE}")

    _assert_error_without_body(reference_response, 404, "not_found", PDF_BYTES)
    _assert_error_without_body(artifact_response, 404, "not_found", SVG_BYTES)
    assert str(files.data_source_dir) not in reference_response.text
    assert str(files.saved_artifacts_dir) not in artifact_response.text
    assert storage_path not in artifact_response.text
    trace_logs = tuple(files.trace_log_dir.rglob("*.yaml"))
    assert len(trace_logs) == 1
    trace_log_text = trace_logs[0].read_text(encoding="utf-8")
    assert "api_failed" in trace_log_text
    assert artifact_response.headers["x-trace-id"] in trace_log_text
    assert "not_found" in trace_log_text
    assert f"/api/artifacts/{ARTIFACT_ID_VALUE}" in trace_log_text
    assert "保存済み成果物ファイルが見つかりません。" in trace_log_text


@pytest.mark.asyncio
async def test_artifact_api_returns_saved_file_with_persisted_mime_type(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-08 Codex成果物取得APIがREST、認証、DB、保存済み成果物領域を結合すること
    確認：採用済み成果物だけをDB保存MIMEタイプで返し、Codex作業領域内パスを返さないこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    storage_path = f"{seeded.user_id}/{SESSION_ID_VALUE}/{ARTIFACT_ID_VALUE}.svg"
    _seed_completed_delivery_chat(
        database_url,
        user_id=seeded.user_id,
        reference_path="manual/a.pdf",
        artifact_storage_path=storage_path,
        artifact_mime_type="image/svg+xml",
    )
    saved_file = files.saved_artifacts_dir / storage_path
    saved_file.parent.mkdir(parents=True)
    saved_file.write_bytes(SVG_BYTES)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.get(f"/api/artifacts/{ARTIFACT_ID_VALUE}")

    assert response.status_code == 200
    assert _content_type(response) == "image/svg+xml"
    assert response.content == SVG_BYTES
    assert "codex/sessions" not in response.text


@pytest.mark.parametrize(
    ("extension", "mime_type", "body"),
    [
        ("html", "text/html", HTML_BYTES),
        ("csv", "text/csv", CSV_BYTES),
    ],
)
@pytest.mark.asyncio
async def test_artifact_api_returns_allowed_text_artifacts_with_saved_mime_type(
    tmp_path: Path,
    extension: str,
    mime_type: str,
    body: bytes,
) -> None:
    """
    観点：IF-SB-08 が非画像の許可MIMEタイプ成果物を保存済みMIMEで配信すること
    確認：text/htmlとtext/csvの保存済み成果物をContent-Typeを保って返すこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    storage_path = (
        f"{seeded.user_id}/{SESSION_ID_VALUE}/{ARTIFACT_ID_VALUE}.{extension}"
    )
    _seed_completed_delivery_chat(
        database_url,
        user_id=seeded.user_id,
        reference_path="manual/a.pdf",
        artifact_storage_path=storage_path,
        artifact_mime_type=mime_type,
    )
    saved_file = files.saved_artifacts_dir / storage_path
    saved_file.parent.mkdir(parents=True)
    saved_file.write_bytes(body)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.get(f"/api/artifacts/{ARTIFACT_ID_VALUE}")

    assert response.status_code == 200
    assert _content_type(response) == mime_type
    assert response.content == body
    assert storage_path not in response.text


@pytest.mark.asyncio
async def test_artifact_api_rejects_disallowed_mime_without_file_body(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-08 Codex成果物取得APIが保存済みMIMEタイプの許可範囲を検証すること
    確認：許可外MIMEタイプの成果物は403共通エラーとなり、
    保存済みファイルの内容を返さないこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    storage_path = f"{seeded.user_id}/{SESSION_ID_VALUE}/{ARTIFACT_ID_VALUE}.bin"
    _seed_completed_delivery_chat(
        database_url,
        user_id=seeded.user_id,
        reference_path="manual/a.pdf",
        artifact_storage_path=storage_path,
        artifact_mime_type="application/octet-stream",
    )
    saved_file = files.saved_artifacts_dir / storage_path
    saved_file.parent.mkdir(parents=True)
    saved_file.write_bytes(b"unsafe artifact")
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.get(f"/api/artifacts/{ARTIFACT_ID_VALUE}")

    assert response.status_code == 403
    payload = _error_payload(response)
    assert payload["error"] == "forbidden"
    assert b"unsafe artifact" not in response.content


@pytest.mark.asyncio
async def test_artifact_api_rejects_mime_extension_mismatch_without_file_body(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-08 が保存済み成果物のMIMEタイプと拡張子の対応を検証すること
    確認：storage_pathが.svgで保存MIMEがtext/htmlの場合は403共通エラーとなり、
    保存済みファイルの内容を返さないこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    storage_path = f"{seeded.user_id}/{SESSION_ID_VALUE}/{ARTIFACT_ID_VALUE}.svg"
    _seed_completed_delivery_chat(
        database_url,
        user_id=seeded.user_id,
        reference_path="manual/a.pdf",
        artifact_storage_path=storage_path,
        artifact_mime_type="text/html",
    )
    saved_file = files.saved_artifacts_dir / storage_path
    saved_file.parent.mkdir(parents=True)
    saved_file.write_bytes(SVG_BYTES)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.get(f"/api/artifacts/{ARTIFACT_ID_VALUE}")

    assert response.status_code == 403
    payload = _error_payload(response)
    assert payload["error"] == "forbidden"
    assert SVG_BYTES not in response.content


@pytest.mark.asyncio
async def test_delivery_apis_reject_missing_cookie_without_file_body(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-08/09 が保護対象APIとして未ログインアクセスを拒否すること
    確認：Cookieなしでは401共通エラーとなり、保存済みPDFと成果物本文を返さないこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    storage_path = f"{seeded.user_id}/{SESSION_ID_VALUE}/{ARTIFACT_ID_VALUE}.svg"
    _seed_completed_delivery_chat(
        database_url,
        user_id=seeded.user_id,
        reference_path="manual/a.pdf",
        artifact_storage_path=storage_path,
    )
    pdf_path = files.data_source_dir / "manual" / "a.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(PDF_BYTES)
    saved_file = files.saved_artifacts_dir / storage_path
    saved_file.parent.mkdir(parents=True)
    saved_file.write_bytes(SVG_BYTES)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        reference_response = await client.get(f"/api/references/{REFERENCE_ID_VALUE}")
        artifact_response = await client.get(f"/api/artifacts/{ARTIFACT_ID_VALUE}")

    _assert_unauthorized_without_body(reference_response, PDF_BYTES)
    _assert_unauthorized_without_body(artifact_response, SVG_BYTES)


def _seed_completed_delivery_chat(
    database_url: str,
    *,
    user_id: str,
    reference_path: str,
    artifact_storage_path: str,
    artifact_mime_type: str = "image/svg+xml",
    chat_id: UUID = CHAT_ID_VALUE,
    run_id: UUID = RUN_ID_VALUE,
    session_id: UUID = SESSION_ID_VALUE,
    instruction_id: UUID = INSTRUCTION_ID_VALUE,
    answer_block_id: UUID = ANSWER_BLOCK_ID_VALUE,
    reference_id: UUID = REFERENCE_ID_VALUE,
    artifact_id: UUID = ARTIFACT_ID_VALUE,
    chat_state: str = ChatState.ACTIVE.value,
) -> None:
    insert_chat_run(
        database_url,
        user_id=user_id,
        chat_id=chat_id,
        run_id=run_id,
        session_id=session_id,
        instruction_id=instruction_id,
        title="F006配信チャット",
        instruction="参照元と成果物を表示してください。",
        run_state=RunState.COMPLETED.value,
        chat_state=chat_state,
    )
    engine = create_engine(database_url)
    try:
        _insert_answer_block_reference_and_artifact(
            engine,
            run_id=run_id,
            answer_block_id=answer_block_id,
            reference_id=reference_id,
            artifact_id=artifact_id,
            reference_path=reference_path,
            artifact_storage_path=artifact_storage_path,
            artifact_mime_type=artifact_mime_type,
        )
    finally:
        engine.dispose()


def _insert_answer_block_reference_and_artifact(
    engine: Engine,
    *,
    run_id: UUID,
    answer_block_id: UUID,
    reference_id: UUID,
    artifact_id: UUID,
    reference_path: str,
    artifact_storage_path: str,
    artifact_mime_type: str,
) -> None:
    answer_blocks = _metadata_table(engine, "answer_blocks")
    references = _metadata_table(engine, "references")
    artifacts = _metadata_table(engine, "artifacts")
    locator: PdfLocatorDbPayload = {
        "path": reference_path,
        "page_start": 2,
        "page_end": 3,
    }
    with engine.begin() as connection:
        connection.execute(
            answer_blocks.insert().values(
                id=answer_block_id,
                run_id=run_id,
                position=1,
                markdown=f"回答本文 ![図](/api/artifacts/{artifact_id})",
            ),
        )
        connection.execute(
            references.insert().values(
                id=reference_id,
                answer_block_id=answer_block_id,
                position=1,
                source_type="pdf",
                label="資料A",
                locator=locator,
            ),
        )
        connection.execute(
            artifacts.insert().values(
                id=artifact_id,
                answer_block_id=answer_block_id,
                mime_type=artifact_mime_type,
                storage_path=artifact_storage_path,
                created_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
            ),
        )


def _metadata_table(engine: Engine, table_name: str) -> Table:
    metadata = MetaData()
    metadata.reflect(bind=engine, only=(table_name,))
    return metadata.tables[table_name]


def _content_type(response: Response) -> str:
    return response.headers["content-type"].split(";")[0]


def _error_payload(response: Response) -> ErrorPayload:
    payload = json.loads(response.text)
    assert isinstance(payload, dict)
    assert isinstance(payload.get("error"), str)
    assert isinstance(payload.get("message"), str)
    return ErrorPayload(error=payload["error"], message=payload["message"])


def _assert_unauthorized_without_body(
    response: Response,
    forbidden_body: bytes,
) -> None:
    assert response.status_code == 401
    payload = _error_payload(response)
    assert payload["error"] == "unauthorized"
    assert forbidden_body not in response.content


def _assert_error_without_body(
    response: Response,
    status_code: int,
    error: str,
    forbidden_body: bytes,
) -> None:
    assert response.status_code == status_code
    payload = _error_payload(response)
    assert payload["error"] == error
    assert forbidden_body not in response.content

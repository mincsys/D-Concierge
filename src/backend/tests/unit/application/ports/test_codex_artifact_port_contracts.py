from __future__ import annotations

from pathlib import Path

from backend.tests.support.chat import (
    CHAT_ID_VALUE,
    F003_USER_ID,
    RUN_ID_VALUE,
    SESSION_ID_VALUE,
)


def test_codex_generation_port_contract_keeps_session_and_conversation_ids() -> None:
    """
    観点：Codex生成Port DTOがD-Conciergeのsession_idとCodex会話継続IDを分離すること
    確認：生成要求はrun/chat/session、resume_conversation_id、remaining_seconds、
    再生成指示を明示し、結果はthread_idとprogress/finalを分けて返すこと
    """
    from backend.application.ports.codex.dto import (
        CodexGenerationRequest,
        CodexGenerationResult,
    )

    request = CodexGenerationRequest(
        chat_id=CHAT_ID_VALUE,
        run_id=RUN_ID_VALUE,
        user_id=F003_USER_ID,
        session_id=SESSION_ID_VALUE,
        user_instruction="ポンプの点検方法を教えてください。",
        resume_conversation_id="gen-thread-previous",
        regeneration_instruction="不合格理由：根拠が不足しています。",
        remaining_seconds=300,
    )
    result = CodexGenerationResult(
        conversation_id="gen-thread-001",
        progress_messages=("調査しています。",),
        final_answer_json='{"payload":{"kind":"final","answers":[]}}',
        artifacts_dir=Path("codex/sessions/user-001/session/artifacts"),
    )

    assert request.session_id == SESSION_ID_VALUE
    assert request.resume_conversation_id == "gen-thread-previous"
    assert request.remaining_seconds == 300
    assert request.regeneration_instruction is not None
    assert "根拠" in request.regeneration_instruction
    assert result.conversation_id == "gen-thread-001"
    assert result.progress_messages == ("調査しています。",)
    assert result.final_answer_json.startswith('{"payload"')


def test_validator_and_reference_port_contracts_keep_fixed_validation_results() -> None:
    """
    観点：回答検証で使うPort DTOが固定検証とCodex検証の結果を分離すること
    確認：PDF参照元検証は正規化済みpath/page_start/page_endを返し、
    検証用Codex結果はprogressとfinal検証JSONを分けて返すこと
    """
    from backend.application.ports.codex.dto import (
        ReferenceValidationResult,
        ValidatorCodexRequest,
        ValidatorCodexResult,
    )

    reference = ReferenceValidationResult(
        path="manuals/pump.pdf",
        page_start=2,
        page_end=3,
        exists=True,
        readable=True,
        page_count=8,
    )
    request = ValidatorCodexRequest(
        chat_id=CHAT_ID_VALUE,
        run_id=RUN_ID_VALUE,
        user_id=F003_USER_ID,
        session_id=SESSION_ID_VALUE,
        candidate_json='{"payload":{"kind":"final","answers":[]}}',
        resume_conversation_id=None,
        artifacts_readonly_dir=Path("codex/sessions/user-001/session/artifacts"),
        remaining_seconds=240,
    )
    result = ValidatorCodexResult(
        conversation_id="val-thread-001",
        progress_messages=("回答候補を検証しています。",),
        final_result_json='{"payload":{"kind":"final","valid":true,"comment":""}}',
    )

    assert reference.path == "manuals/pump.pdf"
    assert reference.page_start == 2
    assert reference.page_end == 3
    assert request.artifacts_readonly_dir is not None
    assert request.remaining_seconds == 240
    assert result.final_result_json.endswith("}}")


def test_adopted_artifact_port_contract_uses_saved_storage_boundary() -> None:
    """
    観点：採用済み成果物Port DTOが一時成果物と公開保存先を分離すること
    確認：保存要求はセッション内相対パスだけを渡し、結果はartifact_id、
    storage_path、公開URL、MIMEタイプを返すこと
    """
    from backend.application.ports.filesystem.dto import (
        AdoptedArtifactSaveRequest,
        AdoptedArtifactSaveResult,
    )

    request = AdoptedArtifactSaveRequest(
        user_id=F003_USER_ID,
        session_id=SESSION_ID_VALUE,
        artifacts_dir=Path("codex/sessions/user-001/session/artifacts"),
        relative_path="artifacts/diagram.svg",
    )
    result = AdoptedArtifactSaveResult(
        artifact_id="aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa",
        storage_path=f"{F003_USER_ID}/{SESSION_ID_VALUE}/aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa.svg",
        public_url="/api/artifacts/aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa",
        mime_type="image/svg+xml",
    )

    assert request.relative_path == "artifacts/diagram.svg"
    assert request.artifacts_dir.name == "artifacts"
    assert result.public_url.startswith("/api/artifacts/")
    assert result.storage_path.startswith(f"{F003_USER_ID}/{SESSION_ID_VALUE}/")
    assert result.mime_type == "image/svg+xml"


def test_session_workdir_cleanup_port_exposes_f007_chat_and_account_methods() -> None:
    """
    観点：Codex作業領域削除Portがチャット物理削除とアカウント物理削除の
    ファイル境界を表すこと
    確認：session_id単位とuser_id単位の作業領域削除メソッドが
    Protocolに定義されること
    """
    from backend.application.ports.codex.interface import SessionWorkdirCleanupPort

    assert hasattr(SessionWorkdirCleanupPort, "delete_session_workdirs")
    assert hasattr(SessionWorkdirCleanupPort, "delete_user_workdirs")

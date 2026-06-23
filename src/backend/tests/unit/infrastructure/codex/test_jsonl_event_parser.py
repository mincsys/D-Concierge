from __future__ import annotations

import json

import pytest

from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.tests.support.codex import valid_candidate_json, validator_result_json


def test_jsonl_parser_extracts_thread_id_progress_and_final_candidate() -> None:
    """
    観点：JsonlEventParserがCodex JSONLの公開イベントを型付き結果へ変換すること
    確認：thread.startedの会話ID、progress本文、final候補JSONを抽出し、
    finalを中間メッセージとして扱わないこと
    """
    from backend.infrastructure.codex.jsonl_event_parser import (
        JsonlEventParser,
        JsonlEventType,
    )

    parser = JsonlEventParser()
    started = parser.parse_line(
        json.dumps(
            {
                "type": "thread.started",
                "thread_id": "thread-001",
            },
        ),
    )
    progress = parser.parse_line(
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": json.dumps(
                        {"payload": {"kind": "progress", "text": "調査中です。"}},
                        ensure_ascii=False,
                    ),
                },
            },
        ),
    )
    final_candidate = valid_candidate_json()
    final = parser.parse_line(
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": final_candidate,
                },
            },
        ),
    )

    assert started.event_type is JsonlEventType.THREAD_STARTED
    assert started.thread_id == "thread-001"
    assert progress.event_type is JsonlEventType.AGENT_MESSAGE
    assert progress.progress_text == "調査中です。"
    assert progress.final_payload_json is None
    assert final.event_type is JsonlEventType.AGENT_MESSAGE
    assert final.progress_text is None
    assert final.final_payload_json == final_candidate


def test_jsonl_parser_extracts_turn_failed_error_and_unknown_event() -> None:
    """
    観点：JsonlEventParserが異常終了と未知イベントを上位で判断可能にすること
    確認：turn.failedとerrorの診断メッセージを保持し、未知イベントは内部イベントとして
    final候補や中間メッセージへ変換しないこと
    """
    from backend.infrastructure.codex.jsonl_event_parser import (
        JsonlEventParser,
        JsonlEventType,
    )

    parser = JsonlEventParser()
    failed = parser.parse_line(
        json.dumps(
            {
                "type": "turn.failed",
                "error": {"message": "モデル呼び出しに失敗しました。"},
            },
            ensure_ascii=False,
        ),
    )
    error = parser.parse_line(
        json.dumps(
            {
                "type": "error",
                "message": "JSONLストリームが終了しました。",
            },
            ensure_ascii=False,
        ),
    )
    unknown = parser.parse_line(
        json.dumps(
            {
                "type": "experimental.event",
                "value": "ignored",
            },
        ),
    )

    assert failed.event_type is JsonlEventType.TURN_FAILED
    assert failed.error_message == "モデル呼び出しに失敗しました。"
    assert error.event_type is JsonlEventType.ERROR
    assert error.error_message == "JSONLストリームが終了しました。"
    assert unknown.event_type is JsonlEventType.INTERNAL
    assert unknown.progress_text is None
    assert unknown.final_payload_json is None


def test_jsonl_parser_distinguishes_turn_completed_from_payload_events() -> None:
    """
    観点：JsonlEventParserがturn.completedを最終候補の確定契機として扱うこと
    確認：turn.completedは専用イベント種別として返り、progress本文やfinal payloadへ
    誤変換されず、上位が候補確定タイミングを識別できること
    """
    from backend.infrastructure.codex.jsonl_event_parser import (
        JsonlEventParser,
        JsonlEventType,
    )

    parser = JsonlEventParser()
    completed = parser.parse_line(json.dumps({"type": "turn.completed"}))

    assert completed.event_type is JsonlEventType.TURN_COMPLETED
    assert completed.progress_text is None
    assert completed.final_payload_json is None
    assert completed.error_message is None


def test_jsonl_parser_keeps_turn_and_item_started_as_internal_events() -> None:
    """
    観点：JsonlEventParserが開始系イベントを回答候補として採用しないこと
    確認：turn.startedとitem.startedは内部イベントとして返り、中間メッセージ、
    final payload、エラー診断へ変換されないこと
    """
    from backend.infrastructure.codex.jsonl_event_parser import (
        JsonlEventParser,
        JsonlEventType,
    )

    parser = JsonlEventParser()
    turn_started = parser.parse_line(json.dumps({"type": "turn.started"}))
    item_started = parser.parse_line(
        json.dumps(
            {
                "type": "item.started",
                "item": {"type": "agent_message"},
            },
        ),
    )

    assert turn_started.event_type is JsonlEventType.INTERNAL
    assert item_started.event_type is JsonlEventType.INTERNAL
    assert turn_started.progress_text is None
    assert item_started.final_payload_json is None


def test_jsonl_parser_rejects_invalid_json_and_validator_final_shape() -> None:
    """
    観点：JsonlEventParserが解析不能行と検証用final payloadを区別して扱うこと
    確認：壊れたJSONLはtrace対象のSYSTEM AppErrorとなり、検証用finalは
    final_payload_jsonとして保持されること
    """
    from backend.infrastructure.codex.jsonl_event_parser import JsonlEventParser

    parser = JsonlEventParser()
    validation_final = parser.parse_line(
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": validator_result_json(valid=True),
                },
            },
        ),
    )

    assert validation_final.progress_text is None
    assert validation_final.final_payload_json == validator_result_json(valid=True)
    with pytest.raises(AppError) as raised:
        parser.parse_line("{not-json")

    assert raised.value.error_type is ErrorType.SYSTEM
    assert raised.value.trace is True
    assert "JSONL" in raised.value.diagnostic_message


def test_jsonl_parser_rejects_non_object_line_and_missing_type() -> None:
    """
    観点：JsonlEventParserがJSONとして読めてもイベント形でない行を拒否すること
    確認：トップレベル配列とtype欠落はtrace対象のSYSTEM AppErrorとなり、
    中間メッセージやfinal候補へ変換しないこと
    """
    from backend.infrastructure.codex.jsonl_event_parser import JsonlEventParser

    parser = JsonlEventParser()

    with pytest.raises(AppError) as non_object:
        parser.parse_line("[]")
    with pytest.raises(AppError) as missing_type:
        parser.parse_line(json.dumps({"thread_id": "thread-001"}))

    assert non_object.value.error_type is ErrorType.SYSTEM
    assert non_object.value.trace is True
    assert missing_type.value.error_type is ErrorType.SYSTEM
    assert "type" in missing_type.value.diagnostic_message


@pytest.mark.parametrize(
    "line",
    (
        json.dumps({"type": "item.completed"}),
        json.dumps({"type": "item.completed", "item": {"type": "tool_call"}}),
        json.dumps(
            {"type": "item.completed", "item": {"type": "agent_message"}},
        ),
        json.dumps(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "[]"},
            },
        ),
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": json.dumps({"message": "payloadなし"}),
                },
            },
            ensure_ascii=False,
        ),
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": json.dumps({"payload": {"kind": "debug"}}),
                },
            },
        ),
    ),
)
def test_jsonl_parser_keeps_non_answer_item_completed_as_internal(
    line: str,
) -> None:
    """
    観点：JsonlEventParserが回答候補ではないitem.completedを内部イベントへ退避すること
    確認：item欠落、agent_message以外、text欠落、payload欠落、未知kindを
    progressやfinal payloadへ誤変換しないこと
    """
    from backend.infrastructure.codex.jsonl_event_parser import (
        JsonlEventParser,
        JsonlEventType,
    )

    event = JsonlEventParser().parse_line(line)

    assert event.event_type is JsonlEventType.INTERNAL
    assert event.progress_text is None
    assert event.final_payload_json is None


def test_jsonl_parser_uses_fallback_error_messages_for_failed_events() -> None:
    """
    観点：JsonlEventParserがCodex異常終了の診断を複数形式から抽出すること
    確認：turn.failedのトップレベルmessageとmessage欠落errorを扱い、
    上位が失敗イベントとして識別できること
    """
    from backend.infrastructure.codex.jsonl_event_parser import (
        JsonlEventParser,
        JsonlEventType,
    )

    parser = JsonlEventParser()
    failed = parser.parse_line(
        json.dumps(
            {"type": "turn.failed", "message": "実行が中断されました。"},
            ensure_ascii=False,
        ),
    )
    error_without_message = parser.parse_line(json.dumps({"type": "error"}))

    assert failed.event_type is JsonlEventType.TURN_FAILED
    assert failed.error_message == "実行が中断されました。"
    assert error_without_message.event_type is JsonlEventType.ERROR
    assert error_without_message.error_message == ""

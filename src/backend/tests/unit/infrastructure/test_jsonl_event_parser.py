import pytest

from backend.infrastructure.codex.codex_event_kind import CodexEventKind
from backend.infrastructure.codex.jsonl_event_parser import (
    JsonlEventParser,
    JsonlParseError,
)


def test_jsonl_event_parser_extracts_thread_started_id() -> None:
    """観点：JSONL解析。

    確認：thread.startedからCodex側resume用IDを構造化イベントへ変換する。
    """
    event = JsonlEventParser.parse_line(
        '{"type":"thread.started","thread_id":"codex-thread-1"}'
    )

    assert event.kind is CodexEventKind.THREAD_STARTED
    assert event.event_type == "thread.started"
    assert event.thread_id == "codex-thread-1"


def test_jsonl_event_parser_keeps_agent_message_as_pending_candidate() -> None:
    """観点：JSONL解析。

    確認：item.completedのagent_messageを中間/最終未分類の本文として返す。
    """
    event = JsonlEventParser.parse_line(
        '{"type":"item.completed","item":{"type":"agent_message","text":"回答候補"}}'
    )

    assert event.kind is CodexEventKind.AGENT_MESSAGE
    assert event.text == "回答候補"


def test_jsonl_event_parser_keeps_unknown_completed_item_internal() -> None:
    """観点：JSONL解析。

    確認：未知のitem.completedを内部イベントとして保持し、回答候補にしない。
    """
    event = JsonlEventParser.parse_line(
        '{"type":"item.completed","item":{"type":"file_change","path":"a.txt"}}'
    )

    assert event.kind is CodexEventKind.UNKNOWN
    assert event.text is None


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ('{"type":"turn.started"}', CodexEventKind.TURN_STARTED),
        (
            '{"type":"item.started","item":{"type":"agent_message"}}',
            CodexEventKind.ITEM_STARTED,
        ),
        ('{"type":"turn.completed"}', CodexEventKind.TURN_COMPLETED),
        ('{"type":"turn.failed","message":"失敗"}', CodexEventKind.TURN_FAILED),
        ('{"type":"error","message":"異常"}', CodexEventKind.ERROR),
        ('{"type":"custom.event","value":1}', CodexEventKind.UNKNOWN),
    ],
)
def test_jsonl_event_parser_distinguishes_known_and_unknown_events(
    line: str,
    kind: CodexEventKind,
) -> None:
    """観点：JSONL解析。

    確認：既知イベントと未知イベントを、利用側が判定可能な種別へ変換する。
    """
    event = JsonlEventParser.parse_line(line)

    assert event.kind is kind


@pytest.mark.parametrize(
    "line",
    [
        "{",
        "[]",
        '{"type":1}',
        '{"type":"thread.started"}',
        '{"type":"thread.started","thread":{"id":""}}',
        '{"event":"thread.started","thread":{"thread_id":"nested-thread"}}',
        '{"type":"item.completed","item":1}',
        '{"type":"item.completed","item":{"type":"agent_message"}}',
        '{"type":"item.completed","item":{"item_type":"agent_message","text":"候補"}}',
        '{"type":"item.completed","item":{"value":1}}',
        '{"type":"error","message":1}',
    ],
)
def test_jsonl_event_parser_rejects_invalid_line(line: str) -> None:
    """観点：JSONL解析異常系。

    確認：JSON構文やイベント必須項目が不正な行を解析失敗として扱う。
    """
    with pytest.raises(JsonlParseError):
        JsonlEventParser.parse_line(line)


def test_jsonl_event_parser_accepts_failed_event_without_message() -> None:
    """観点：JSONL解析。

    確認：messageのないturn.failedを失敗終端イベントとして扱う。
    """
    event = JsonlEventParser.parse_line('{"type":"turn.failed"}')

    assert event.kind is CodexEventKind.TURN_FAILED
    assert event.message is None

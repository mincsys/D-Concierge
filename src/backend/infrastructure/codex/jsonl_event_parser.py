import json
from dataclasses import dataclass

from backend.infrastructure.codex.codex_event_kind import CodexEventKind

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class JsonlParseError(Exception):
    """Codex JSONLイベント解析失敗。"""


@dataclass(frozen=True, slots=True)
class ParsedCodexEvent:
    """Codex JSONLの構造化イベント。"""

    kind: CodexEventKind
    event_type: str
    thread_id: str | None = None
    text: str | None = None
    message: str | None = None


class JsonlEventParser:
    """codex execのJSONL 1行を構造化イベントへ変換する。"""

    @staticmethod
    def parse_line(line: str) -> ParsedCodexEvent:
        """JSONL 1行を解析し、利用側が判定可能なイベント種別へ変換する。"""
        try:
            loaded: JsonValue = json.loads(line)
        except json.JSONDecodeError as exc:
            raise JsonlParseError("JSONL行を解析できません。") from exc

        if not isinstance(loaded, dict):
            raise JsonlParseError("JSONLイベントの形式が不正です。")

        event_type = _event_type(loaded)
        match event_type:
            case "thread.started":
                return ParsedCodexEvent(
                    kind=CodexEventKind.THREAD_STARTED,
                    event_type=event_type,
                    thread_id=_thread_id(loaded),
                )
            case "turn.started":
                return ParsedCodexEvent(
                    kind=CodexEventKind.TURN_STARTED,
                    event_type=event_type,
                )
            case "item.started":
                return ParsedCodexEvent(
                    kind=CodexEventKind.ITEM_STARTED,
                    event_type=event_type,
                )
            case "item.completed":
                return _parse_completed_item(event_type, loaded)
            case "turn.completed":
                return ParsedCodexEvent(
                    kind=CodexEventKind.TURN_COMPLETED,
                    event_type=event_type,
                )
            case "turn.failed":
                return ParsedCodexEvent(
                    kind=CodexEventKind.TURN_FAILED,
                    event_type=event_type,
                    message=_optional_string(loaded, "message"),
                )
            case "error":
                return ParsedCodexEvent(
                    kind=CodexEventKind.ERROR,
                    event_type=event_type,
                    message=_optional_string(loaded, "message"),
                )
            case _:
                return ParsedCodexEvent(
                    kind=CodexEventKind.UNKNOWN,
                    event_type=event_type,
                )


def _parse_completed_item(
    event_type: str, event_data: dict[str, JsonValue]
) -> ParsedCodexEvent:
    item = event_data.get("item")
    if not isinstance(item, dict):
        raise JsonlParseError("JSONL item.completedのitem形式が不正です。")

    item_type = _item_type(item)
    match item_type:
        case "agent_message":
            return ParsedCodexEvent(
                kind=CodexEventKind.AGENT_MESSAGE,
                event_type=event_type,
                text=_required_string(item, "text"),
            )
        case _:
            return ParsedCodexEvent(kind=CodexEventKind.UNKNOWN, event_type=event_type)


def _event_type(event_data: dict[str, JsonValue]) -> str:
    value = event_data.get("type")
    if not isinstance(value, str) or value.strip() == "":
        raise JsonlParseError("JSONLイベント種別が不正です。")
    return value


def _item_type(item: dict[str, JsonValue]) -> str:
    value = item.get("type")
    if not isinstance(value, str) or value.strip() == "":
        raise JsonlParseError("JSONL item種別が不正です。")
    return value


def _thread_id(event_data: dict[str, JsonValue]) -> str:
    value = event_data.get("thread_id")
    if isinstance(value, str) and value.strip() != "":
        return value
    raise JsonlParseError("thread.startedのthread_idが不正です。")


def _required_string(data: dict[str, JsonValue], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or value.strip() == "":
        raise JsonlParseError(f"JSONL項目 {key} が不正です。")
    return value


def _optional_string(data: dict[str, JsonValue], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise JsonlParseError(f"JSONL項目 {key} が不正です。")
    return value

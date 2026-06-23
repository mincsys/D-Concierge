from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum

from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError

type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)


class JsonlEventType(StrEnum):
    """Codex JSONLの内部イベント種別。"""

    THREAD_STARTED = "thread_started"
    AGENT_MESSAGE = "agent_message"
    TURN_COMPLETED = "turn_completed"
    TURN_FAILED = "turn_failed"
    ERROR = "error"
    INTERNAL = "internal"


@dataclass(frozen=True, slots=True)
class JsonlEvent:
    """Codex JSONL 1行を構造化したイベント。"""

    event_type: JsonlEventType
    thread_id: str | None = None
    progress_text: str | None = None
    final_payload_json: str | None = None
    error_message: str | None = None


class JsonlEventParser:
    """Codex JSONL stdoutを上位処理用イベントへ変換する。"""

    def parse_line(self, line: str) -> JsonlEvent:
        value = _load_json(line)
        if not isinstance(value, dict):
            raise _jsonl_error("Codex JSONLの形式が不正です。")
        event_type = _str_field(value, "type")
        if event_type == "thread.started":
            return JsonlEvent(
                event_type=JsonlEventType.THREAD_STARTED,
                thread_id=_optional_str_field(value, "thread_id"),
            )
        if event_type == "item.completed":
            return _agent_message_event(_dict_field(value, "item"))
        if event_type == "turn.completed":
            return JsonlEvent(event_type=JsonlEventType.TURN_COMPLETED)
        if event_type == "turn.failed":
            return JsonlEvent(
                event_type=JsonlEventType.TURN_FAILED,
                error_message=_turn_failed_message(value),
            )
        if event_type == "error":
            return JsonlEvent(
                event_type=JsonlEventType.ERROR,
                error_message=_optional_str_field(value, "message") or "",
            )
        return JsonlEvent(event_type=JsonlEventType.INTERNAL)


def _agent_message_event(item: dict[str, JsonValue] | None) -> JsonlEvent:
    if item is None or _optional_str_field(item, "type") != "agent_message":
        return JsonlEvent(event_type=JsonlEventType.INTERNAL)
    text = _optional_str_field(item, "text")
    if text is None:
        return JsonlEvent(event_type=JsonlEventType.INTERNAL)
    value = _load_json(text)
    if not isinstance(value, dict):
        return JsonlEvent(event_type=JsonlEventType.INTERNAL)
    payload = _dict_field(value, "payload")
    if payload is None:
        return JsonlEvent(event_type=JsonlEventType.INTERNAL)
    kind = _optional_str_field(payload, "kind")
    if kind == "progress":
        return JsonlEvent(
            event_type=JsonlEventType.AGENT_MESSAGE,
            progress_text=_optional_str_field(payload, "text") or "",
        )
    if kind == "final":
        return JsonlEvent(
            event_type=JsonlEventType.AGENT_MESSAGE,
            final_payload_json=text,
        )
    return JsonlEvent(event_type=JsonlEventType.INTERNAL)


def _turn_failed_message(value: dict[str, JsonValue]) -> str:
    error = _dict_field(value, "error")
    if error is not None:
        return _optional_str_field(error, "message") or ""
    return _optional_str_field(value, "message") or ""


def _load_json(text: str) -> JsonValue:
    try:
        value: JsonValue = json.loads(text)
    except json.JSONDecodeError as error:
        raise _jsonl_error("Codex JSONLの解析に失敗しました。", error) from error
    return value


def _str_field(value: dict[str, JsonValue], key: str) -> str:
    field_value = value.get(key)
    if not isinstance(field_value, str):
        raise _jsonl_error(f"Codex JSONLの{key}が不正です。")
    return field_value


def _optional_str_field(value: dict[str, JsonValue], key: str) -> str | None:
    field_value = value.get(key)
    if isinstance(field_value, str):
        return field_value
    return None


def _dict_field(
    value: dict[str, JsonValue],
    key: str,
) -> dict[str, JsonValue] | None:
    field_value = value.get(key)
    if isinstance(field_value, dict):
        return field_value
    return None


def _jsonl_error(message: str, cause: BaseException | None = None) -> AppError:
    return AppError(
        error_type=ErrorType.SYSTEM,
        trace=True,
        diagnostic_message=message,
        cause=cause,
    )

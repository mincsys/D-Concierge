import json
from collections.abc import Callable

from backend.infrastructure.codex.jsonl_event_parser import JsonValue, ParsedCodexEvent


class CodexIntermediateMessageStreamer:
    """JSONLイベントから逐次配信可能な中間メッセージ本文を抽出する。"""

    def __init__(
        self,
        emit: Callable[[str], None] | None,
    ) -> None:
        self._emit = emit

    def accept(self, event: ParsedCodexEvent) -> None:
        """agent_message.textを中間メッセージ候補として通知する。"""
        if self._emit is None or event.kind != "agent_message" or event.text is None:
            return
        for extracted_message in _progress_messages(event.text):
            self._emit(extracted_message)


def _progress_messages(message: str) -> tuple[str, ...]:
    loaded = _load_json_object(message)
    if loaded is None:
        return ()
    payload = loaded.get("payload")
    if not isinstance(payload, dict):
        return ()
    if payload.get("kind") != "progress":
        return ()
    text = payload.get("text")
    if not isinstance(text, str) or text.strip() == "":
        return ()
    return (text.strip(),)


def _load_json_object(message: str) -> dict[str, JsonValue] | None:
    try:
        loaded: JsonValue = json.loads(message)
    except json.JSONDecodeError:
        return None
    if not isinstance(loaded, dict):
        return None
    return loaded

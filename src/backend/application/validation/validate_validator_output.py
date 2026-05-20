"""検証用Codexの最終出力を固定検証する。"""

import json
from dataclasses import dataclass

from backend.domain.answer.output_kind import CodexOutputKind
from backend.shared.errors.errors import ValidationResultFormatError

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True, slots=True)
class ParsedValidatorOutput:
    """固定検証済みの検証用Codex最終出力。"""

    valid: bool
    comment: str


def parse_validator_final_output(raw_json: str) -> ParsedValidatorOutput:
    """検証用Codexの最終出力JSONを検証し、型付き結果へ変換する。"""
    try:
        loaded: JsonValue = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValidationResultFormatError("検証結果を解析できませんでした。") from exc
    if not isinstance(loaded, dict):
        raise ValidationResultFormatError("検証結果の形式が不正です。")

    payload = loaded.get("payload")
    if not isinstance(payload, dict):
        raise ValidationResultFormatError("検証結果の形式が不正です。")
    if payload.get("kind") != CodexOutputKind.FINAL.value:
        raise ValidationResultFormatError("検証結果の形式が不正です。")

    valid_value = payload.get("valid")
    comment_value = payload.get("comment")
    if not isinstance(valid_value, bool) or not isinstance(comment_value, str):
        raise ValidationResultFormatError("検証結果の形式が不正です。")
    return ParsedValidatorOutput(valid=valid_value, comment=comment_value)

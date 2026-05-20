import pytest

from backend.application.validation.validate_validator_output import (
    parse_validator_final_output,
)
from backend.shared.errors.errors import ValidationResultFormatError


def test_parse_validator_final_output_accepts_final_payload() -> None:
    """観点：検証用Codex出力固定検証。確認：final payloadを型付き結果へ変換する。"""
    result = parse_validator_final_output(
        '{"payload":{"kind":"final","valid":false,"comment":"根拠不足"}}'
    )

    assert result.valid is False
    assert result.comment == "根拠不足"


@pytest.mark.parametrize(
    "raw_json",
    [
        '{"payload":{"kind":"progress","text":"確認中"}}',
        '{"payload":{"kind":"final","valid":"false","comment":"根拠不足"}}',
        '{"payload":{"kind":"final","valid":false,"comment":null}}',
        '{"payload":null}',
        "[]",
        "{",
    ],
)
def test_parse_validator_final_output_rejects_invalid_payload(raw_json: str) -> None:
    """観点：検証用Codex出力固定検証。確認：final形式以外は形式不正にする。"""
    with pytest.raises(ValidationResultFormatError):
        parse_validator_final_output(raw_json)

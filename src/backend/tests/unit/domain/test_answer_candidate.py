import pytest

from backend.domain.answer.answer_candidate import (
    AnswerParseError,
    GenericAnswerParseFailure,
    InvalidReferencePageRangeFailure,
    InvalidReferencePathFailure,
    parse_generation_final_output,
)


def test_parse_generation_final_output_preserves_answer_blocks() -> None:
    """観点：回答候補固定検証。

    確認：payload.kind=finalの回答本文と参照元の組をブロックとして保持する。
    """
    candidate = parse_generation_final_output(
        """
        {
          "payload": {
            "kind": "final",
            "answers": [
              {
                "text": "  第一回答  ",
                "references": [
                  {
                    "source_type": "pdf",
                    "locator": {
                      "path": "readonly/manuals/guide.pdf",
                      "start_page": 2,
                      "end_page": 4
                    }
                  }
                ]
              },
              {"text": "第二回答", "references": []}
            ]
          }
        }
        """
    )

    assert len(candidate.blocks) == 2
    assert candidate.blocks[0].markdown == "第一回答"
    assert candidate.blocks[1].markdown == "第二回答"
    assert candidate.blocks[0].references[0].label == "guide.pdf"
    assert candidate.blocks[0].references[0].relative_path == "manuals/guide.pdf"
    assert candidate.blocks[0].references[0].page_start == 2
    assert candidate.blocks[0].references[0].page_end == 4
    assert candidate.blocks[1].references == ()


def test_parse_generation_final_output_accepts_payload_final_answers() -> None:
    """観点：回答候補固定検証。

    確認：中間メッセージ用スキーマと同居するpayload.kind=finalの回答を変換する。
    """
    candidate = parse_generation_final_output(
        """
        {
          "payload": {
            "kind": "final",
            "answers": [
              {
                "text": "最終回答",
                "references": [
                  {
                    "source_type": "pdf",
                    "locator": {
                      "path": "readonly/system-test-reference.pdf",
                      "start_page": 1,
                      "end_page": 1
                    }
                  }
                ]
              }
            ]
          }
        }
        """
    )

    assert candidate.blocks[0].markdown == "最終回答"
    assert (
        candidate.blocks[0].references[0].relative_path == "system-test-reference.pdf"
    )


def test_parse_generation_final_output_normalizes_readonly_backslashes() -> None:
    """観点：回答候補固定検証。

    確認：Codex出力のreadonly配下pathは区切り文字差分をPOSIX相対形式へ標準化する。
    """
    candidate = parse_generation_final_output(
        """
        {
          "payload": {
            "kind": "final",
            "answers": [
              {
                "text": "回答",
                "references": [
                  {
                    "source_type": "pdf",
                    "locator": {
                      "path": "readonly\\\\raw\\\\pdf\\\\manual.pdf",
                      "start_page": 1,
                      "end_page": 1
                    }
                  }
                ]
              }
            ]
          }
        }
        """
    )

    assert candidate.blocks[0].references[0].relative_path == "raw/pdf/manual.pdf"


def test_parse_generation_final_output_reports_invalid_reference_paths() -> None:
    """観点：回答候補固定検証の異常系。

    確認：不正な参照元pathを複数件まとめて構造化失敗理由で返す。
    """
    with pytest.raises(AnswerParseError) as exc_info:
        parse_generation_final_output(
            """
            {
              "payload": {
                "kind": "final",
                "answers": [
                  {
                    "text": "回答",
                    "references": [
                      {
                        "source_type": "pdf",
                        "locator": {
                          "path": "manual.pdf",
                          "start_page": 1,
                          "end_page": 1
                        }
                      },
                      {
                        "source_type": "pdf",
                        "locator": {
                          "path": "readonly/html/manual/index.html",
                          "start_page": 2,
                          "end_page": 3
                        }
                      }
                    ]
                  }
                ]
              }
            }
            """
        )

    assert exc_info.value.failure == InvalidReferencePathFailure(
        paths=("manual.pdf", "readonly/html/manual/index.html"),
    )


def test_parse_generation_final_output_reports_invalid_page_ranges() -> None:
    """観点：回答候補固定検証の異常系。

    確認：不正な参照元ページ範囲を複数件まとめて構造化失敗理由で返す。
    """
    with pytest.raises(AnswerParseError) as exc_info:
        parse_generation_final_output(
            """
            {
              "payload": {
                "kind": "final",
                "answers": [
                  {
                    "text": "回答",
                    "references": [
                      {
                        "source_type": "pdf",
                        "locator": {
                          "path": "readonly/manual.pdf",
                          "start_page": 0,
                          "end_page": 1
                        }
                      },
                      {
                        "source_type": "pdf",
                        "locator": {
                          "path": "readonly/guide.pdf",
                          "start_page": 4,
                          "end_page": 3
                        }
                      }
                    ]
                  }
                ]
              }
            }
            """
        )

    failure = exc_info.value.failure
    assert isinstance(failure, InvalidReferencePageRangeFailure)
    assert [
        (item.path, item.page_start, item.page_end) for item in failure.page_ranges
    ] == [
        ("readonly/manual.pdf", 0, 1),
        ("readonly/guide.pdf", 4, 3),
    ]


@pytest.mark.parametrize(
    ("raw_json", "expected_message"),
    [
        (
            "{",
            "回答JSONを解析できません。"
            "最終出力がJSONとして解釈できない文字列になっています。",
        ),
        (
            "[]",
            "回答の形式が不正です。"
            '最終出力が payload.kind="final" を持つJSONオブジェクトになっていません。',
        ),
        (
            '{"payload":{"kind":"progress","text":"確認しています。"}}',
            "回答の形式が不正です。"
            '最終出力が payload.kind="final" を持つJSONオブジェクトになっていません。',
        ),
        (
            '{"payload":{"kind":"final","answers":[]}}',
            "回答が空です。"
            "payload.answers が存在しない、配列ではない、または空配列になっています。",
        ),
        (
            '{"payload":{"kind":"final","answers":[1]}}',
            "回答要素の形式が不正です。"
            "payload.answers[0] がJSONオブジェクトになっていません。",
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":" ","references":[]}]}}',
            "回答本文が空です。"
            "payload.answers[0].text が存在しない、文字列ではない、"
            "または空文字列になっています。",
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答"}]}}',
            "参照元の形式が不正です。"
            "payload.answers[0].references が存在しない、または配列ではありません。",
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":[1]}]}}',
            "参照元要素の形式が不正です。"
            "payload.answers[0].references[0] がJSONオブジェクトになっていません。",
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":'
            '[{"source_type":"web","locator":{}}]}]}}',
            "未対応の参照元種別です。"
            'payload.answers[0].references[0].source_type が "pdf" 以外に'
            "なっています。",
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":'
            '[{"source_type":"pdf","locator":1}]}]}}',
            "参照位置の形式が不正です。"
            "payload.answers[0].references[0].locator が存在しない、"
            "またはJSONオブジェクトではありません。",
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":'
            '[{"source_type":"pdf","locator":{"path":1,'
            '"start_page":1,"end_page":1}}]}]}}',
            "PDF参照位置が不正です。"
            "payload.answers[0].references[0].locator.path、start_page、end_page "
            "のいずれかが参照元PDFの位置情報として不正です。",
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":[]},'
            '{"text":" ","references":[]}]}}',
            "回答本文が空です。"
            "payload.answers[1].text が存在しない、文字列ではない、"
            "または空文字列になっています。",
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":['
            '{"source_type":"pdf","locator":{"path":"readonly/manual.pdf",'
            '"start_page":1,"end_page":1}},'
            '{"source_type":"web","locator":{}}]}]}}',
            "未対応の参照元種別です。"
            'payload.answers[0].references[1].source_type が "pdf" 以外に'
            "なっています。",
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":['
            '{"source_type":"pdf","locator":{"path":"readonly/manual.pdf",'
            '"start_page":1,"end_page":1}},'
            '{"source_type":"pdf","locator":1}]}]}}',
            "参照位置の形式が不正です。"
            "payload.answers[0].references[1].locator が存在しない、"
            "またはJSONオブジェクトではありません。",
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":['
            '{"source_type":"pdf","locator":{"path":"readonly/manual.pdf",'
            '"start_page":1,"end_page":1}},'
            '{"source_type":"pdf","locator":{"path":1,'
            '"start_page":1,"end_page":1}}]}]}}',
            "PDF参照位置が不正です。"
            "payload.answers[0].references[1].locator.path、start_page、end_page "
            "のいずれかが参照元PDFの位置情報として不正です。",
        ),
    ],
)
def test_parse_generation_final_output_reports_generic_failure_messages(
    raw_json: str,
    expected_message: str,
) -> None:
    """観点：回答候補固定検証の異常系。確認：汎用不合格理由に問題点を含める。"""
    with pytest.raises(AnswerParseError) as exc_info:
        parse_generation_final_output(raw_json)

    assert exc_info.value.failure == GenericAnswerParseFailure(expected_message)


@pytest.mark.parametrize(
    "raw_json",
    [
        "{",
        "[]",
        '{"payload":{"kind":"progress","text":"確認しています。"}}',
        '{"payload":{"kind":"final","answers":[]}}',
        '{"payload":{"kind":"final","answers":[1]}}',
        '{"payload":{"kind":"final","answers":[{"text":" ","references":[]}]}}',
        '{"payload":{"kind":"final","answers":[{"text":"回答"}]}}',
        '{"payload":{"kind":"final","answers":[{"text":"回答","references":[1]}]}}',
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":'
            '[{"source_type":"web","locator":{}}]}]}}'
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":'
            '[{"source_type":"pdf","locator":1}]}]}}'
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":'
            '[{"source_type":"pdf","locator":{"path":"manual.pdf",'
            '"start_page":0,"end_page":1}}]}]}}'
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":'
            '[{"source_type":"pdf","locator":{"path":"manual.pdf",'
            '"start_page":3,"end_page":2}}]}]}}'
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":'
            '[{"source_type":"pdf","locator":{"path":"manual.pdf",'
            '"start_page":1,"end_page":1}}]}]}}'
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":'
            '[{"source_type":"pdf","locator":{"path":"raw/pdf/manual.pdf",'
            '"start_page":1,"end_page":1}}]}]}}'
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":'
            '[{"source_type":"pdf","locator":{"path":"codex/readonly/manual.pdf",'
            '"start_page":1,"end_page":1}}]}]}}'
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":'
            '[{"source_type":"pdf","locator":{"path":"readonly/../secret.pdf",'
            '"start_page":1,"end_page":1}}]}]}}'
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":'
            '[{"source_type":"pdf","locator":{"path":"readonly/memo.txt",'
            '"start_page":1,"end_page":1}}]}]}}'
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":'
            '[{"source_type":"pdf","locator":{"path":"C:\\\\data\\\\manual.pdf",'
            '"start_page":1,"end_page":1}}]}]}}'
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":'
            '[{"source_type":"pdf","locator":{"path":"\\\\\\\\server\\\\share\\\\manual.pdf",'
            '"start_page":1,"end_page":1}}]}]}}'
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":'
            '[{"source_type":"pdf","locator":{"path":"readonly\\\\..\\\\secret.pdf",'
            '"start_page":1,"end_page":1}}]}]}}'
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":'
            '[{"source_type":"pdf","locator":{"path":"file:///tmp/manual.pdf",'
            '"start_page":1,"end_page":1}}]}]}}'
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答","references":'
            '[{"source_type":"pdf","locator":{"path":"https://example.test/manual.pdf",'
            '"start_page":1,"end_page":1}}]}]}}'
        ),
    ],
)
def test_parse_generation_final_output_rejects_invalid_generated_payload(
    raw_json: str,
) -> None:
    """観点：回答候補固定検証の異常系。

    確認：生成結果が契約外の場合は採用可能な回答候補へ変換しない。
    """
    with pytest.raises(AnswerParseError):
        parse_generation_final_output(raw_json)

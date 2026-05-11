import pytest

from backend.domain.answer.answer_candidate import (
    AnswerParseError,
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

    確認：不正な参照元pathを複数件まとめて再生成指示へ使える文面で返す。
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

    assert str(exc_info.value) == (
        "参照元のパスが不正なため、この回答は採用できません。\n"
        "以下のパス指定が間違っています。\n"
        "- manual.pdf\n"
        "- readonly/html/manual/index.html\n"
        "参照元の locator.path は、必ず既存の実PDFファイルへのパスを指す "
        "`readonly/... .pdf` 形式にしてください。\n"
        "回答本文は前回同様にユーザ質問へ完全に回答し、"
        "参照元だけを正しいPDFパスへ修正して最終JSONを再出力してください。"
    )


def test_parse_generation_final_output_reports_invalid_page_ranges() -> None:
    """観点：回答候補固定検証の異常系。

    確認：不正な参照元ページ範囲を複数件まとめて再生成指示へ使える文面で返す。
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

    assert str(exc_info.value) == (
        "参照元のページ範囲が不正なため、この回答は採用できません。\n"
        "以下のページ範囲指定が間違っています。\n"
        "- readonly/manual.pdf 0-1ページ\n"
        "- readonly/guide.pdf 4-3ページ\n"
        "参照元の locator.start_page / locator.end_page は、"
        "指定したPDFに実在するページ範囲を指定してください。\n"
        "回答本文は前回同様にユーザ質問へ完全に回答し、"
        "参照元だけを正しいPDFパスとページ範囲へ修正して"
        "最終JSONを再出力してください。"
    )


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

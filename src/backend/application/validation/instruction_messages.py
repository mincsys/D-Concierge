"""生成用Codexへ返す再生成指示メッセージ生成。"""

from backend.application.artifacts.validate_artifact_links import (
    ArtifactLinkValidationResult,
)
from backend.application.ports.codex.dto import ReferenceValidationResult
from backend.domain.answer.answer_candidate import (
    AnswerParseFailure,
    GenericAnswerParseFailure,
    InvalidPageRange,
    InvalidReferencePageRangeFailure,
    InvalidReferencePathFailure,
)

REFERENCE_VALIDATION_FAILED_MESSAGE = "参照元検証に失敗しました。"


def get_answer_parse_failure_message(failure: AnswerParseFailure) -> str:
    """回答候補固定検証失敗を再生成指示へ変換する。"""
    match failure:
        case InvalidReferencePathFailure(paths=paths):
            return get_invalid_reference_path_message(paths)
        case InvalidReferencePageRangeFailure(page_ranges=page_ranges):
            return get_invalid_reference_page_range_message(page_ranges)
        case GenericAnswerParseFailure(message=message):
            return get_generic_fixed_validation_message(message)


def get_generic_fixed_validation_message(reason: str) -> str:
    """回答JSON固定検証不合格を生成用Codexへ伝える再生成指示を組み立てる。"""
    return (
        "回答JSONの固定検証で不合格になったため、この回答は採用できません。\n"
        f"不合格理由：{reason}\n\n"
        "ユーザ指示には完全に回答し、指定スキーマに従って回答を再出力してください。"
    )


def get_invalid_reference_path_message(paths: tuple[str, ...]) -> str:
    """不正な参照元pathを生成用Codexへ伝える再生成指示を組み立てる。"""
    path_lines = "\n".join(f"- {path}" for path in paths)
    return (
        "参照元のパスが不正なため、この回答は採用できません。\n"
        "以下のパス指定が間違っています。\n"
        f"{path_lines}\n"
        "参照元の locator.path は、必ず既存の実PDFファイルへのパスを指す "
        "`readonly/... .pdf` 形式にしてください。\n"
        "回答本文は前回同様にユーザ質問へ完全に回答し、"
        "参照元だけを正しいPDFパスへ修正して最終JSONを再出力してください。"
    )


def get_invalid_reference_page_range_message(
    page_ranges: tuple[InvalidPageRange, ...],
) -> str:
    """不正な参照元ページ範囲を生成用Codexへ伝える再生成指示を組み立てる。"""
    range_lines = "\n".join(
        f"- {page_range.path} {page_range.page_start}-{page_range.page_end}ページ"
        for page_range in page_ranges
    )
    return (
        "参照元のページ範囲が不正なため、この回答は採用できません。\n"
        "以下のページ範囲指定が間違っています。\n"
        f"{range_lines}\n"
        "参照元の locator.start_page / locator.end_page は、"
        "指定したPDFに実在するページ範囲を指定してください。\n"
        "回答本文は前回同様にユーザ質問へ完全に回答し、"
        "参照元だけを正しいPDFパスとページ範囲へ修正して"
        "最終JSONを再出力してください。"
    )


def get_artifact_link_validation_message(
    result: ArtifactLinkValidationResult,
) -> str:
    """成果物リンク固定検証失敗を再生成指示へ変換する。"""
    lines = [
        "成果物リンクが不正なため、この回答は採用できません。",
    ]
    _append_issue_lines(lines, "許可されていない成果物リンク", result.invalid_targets)
    _append_issue_lines(lines, "存在しない成果物ファイル", result.missing_targets)
    _append_issue_lines(
        lines,
        "許可されていない成果物拡張子",
        result.disallowed_suffix_targets,
    )
    lines.extend(
        [
            "回答本文は前回同様にユーザ質問へ完全に回答してください。",
            "成果物リンクは `artifacts/...` または `./artifacts/...` 形式で、"
            "生成用Codexの `artifacts/` 配下に存在するファイルだけを指定してください。",
        ]
    )
    return "\n".join(lines)


def get_reference_validation_failed_message(
    validation: ReferenceValidationResult,
) -> str:
    """参照元検証失敗を再生成指示へ変換する。"""
    match validation.failure:
        case InvalidReferencePathFailure(paths=paths):
            return get_invalid_reference_path_message(paths)
        case InvalidReferencePageRangeFailure(page_ranges=page_ranges):
            return get_invalid_reference_page_range_message(page_ranges)
        case None:
            if validation.comment is None or validation.comment.strip() == "":
                return REFERENCE_VALIDATION_FAILED_MESSAGE
            return validation.comment


def _append_issue_lines(
    lines: list[str], heading: str, targets: tuple[str, ...]
) -> None:
    if not targets:
        return
    lines.append(f"{heading}:")
    lines.extend(f"- {target}" for target in targets)

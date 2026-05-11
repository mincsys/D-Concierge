import json
from dataclasses import dataclass
from pathlib import PurePosixPath

from backend.domain.answer.output_kind import CodexOutputKind
from backend.domain.references.source_type import SourceType

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class AnswerParseError(Exception):
    """回答候補の固定検証失敗。"""

    def __init__(
        self,
        message: str,
        *,
        regeneration_instruction: str | None = None,
    ) -> None:
        super().__init__(message)
        self.regeneration_instruction = regeneration_instruction


@dataclass(frozen=True, slots=True)
class InvalidPageRange:
    """再生成指示へ表示する不正なPDFページ範囲。"""

    path: str
    page_start: int
    page_end: int


@dataclass(frozen=True, slots=True)
class ParsedReference:
    """固定検証済みPDF参照元。"""

    label: str
    relative_path: str
    page_start: int
    page_end: int


@dataclass(frozen=True, slots=True)
class ParsedAnswerCandidate:
    """固定検証済み回答候補。"""

    blocks: tuple["ParsedAnswerBlock", ...]


@dataclass(frozen=True, slots=True)
class ParsedAnswerBlock:
    """固定検証済み回答候補の本文と参照元の組。"""

    markdown: str
    references: tuple[ParsedReference, ...]


def parsed_candidate_references(
    candidate: ParsedAnswerCandidate,
) -> tuple[ParsedReference, ...]:
    """回答候補内の全参照元をブロック順に返す。"""
    return tuple(
        reference for block in candidate.blocks for reference in block.references
    )


_CODEX_READONLY_DIR = "readonly"


def invalid_reference_path_message(paths: list[str]) -> str:
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


def invalid_reference_page_range_message(page_ranges: list[InvalidPageRange]) -> str:
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


def codex_visible_reference_path(relative_path: str) -> str:
    """共有データソース相対pathをCodex作業領域上の表示pathへ戻す。"""
    return PurePosixPath(_CODEX_READONLY_DIR, relative_path).as_posix()


def parse_generation_final_output(raw_json: str) -> ParsedAnswerCandidate:
    """生成用Codexの最終出力envelopeを内部回答候補へ変換する。"""
    loaded = _load_object(raw_json)
    payload_value = loaded.get("payload")
    if (
        not isinstance(payload_value, dict)
        or payload_value.get("kind") != CodexOutputKind.FINAL.value
    ):
        raise AnswerParseError("回答候補の形式が不正です。")
    answers_value = payload_value.get("answers")
    if not isinstance(answers_value, list):
        raise AnswerParseError("回答候補が空です。")
    return _parse_answers(answers_value)


def _load_object(raw_json: str) -> dict[str, JsonValue]:
    try:
        loaded: JsonValue = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise AnswerParseError("回答候補JSONを解析できません。") from exc
    if not isinstance(loaded, dict):
        raise AnswerParseError("回答候補の形式が不正です。")
    return loaded


def _parse_answers(answers_value: list[JsonValue]) -> ParsedAnswerCandidate:
    if len(answers_value) == 0:
        raise AnswerParseError("回答候補が空です。")

    blocks: list[ParsedAnswerBlock] = []
    for answer_value in answers_value:
        if not isinstance(answer_value, dict):
            raise AnswerParseError("回答要素の形式が不正です。")
        text_value = answer_value.get("text")
        if not isinstance(text_value, str) or text_value.strip() == "":
            raise AnswerParseError("回答本文が空です。")
        references_value = answer_value.get("references")
        if not isinstance(references_value, list):
            raise AnswerParseError("参照元の形式が不正です。")
        blocks.append(
            ParsedAnswerBlock(
                markdown=text_value.strip(),
                references=tuple(_parse_references(references_value)),
            )
        )

    return ParsedAnswerCandidate(blocks=tuple(blocks))


def _parse_references(references_value: list[JsonValue]) -> list[ParsedReference]:
    parsed: list[ParsedReference] = []
    invalid_paths: list[str] = []
    invalid_page_ranges: list[InvalidPageRange] = []
    for reference_value in references_value:
        if not isinstance(reference_value, dict):
            raise AnswerParseError("参照元要素の形式が不正です。")
        source_type = reference_value.get("source_type")
        if source_type != SourceType.PDF.value:
            raise AnswerParseError("未対応の参照元種別です。")
        locator_value = reference_value.get("locator")
        if not isinstance(locator_value, dict):
            raise AnswerParseError("参照位置の形式が不正です。")
        path_value = locator_value.get("path")
        start_page_value = locator_value.get("start_page")
        end_page_value = locator_value.get("end_page")
        if (
            not isinstance(path_value, str)
            or not isinstance(start_page_value, int)
            or not isinstance(end_page_value, int)
        ):
            raise AnswerParseError("PDF参照位置が不正です。")
        relative_path = _try_normalize_readonly_pdf_path(path_value)
        if relative_path is None:
            invalid_paths.append(path_value)
            continue
        if start_page_value < 1 or end_page_value < start_page_value:
            invalid_page_ranges.append(
                InvalidPageRange(
                    path=path_value,
                    page_start=start_page_value,
                    page_end=end_page_value,
                )
            )
            continue
        parsed.append(
            ParsedReference(
                label=PurePosixPath(relative_path).name,
                relative_path=relative_path,
                page_start=start_page_value,
                page_end=end_page_value,
            )
        )
    if invalid_paths:
        message = invalid_reference_path_message(invalid_paths)
        raise AnswerParseError(message, regeneration_instruction=message)
    if invalid_page_ranges:
        message = invalid_reference_page_range_message(invalid_page_ranges)
        raise AnswerParseError(message, regeneration_instruction=message)
    return parsed


def _try_normalize_readonly_pdf_path(path_value: str) -> str | None:
    try:
        return _normalize_readonly_pdf_path(path_value)
    except AnswerParseError:
        return None


def _normalize_readonly_pdf_path(path_value: str) -> str:
    if "\x00" in path_value or "\\" in path_value:
        raise AnswerParseError("PDF参照位置が不正です。")

    path = PurePosixPath(path_value)
    parts = path.parts
    if path.is_absolute() or len(parts) < 2 or parts[0] != _CODEX_READONLY_DIR:
        raise AnswerParseError("PDF参照位置が不正です。")
    if any(part in {"", ".", ".."} for part in parts):
        raise AnswerParseError("PDF参照位置が不正です。")

    relative_path = PurePosixPath(*parts[1:])
    if relative_path.suffix.lower() != ".pdf":
        raise AnswerParseError("PDF参照位置が不正です。")
    return relative_path.as_posix()

import json
from dataclasses import dataclass
from pathlib import PurePosixPath

from backend.domain.answer.output_kind import CodexOutputKind
from backend.domain.references.pdf_reference import (
    InvalidPdfReferenceError,
    PdfLocator,
    PdfReference,
)
from backend.domain.references.source_type import SourceType

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True, slots=True)
class InvalidPageRange:
    """不正なPDFページ範囲。"""

    path: str
    page_start: int
    page_end: int


@dataclass(frozen=True, slots=True)
class GenericAnswerParseFailure:
    """構造化できない回答候補固定検証失敗。"""

    message: str


@dataclass(frozen=True, slots=True)
class InvalidReferencePathFailure:
    """不正な参照元pathを含む固定検証失敗。"""

    paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InvalidReferencePageRangeFailure:
    """不正な参照元ページ範囲を含む固定検証失敗。"""

    page_ranges: tuple[InvalidPageRange, ...]


type AnswerParseFailure = (
    GenericAnswerParseFailure
    | InvalidReferencePathFailure
    | InvalidReferencePageRangeFailure
)
type ReferenceValidationFailure = (
    InvalidReferencePathFailure | InvalidReferencePageRangeFailure
)


class AnswerParseError(Exception):
    """回答候補の固定検証失敗。"""

    def __init__(self, failure: AnswerParseFailure | str) -> None:
        if isinstance(failure, str):
            failure = GenericAnswerParseFailure(failure)
        super().__init__(_failure_message(failure))
        self.failure = failure


@dataclass(frozen=True, slots=True)
class ParsedAnswerCandidate:
    """固定検証済み回答候補。"""

    blocks: tuple["ParsedAnswerBlock", ...]


@dataclass(frozen=True, slots=True)
class ParsedAnswerBlock:
    """固定検証済み回答候補の本文と参照元の組。"""

    markdown: str
    references: tuple[PdfReference, ...]


def parsed_candidate_references(
    candidate: ParsedAnswerCandidate,
) -> tuple[PdfReference, ...]:
    """回答候補内の全参照元をブロック順に返す。"""
    return tuple(
        reference for block in candidate.blocks for reference in block.references
    )


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


def _parse_references(references_value: list[JsonValue]) -> list[PdfReference]:
    parsed: list[PdfReference] = []
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
        try:
            locator = PdfLocator(
                relative_path=relative_path,
                page_start=start_page_value,
                page_end=end_page_value,
            )
        except InvalidPdfReferenceError:
            invalid_page_ranges.append(
                InvalidPageRange(
                    path=path_value,
                    page_start=start_page_value,
                    page_end=end_page_value,
                )
            )
            continue
        parsed.append(PdfReference.from_locator(locator))
    if invalid_paths:
        raise AnswerParseError(InvalidReferencePathFailure(tuple(invalid_paths)))
    if invalid_page_ranges:
        raise AnswerParseError(
            InvalidReferencePageRangeFailure(tuple(invalid_page_ranges))
        )
    return parsed


def _try_normalize_readonly_pdf_path(path_value: str) -> str | None:
    try:
        return _normalize_readonly_pdf_path(path_value)
    except AnswerParseError:
        return None


def _normalize_readonly_pdf_path(path_value: str) -> str:
    if "\x00" in path_value:
        raise AnswerParseError("PDF参照位置が不正です。")

    normalized_path_value = path_value.replace("\\", "/")
    path = PurePosixPath(normalized_path_value)
    parts = path.parts
    if path.is_absolute() or len(parts) < 2 or parts[0] != "readonly":
        raise AnswerParseError("PDF参照位置が不正です。")
    if any(part in {"", ".", ".."} for part in parts):
        raise AnswerParseError("PDF参照位置が不正です。")

    relative_path = PurePosixPath(*parts[1:]).as_posix()
    try:
        PdfLocator(relative_path=relative_path, page_start=1, page_end=1)
    except InvalidPdfReferenceError as exc:
        raise AnswerParseError("PDF参照位置が不正です。") from exc
    return relative_path


def _failure_message(failure: AnswerParseFailure) -> str:
    match failure:
        case GenericAnswerParseFailure(message=message):
            return message
        case InvalidReferencePathFailure():
            return "PDF参照位置が不正です。"
        case InvalidReferencePageRangeFailure():
            return "参照元ページ範囲が不正です。"

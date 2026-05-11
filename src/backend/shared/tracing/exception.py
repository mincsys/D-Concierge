import traceback

MAX_TRACE_TEXT_LENGTH = 65_536
MAX_STACKTRACE_LENGTH = 1_048_576
_TRUNCATED_MARKER = "...<truncated>"


def limit_trace_text(value: str, max_length: int = MAX_TRACE_TEXT_LENGTH) -> str:
    """トレースログ用文字列を上限長で切り詰める。"""
    if len(value) <= max_length:
        return value
    return value[: max_length - len(_TRUNCATED_MARKER)] + _TRUNCATED_MARKER


def exception_message(exc: BaseException) -> str:
    """例外メッセージをトレースログ用に返す。"""
    return limit_trace_text(str(exc))


def exception_stacktrace(exc: BaseException) -> str:
    """例外のスタックトレースをトレースログ用に返す。"""
    return limit_trace_text(
        "".join(traceback.format_exception(exc)),
        max_length=MAX_STACKTRACE_LENGTH,
    )

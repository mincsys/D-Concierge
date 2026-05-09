from enum import StrEnum


class ErrorClass(StrEnum):
    """アプリケーション全体で扱うエラー分類。"""

    INPUT = "input"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    CONFIGURATION = "configuration"
    FORBIDDEN = "forbidden"
    SYSTEM = "system"


class AppError(Exception):
    """利用者向け応答へ変換できるアプリケーション例外。"""

    def __init__(self, error_class: ErrorClass, user_message: str) -> None:
        super().__init__(user_message)
        self.error_class = error_class
        self.user_message = user_message


PDF_READ_FAILURE_MESSAGE = "PDF読み取り中にエラーが発生しました。"


class ReferencePdfReadError(AppError):
    """存在する参照元PDFを読み取れないことを示すシステムエラー。"""

    def __init__(self, relative_path: str, cause: Exception) -> None:
        super().__init__(ErrorClass.SYSTEM, PDF_READ_FAILURE_MESSAGE)
        self.relative_path = relative_path
        self.cause_type = type(cause).__name__
        self.cause_message = str(cause)

    @property
    def diagnostic_message(self) -> str:
        """トレースログ向けの診断メッセージを返す。"""
        if self.cause_message == "":
            return (
                f"参照元PDFを読み取れません: {self.relative_path} "
                f"({self.cause_type})"
            )
        return (
            f"参照元PDFを読み取れません: {self.relative_path} "
            f"({self.cause_type}: {self.cause_message})"
        )


class RunTimeoutError(Exception):
    """チャット実行または外部実行がタイムアウトしたことを示す。"""

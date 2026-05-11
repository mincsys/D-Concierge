from backend.shared.error_class import ErrorClass


class AppError(Exception):
    """利用者向け応答へ変換できるアプリケーション例外。"""

    def __init__(self, error_class: ErrorClass, user_message: str) -> None:
        super().__init__(user_message)
        self.error_class = error_class
        self.user_message = user_message


PDF_READ_FAILURE_MESSAGE = "PDF読み取り中にエラーが発生しました。"
VALIDATION_RESULT_FAILURE_MESSAGE = "回答の検証に失敗しました。再度お試しください。"


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
                f"参照元PDFを読み取れません: {self.relative_path} ({self.cause_type})"
            )
        return (
            f"参照元PDFを読み取れません: {self.relative_path} "
            f"({self.cause_type}: {self.cause_message})"
        )


class ValidationWorkspacePreparationError(AppError):
    """検証用Codex作業領域の準備に失敗したことを示すシステムエラー。"""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(ErrorClass.SYSTEM, "処理中にエラーが発生しました。")
        self.message = message
        self.cause_type = type(cause).__name__ if cause is not None else ""
        self.cause_message = str(cause) if cause is not None else ""

    @property
    def diagnostic_message(self) -> str:
        """トレースログ向けの診断メッセージを返す。"""
        if self.cause_type == "":
            return self.message
        if self.cause_message == "":
            return f"{self.message} ({self.cause_type})"
        return f"{self.message} ({self.cause_type}: {self.cause_message})"


class ValidationResultFormatError(AppError):
    """検証用Codexの最終検証結果形式が不正であることを示すシステムエラー。"""

    def __init__(self, diagnostic_message: str) -> None:
        super().__init__(ErrorClass.SYSTEM, VALIDATION_RESULT_FAILURE_MESSAGE)
        self.diagnostic_message = diagnostic_message


class RunTimeoutError(Exception):
    """チャット実行または外部実行がタイムアウトしたことを示す。"""

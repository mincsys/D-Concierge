from backend.shared.errors.error_type import ErrorType


class AppError(Exception):
    """アプリ内部で扱う構造化エラー。

    diagnostic_message はトレースログへ記録する開発者向け診断文だけを保持する。
    trace=False のエラーでは diagnostic_message を原則空文字にし、
    利用者向け文言や画面表示用メッセージを入れてはならない。
    """

    def __init__(
        self,
        error_type: ErrorType,
        *,
        trace: bool = False,
        diagnostic_message: str = "",
        cause: Exception | None = None,
    ) -> None:
        if trace and diagnostic_message == "":
            raise ValueError("trace=True の AppError には診断メッセージが必要です。")
        if not trace and diagnostic_message != "":
            raise ValueError(
                "trace=False の AppError に診断メッセージを設定できません。"
            )
        super().__init__(diagnostic_message)
        self.error_type = error_type
        self.trace = trace
        self.diagnostic_message = diagnostic_message
        self.cause = cause


class FieldValidationError(AppError):
    """入力欄単位の検証エラー。"""

    def __init__(self, field_errors: dict[str, str]) -> None:
        super().__init__(ErrorType.INPUT)
        self.field_errors = field_errors


class AuthenticationRequiredError(AppError):
    """ログインが必要であることを示す。"""

    def __init__(self) -> None:
        super().__init__(ErrorType.UNAUTHORIZED)


class UserInstructionRequiredError(AppError):
    """ユーザ指示が空であることを示す入力エラー。"""

    def __init__(self) -> None:
        super().__init__(ErrorType.INPUT)


class ChatNotFoundError(AppError):
    """対象チャットが存在しないことを示す。"""

    def __init__(self) -> None:
        super().__init__(ErrorType.NOT_FOUND)


class ChatDeletingError(AppError):
    """対象チャットが削除中で操作できないことを示す。"""

    def __init__(self) -> None:
        super().__init__(ErrorType.CONFLICT)


class RunNotFoundError(AppError):
    """対象runが存在しないことを示す。"""

    def __init__(self) -> None:
        super().__init__(ErrorType.NOT_FOUND)


class ChatRunNotFoundError(AppError):
    """対象チャット実行処理が存在しないことを示す。"""

    def __init__(self) -> None:
        super().__init__(ErrorType.NOT_FOUND)


class ReferenceNotFoundError(AppError):
    """対象参照元が存在しないことを示す。"""

    def __init__(self) -> None:
        super().__init__(ErrorType.NOT_FOUND)


class ArtifactNotFoundError(AppError):
    """対象成果物が存在しないことを示す。"""

    def __init__(self) -> None:
        super().__init__(ErrorType.NOT_FOUND)


class ReferenceNotDisplayableError(AppError):
    """対象参照元を表示できないことを示す。"""

    def __init__(self) -> None:
        super().__init__(ErrorType.FORBIDDEN)


class ArtifactNotDisplayableError(AppError):
    """対象成果物を表示できないことを示す。"""

    def __init__(self) -> None:
        super().__init__(ErrorType.FORBIDDEN)


class FileNotDisplayableError(AppError):
    """指定ファイルを表示できないことを示す。"""

    def __init__(self) -> None:
        super().__init__(ErrorType.FORBIDDEN)


class ActiveRunConflictError(AppError):
    """未完了runが存在するため操作を受け付けられないことを示す。"""

    def __init__(self) -> None:
        super().__init__(ErrorType.CONFLICT)


class CancelNotAllowedError(AppError):
    """対象runをキャンセルできないことを示す。"""

    def __init__(self) -> None:
        super().__init__(ErrorType.CONFLICT)


class ProcessCanceledConflictError(AppError):
    """処理がキャンセル済みのため続行できないことを示す。"""

    def __init__(self) -> None:
        super().__init__(ErrorType.CONFLICT)


class RunStateChangedError(AppError):
    """run状態が想定外に変更されていることを示す。"""

    def __init__(self) -> None:
        super().__init__(ErrorType.CONFLICT)


class ArtifactAlreadySavedError(AppError):
    """対象成果物が保存済みであることを示す。"""

    def __init__(self) -> None:
        super().__init__(ErrorType.CONFLICT)


class ReferencePdfReadError(AppError):
    """存在する参照元PDFを読み取れないことを示すシステムエラー。"""

    def __init__(self, relative_path: str, cause: Exception) -> None:
        diagnostic_message = _format_cause_message(
            f"参照元PDFを読み取れません: {relative_path}", cause
        )
        super().__init__(
            ErrorType.SYSTEM,
            trace=True,
            diagnostic_message=diagnostic_message,
            cause=cause,
        )
        self.relative_path = relative_path


class ValidationWorkspacePreparationError(AppError):
    """検証用Codex作業領域の準備に失敗したことを示すシステムエラー。"""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        diagnostic_message = (
            message if cause is None else _format_cause_message(message, cause)
        )
        super().__init__(
            ErrorType.SYSTEM,
            trace=True,
            diagnostic_message=diagnostic_message,
            cause=cause,
        )


class ValidationResultFormatError(AppError):
    """検証用Codexの最終検証結果形式が不正であることを示すシステムエラー。"""

    def __init__(self, diagnostic_message: str) -> None:
        super().__init__(
            ErrorType.SYSTEM,
            trace=True,
            diagnostic_message=diagnostic_message,
        )


class CodexProviderError(AppError):
    """codex execがJSONLでAIサービスプロバイダ側エラーを返したことを示す。"""

    def __init__(self, event_type: str, message: str | None, stage: str) -> None:
        diagnostic_message = (
            "Codex JSONLエラーイベントを受信しました。"
            f"event_type={event_type}; message={message or '(messageなし)'}"
        )
        super().__init__(
            ErrorType.SYSTEM,
            trace=True,
            diagnostic_message=diagnostic_message,
        )
        self.codex_event_type = event_type
        self.codex_message = message
        self.stage = stage


class CodexProcessFailureError(AppError):
    """codex execがJSONLエラーなしに異常終了したことを示す。"""

    def __init__(self, return_code: int, stderr: str, stage: str) -> None:
        stderr_summary = stderr.strip() or "(stderrなし)"
        diagnostic_message = (
            "CodexプロセスがJSONLエラーなしに異常終了しました。"
            f"return_code={return_code}; stderr={stderr_summary}"
        )
        super().__init__(
            ErrorType.SYSTEM,
            trace=True,
            diagnostic_message=diagnostic_message,
        )
        self.return_code = return_code
        self.stderr = stderr
        self.stage = stage


class RunTimeoutError(Exception):
    """チャット実行または外部実行がタイムアウトしたことを示す。"""


def _format_cause_message(message: str, cause: Exception) -> str:
    cause_type = type(cause).__name__
    cause_message = str(cause)
    if cause_message == "":
        return f"{message} ({cause_type})"
    return f"{message} ({cause_type}: {cause_message})"

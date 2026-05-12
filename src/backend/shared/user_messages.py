"""利用者向けに表示・保存するメッセージ定義。"""

USER_INSTRUCTION_REQUIRED_MESSAGE = "ユーザ指示を入力してください。"
REQUEST_VALIDATION_FAILURE_MESSAGE = "リクエストの形式が不正です。"
CANCEL_NOT_ALLOWED_MESSAGE = "この処理はキャンセルできません。"
PROCESS_CANCELED_CONFLICT_MESSAGE = "この処理はキャンセルされました。"
CANCEL_REQUESTED_MESSAGE = "処理をキャンセルしています。"
CANCELED_MESSAGE = "処理をキャンセルしました。"

WORK_STARTED_MESSAGE = "作業を開始します。"
WORK_COMPLETED_MESSAGE = "作業が完了しました。"
VALIDATION_STARTED_MESSAGE = "回答を検証します。"
VALIDATION_COMPLETED_MESSAGE = "回答を検証しました。"
ANSWER_REVISION_MESSAGE = "回答を修正します。"

GENERATION_FAILURE_MESSAGE = "回答の生成に失敗しました。再度お試しください。"
VALIDATION_FAILURE_MESSAGE = "回答の生成に失敗しました。再度お試しください。"
VALIDATION_RESULT_FAILURE_MESSAGE = "回答の検証に失敗しました。再度お試しください。"
PDF_READ_FAILURE_MESSAGE = "PDF読み取り中にエラーが発生しました。"
CONFIGURATION_FAILURE_MESSAGE = (
    "アプリケーション設定に問題があるため、処理を実行できませんでした。"
)
TIMEOUT_FAILURE_MESSAGE = (
    "回答生成が時間内に完了しませんでした。ユーザ指示を絞って再度お試しください。"
)
UNEXPECTED_FAILURE_MESSAGE = (
    "予期しないエラーが発生しました。開発者にお問い合わせください。"
)

ANSWER_VALIDATION_FAILED_MESSAGE = "回答を検証できませんでした。"
CHAT_NOT_FOUND_MESSAGE = "対象のチャットが見つかりません。"
RUN_NOT_FOUND_MESSAGE = "対象の実行処理が見つかりません。"
CHAT_RUN_NOT_FOUND_MESSAGE = "対象のチャット実行処理が見つかりません。"
REFERENCE_NOT_FOUND_MESSAGE = "対象の参照元が見つかりません。"
REFERENCE_NOT_DISPLAYABLE_MESSAGE = "対象の参照元は表示できません。"
ARTIFACT_NOT_FOUND_MESSAGE = "対象の成果物が見つかりません。"
ARTIFACT_NOT_DISPLAYABLE_MESSAGE = "対象の成果物は表示できません。"
ARTIFACT_ALREADY_SAVED_MESSAGE = "対象の成果物は保存済みです。"
FILE_NOT_DISPLAYABLE_MESSAGE = "指定されたファイルは表示できません。"
ACTIVE_RUN_CONFLICT_MESSAGE = "実行中の処理があるため送信できません。"
RUN_STATE_CHANGED_MESSAGE = "実行状態が変更されています。"
DISPATCH_FAILURE_MESSAGE = "チャット実行処理を開始できませんでした。"
RECOVERY_ERROR_MESSAGE = "アプリ起動時に処理を再開できませんでした。"

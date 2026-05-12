"""利用者向けに表示・保存するメッセージ定義。"""

USER_INSTRUCTION_REQUIRED_MESSAGE = "ユーザ指示を入力してください。"
CANCEL_NOT_ALLOWED_MESSAGE = "この処理はキャンセルできません。"
PROCESS_CANCELED_CONFLICT_MESSAGE = "この処理はキャンセルされました。"
CANCEL_REQUESTED_MESSAGE = "処理をキャンセルしています。"
CANCELED_MESSAGE = "処理をキャンセルしました。"

WORK_STARTED_MESSAGE = "作業を開始します。"
WORK_COMPLETED_MESSAGE = "作業が完了しました。"
VALIDATION_STARTED_MESSAGE = "回答の検証を開始します。"
VALIDATION_COMPLETED_MESSAGE = "回答の検証を完了しました。"
ANSWER_REVISION_MESSAGE = "回答を修正します。"

GENERATION_FAILURE_MESSAGE = "回答の生成に失敗しました。再度お試しください。"
VALIDATION_FAILURE_MESSAGE = "回答の生成に失敗しました。再度お試しください。"
VALIDATION_RESULT_FAILURE_MESSAGE = "回答の検証に失敗しました。再度お試しください。"
PDF_READ_FAILURE_MESSAGE = "PDF読み取り中にエラーが発生しました。"
TIMEOUT_FAILURE_MESSAGE = (
    "回答生成が時間内に完了しませんでした。ユーザ指示を絞って再度お試しください。"
)
UNEXPECTED_FAILURE_MESSAGE = "処理中にエラーが発生しました。"

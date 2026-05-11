from enum import Enum


class RunState(Enum):
    """チャット実行状態。"""

    ACCEPTED = "受付"
    RUNNING = "実行中"
    VALIDATING = "検証中"
    CANCEL_REQUESTED = "キャンセル要求中"
    CANCELED = "キャンセル済み"
    COMPLETED = "完了"
    ERROR = "エラー"
    TIMED_OUT = "タイムアウト"

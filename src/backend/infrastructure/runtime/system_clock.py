from datetime import UTC, datetime


class SystemClock:
    """UTC現在時刻を提供する本番Clock実装。"""

    def now(self) -> datetime:
        """タイムゾーン付きUTC現在時刻を返す。"""
        return datetime.now(UTC)

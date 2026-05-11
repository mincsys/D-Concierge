from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo


class SystemClock:
    """UTC現在時刻とアプリタイムゾーン現在時刻を提供する本番Clock実装。"""

    def __init__(
        self,
        app_timezone: ZoneInfo | None = None,
        time_source: Callable[[], datetime] | None = None,
    ) -> None:
        self._app_timezone = (
            app_timezone if app_timezone is not None else ZoneInfo("UTC")
        )
        self._time_source = (
            time_source if time_source is not None else lambda: datetime.now(UTC)
        )

    def now(self) -> datetime:
        """タイムゾーン付きUTC現在時刻を返す。"""
        return self.now_utc()

    def now_utc(self) -> datetime:
        """タイムゾーン付きUTC現在時刻を返す。"""
        return self._time_source().astimezone(UTC)

    def now_app_timezone(self) -> datetime:
        """アプリタイムゾーンの現在時刻を返す。"""
        return self.now_utc().astimezone(self._app_timezone)

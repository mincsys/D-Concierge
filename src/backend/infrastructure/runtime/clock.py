from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo


class SystemClock:
    """システム現在時刻を返すClock実装。"""

    def __init__(self, timezone: ZoneInfo | str) -> None:
        self._timezone = ZoneInfo(timezone) if isinstance(timezone, str) else timezone

    def now_utc(self) -> datetime:
        return datetime.now(UTC)

    def now_app_timezone(self) -> datetime:
        return datetime.now(self._timezone)

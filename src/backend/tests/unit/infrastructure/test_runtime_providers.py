from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from backend.infrastructure.runtime.system_clock import SystemClock
from backend.infrastructure.runtime.uuid_generator import UuidGenerator


def test_runtime_providers_generate_clock_and_uuid_values() -> None:
    """観点：Runtime Provider IF。確認：本番実装がUTC現在時刻とUUIDを提供する。"""
    now = SystemClock().now()
    generated = UuidGenerator().new_uuid()

    assert now.tzinfo is UTC
    assert isinstance(generated, UUID)


def test_system_clock_returns_utc_and_app_timezone_values() -> None:
    """観点：Runtime Provider IF。確認：UTC時刻とアプリ時刻を提供する。"""
    clock = SystemClock(
        app_timezone=ZoneInfo("Asia/Tokyo"),
        time_source=lambda: datetime(2026, 5, 10, 15, 0, tzinfo=UTC),
    )

    assert clock.now() == datetime(2026, 5, 10, 15, 0, tzinfo=UTC)
    assert clock.now_utc() == datetime(2026, 5, 10, 15, 0, tzinfo=UTC)
    assert clock.now_app_timezone() == datetime(
        2026, 5, 11, 0, 0, tzinfo=ZoneInfo("Asia/Tokyo")
    )

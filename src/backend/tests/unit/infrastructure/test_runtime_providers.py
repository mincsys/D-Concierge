from datetime import UTC
from uuid import UUID

from backend.infrastructure.runtime.system_clock import SystemClock
from backend.infrastructure.runtime.uuid_generator import UuidGenerator


def test_runtime_providers_generate_clock_and_uuid_values() -> None:
    """観点：Runtime Provider IF。確認：本番実装がUTC現在時刻とUUIDを提供する。"""
    now = SystemClock().now()
    generated = UuidGenerator().new_uuid()

    assert now.tzinfo is UTC
    assert isinstance(generated, UUID)

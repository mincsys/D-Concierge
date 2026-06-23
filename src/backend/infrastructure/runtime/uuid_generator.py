from __future__ import annotations

from uuid import UUID, uuid7


class UuidGenerator:
    """UUIDv7を発番する本番実装。"""

    def new_uuid(self) -> UUID:
        return uuid7()

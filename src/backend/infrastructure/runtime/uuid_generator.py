from uuid import UUID, uuid7


class UuidGenerator:
    """UUIDを発番する本番実装。"""

    def new_uuid(self) -> UUID:
        """新しいUUIDを返す。"""
        return uuid7()

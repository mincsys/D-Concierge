from pydantic import BaseModel

from backend.presentation.schemas.api import (
    AppConfigResponseSchema,
    ChatDetailResponseSchema,
    ChatStartRequestSchema,
    ChatStartResponseSchema,
)


def test_api_schemas_are_pydantic_models() -> None:
    """観点：APIスキーマ設計。確認：API境界のschemaをPydanticモデルとして定義する。"""
    assert issubclass(AppConfigResponseSchema, BaseModel)
    assert issubclass(ChatStartRequestSchema, BaseModel)
    assert issubclass(ChatStartResponseSchema, BaseModel)
    assert issubclass(ChatDetailResponseSchema, BaseModel)

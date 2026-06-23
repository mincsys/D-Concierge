from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppConfigResponse:
    """画面へ公開するアプリ設定レスポンス。"""

    welcome_message: str | None = None
    sub_welcome_message: str | None = None
    input_suggestions: tuple[str, ...] = ()

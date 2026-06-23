from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class AuthenticatedUserResult:
    """認証済みユーザ情報。"""

    user_id: str
    user_name: str


@dataclass(frozen=True, slots=True)
class SessionIssueResult:
    """Cookieへ返すセッション発行結果。"""

    user: AuthenticatedUserResult
    session_token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AccountStateResult:
    """アカウント状態更新結果。"""

    account_state: str

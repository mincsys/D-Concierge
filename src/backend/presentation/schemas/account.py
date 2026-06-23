from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RegisterAccountRequest:
    """アカウント登録リクエスト。"""

    user_id: str
    user_name: str
    password: str
    password_confirmation: str


@dataclass(frozen=True, slots=True)
class LoginRequest:
    """ログインリクエスト。"""

    user_id: str
    password: str


@dataclass(frozen=True, slots=True)
class ChangeUserNameRequest:
    """ユーザ名変更リクエスト。"""

    user_name: str


@dataclass(frozen=True, slots=True)
class ChangePasswordRequest:
    """パスワード変更リクエスト。"""

    current_password: str
    new_password: str
    new_password_confirmation: str


@dataclass(frozen=True, slots=True)
class UserPayload:
    """画面へ返すユーザ情報。"""

    user_id: str
    user_name: str


@dataclass(frozen=True, slots=True)
class UserResponse:
    """ユーザ情報レスポンス。"""

    user: UserPayload


@dataclass(frozen=True, slots=True)
class DeleteAccountResponse:
    """アカウント削除受付レスポンス。"""

    account_state: str

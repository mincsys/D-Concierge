from __future__ import annotations

from dataclasses import fields, is_dataclass


def test_account_repository_port_exposes_f002_account_methods() -> None:
    """
    観点：AccountRepository IFが認証・アカウント管理ユースケースの永続化境界を表すこと
    確認：ユーザ登録、ログイン検証、セッション作成/削除、削除受付、
    論理削除受付に必要な公開メソッドがProtocolに定義されていること
    """
    from backend.application.ports.database.interface import AccountRepositoryPort

    expected_method_names = (
        "create_user",
        "get_user_for_login",
        "update_user_name",
        "update_password_hash",
        "create_login_session",
        "find_session_by_token_hash",
        "delete_session_by_token_hash",
        "delete_sessions_by_user_id",
        "mark_user_deleting",
        "mark_user_chats_deleting",
    )

    for method_name in expected_method_names:
        assert hasattr(AccountRepositoryPort, method_name), method_name


def test_account_repository_dtos_expose_f002_account_fields() -> None:
    """
    観点：Repository DTOがapplication層に必要な認証・削除判定情報をORMなしで返すこと
    確認：AccountUserData、LoginSessionDataがdataclassであり、
    ログイン検証と認証状態確認に必要なユーザ状態を保持すること
    """
    from backend.application.ports.database.dto import (
        AccountUserData,
        LoginSessionData,
    )

    assert is_dataclass(AccountUserData)
    assert is_dataclass(LoginSessionData)

    user_fields = _dataclass_field_names(AccountUserData)
    session_fields = _dataclass_field_names(LoginSessionData)

    assert {"user_id", "user_name", "password_hash", "user_state"} <= user_fields
    assert {
        "session_row_id",
        "token_hash",
        "user_id",
        "user_name",
        "user_state",
        "expires_at",
    } <= session_fields


def test_password_and_session_token_ports_are_security_boundary() -> None:
    """
    観点：パスワードハッシュとセッショントークンをapplication層から具象実装へ直結しないこと
    確認：PasswordHasherPortとSessionTokenProviderPortがsecurity portとして定義され、
    ハッシュ化、検証、発行、照合用ハッシュ生成の公開メソッドを持つこと
    """
    from backend.application.ports.security.interface import (
        PasswordHasherPort,
        SessionTokenProviderPort,
    )

    assert hasattr(PasswordHasherPort, "hash_password")
    assert hasattr(PasswordHasherPort, "verify_password")
    assert hasattr(SessionTokenProviderPort, "issue_token")
    assert hasattr(SessionTokenProviderPort, "hash_token")


def test_account_deletion_dispatcher_port_exposes_result_status() -> None:
    """
    観点：アカウント削除受付が非同期削除ジョブ登録依頼をport経由で行うこと
    確認：AccountDeletionDispatcherPort、AccountDeletionDispatchResult、
    AccountDeletionDispatchStatusが受付境界のruntime portとして定義されること
    """
    from backend.application.ports.runtime.interface import (
        AccountDeletionDispatcherPort,
        AccountDeletionDispatchResult,
        AccountDeletionDispatchStatus,
    )

    assert hasattr(AccountDeletionDispatcherPort, "dispatch_account_deletion")
    assert is_dataclass(AccountDeletionDispatchResult)
    assert tuple(status.value for status in AccountDeletionDispatchStatus) == (
        "registered",
        "already_registered",
        "failed",
    )


def test_account_repository_port_exposes_f007_physical_delete_methods() -> None:
    """
    観点：AccountRepository IFがF007のアカウント物理削除と起動時回復の
    永続化境界を表すこと
    確認：期限切れセッション削除、削除中ユーザ一覧、物理削除対象取得、
    DBデータ削除に必要な公開メソッドがProtocolに定義されること
    """
    from backend.application.ports.database.interface import AccountRepositoryPort

    expected_method_names = (
        "delete_expired_sessions",
        "list_deleting_user_ids",
        "get_account_deletion_target",
        "delete_account_data",
    )

    for method_name in expected_method_names:
        assert hasattr(AccountRepositoryPort, method_name), method_name


def test_account_deletion_target_exposes_f007_physical_delete_fields() -> None:
    """
    観点：AccountDeletionTargetがアカウント物理削除に必要な情報をORMなしで返すこと
    確認：対象user_id、未完了run、作業領域削除対象session_idをDTO項目として
    保持すること
    """
    from backend.application.ports.database.dto import AccountDeletionTarget

    assert is_dataclass(AccountDeletionTarget)
    assert {
        "user_id",
        "unfinished_run_ids",
        "active_chat_session_ids",
    } <= _dataclass_field_names(AccountDeletionTarget)


def test_account_deletion_runtime_ports_expose_f007_executor_boundary() -> None:
    """
    観点：アカウント削除ジョブ登録と実行本体の責務がruntime portで分離されること
    確認：AccountDeletionExecutorPortがexecuteを持ち、Dispatcherは
    dispatch_account_deletionだけでDBやファイルを直接操作しない境界として定義されること
    """
    from backend.application.ports.runtime.interface import (
        AccountDeletionDispatcherPort,
        AccountDeletionExecutorPort,
    )

    assert hasattr(AccountDeletionDispatcherPort, "dispatch_account_deletion")
    assert hasattr(AccountDeletionExecutorPort, "execute")


def _dataclass_field_names(dataclass_type: type) -> set[str]:
    return {field.name for field in fields(dataclass_type)}

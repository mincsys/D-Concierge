# SqlAlchemyAccountRepositoryクラス設計

## 1. 文書の目的

本書は、`SqlAlchemyAccountRepository` クラスの責務、不変条件、公開メソッドを定義することを目的とする。

## 2. 前提

- 本クラスは `クラス一覧.md` で詳細設計対象としたクラスである。
- 本クラスは `AccountRepositoryPort` を実装する。
- SQLAlchemy ORMモデルをapplication層へ返さず、Repository DTOへ変換して返す。

## 3. 責務

- `users`、`login_sessions`、アカウント削除に必要な関連テーブルをSQLAlchemyで読み書きする。
- ユーザ作成、ユーザ名更新、パスワードハッシュ更新、ユーザ状態更新を行う。
- ログインセッションの作成、トークンハッシュ検索、現在セッション削除、ユーザ単位削除、期限切れ削除を行う。
- アカウント削除受付時に、対象ユーザの全チャットを`削除中`へ更新する。
- アカウント物理削除時に、未完了run、削除対象セッションID、保存済み成果物参照を取得する。
- ファイル削除完了後に、対象ユーザに紐づくDBデータを削除する。

## 4. 不変条件

- パスワード生値とログインセッショントークン生値を受け取らない。
- login sessionは `token_hash` で照合し、Cookie生値をDBへ保存しない。
- `users`、`chats`、`login_sessions` の状態更新は呼出元のトランザクション境界に従う。
- `削除中`ユーザを通常操作用の参照結果に含めない。
- 物理削除対象のファイル参照は、application層がユーザ単位削除を判断できるDTOで返す。

## 5. 公開メソッド

| メソッド | 役割 | 入力 | 出力 | 事前条件 | 事後条件 |
| --- | --- | --- | --- | --- | --- |
| `create_user` | ユーザを作成する | ユーザID、ユーザ名、パスワードハッシュ、作成日時 | ユーザDTO | ユーザIDが未登録であること | `users` に`通常`状態のユーザが追加されること |
| `get_user_for_login` | ログイン検証用ユーザ情報を取得する | ユーザID | ユーザDTOまたはなし | なし | パスワードハッシュとユーザ状態が取得できること |
| `update_user_name` | ユーザ名を更新する | ユーザID、新しいユーザ名、更新日時 | 更新後ユーザDTO | 対象ユーザが`通常`で存在すること | `users.user_name` と `updated_at` が更新されること |
| `update_password_hash` | パスワードハッシュを更新する | ユーザID、新しいパスワードハッシュ、更新日時 | なし | 対象ユーザが`通常`で存在すること | `users.password_hash` と `updated_at` が更新されること |
| `create_login_session` | ログインセッションを作成する | token_hash、ユーザID、有効期限、作成日時 | ログインセッションDTO | 対象ユーザが`通常`で存在すること | `login_sessions` に新規行が追加されること |
| `find_session_by_token_hash` | セッションと所有ユーザを取得する | token_hash | ログインセッションDTOまたはなし | なし | 有効期限とユーザ状態を判定できる情報が返ること |
| `delete_session_by_token_hash` | 現在セッションを削除する | token_hash | 削除件数 | なし | 対応する `login_sessions` 行が削除されること |
| `delete_sessions_by_user_id` | ユーザ単位でログインセッションを削除する | ユーザID | 削除件数 | なし | 対象ユーザの全 `login_sessions` 行が削除されること |
| `delete_expired_sessions` | 期限切れセッションを削除する | 現在時刻 | 削除件数 | なし | `expires_at` が現在時刻以前のセッション行が削除されること |
| `mark_user_deleting` | ユーザを`削除中`へ更新する | ユーザID、更新日時 | 更新後状態 | 対象ユーザが存在すること | `users.user_state` が`削除中`になること |
| `mark_user_chats_deleting` | ユーザの全チャットを`削除中`へ更新する | ユーザID、更新日時 | 更新件数 | 対象ユーザが存在すること | 対象ユーザの `chats.chat_state` が`削除中`になること |
| `list_deleting_user_ids` | 起動時再登録対象を取得する | なし | 削除中ユーザID一覧 | なし | `削除中`ユーザだけが返ること |
| `get_account_deletion_target` | アカウント物理削除対象を取得する | ユーザID | 削除対象DTOまたはなし | 対象ユーザが`削除中`であること | 未完了run、セッションID、保存済み成果物参照が取得できること |
| `delete_account_data` | 対象ユーザのDBデータを削除する | ユーザID | なし | 対象ユーザが`削除中`であること<br>ファイル削除が完了していること | 対象ユーザに紐づくDBデータが削除されること |

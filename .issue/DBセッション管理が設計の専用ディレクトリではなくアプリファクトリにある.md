# DBセッション管理が設計の専用ディレクトリではなくアプリファクトリにある

## 内容

`docs/03_内部設計/01_アーキテクチャ設計/ディレクトリ構成.md` では、`src/backend/infrastructure/database/session/` を「DB接続、セッション、トランザクション処理」の配置先としている。

一方、現行実装では `src/backend/infrastructure/database/session/` は空であり、DB engineと `sessionmaker` の生成は `src/backend/app/factory.py` の `_create_sqlalchemy_repository()` に直書きされている。Repositoryは `sessionmaker` を受け取り、各Repositoryメソッド内でSQLAlchemy sessionとトランザクションを開始している。

## 影響

app層がDB接続生成の詳細を知っているため、composition rootが肥大化している。また、DB接続設定、engine生成、session生成の単体テストや差し替え境界が設計書上の配置とずれている。

トランザクション境界についても、処理設計ではユースケース単位の境界を意識している一方、実装ではRepositoryメソッド単位に閉じているため、将来複数Repositoryをまたぐ処理が増えると設計との差分が広がる。

## 設計と実装の評価

設計の方がよい。ただし、現時点でRepositoryメソッドがユースケース上の1操作に対応している箇所は多いため、トランザクション制御の全面変更を急ぐ必要はない。

まずは `infrastructure/database/session` にDB engine/session factory生成を移し、`app/factory.py` はその生成関数またはクラスを呼び出すだけにするのがよい。トランザクション境界をユースケース側へ寄せるかは、複数Repository操作が必要になった段階で別途判断する。

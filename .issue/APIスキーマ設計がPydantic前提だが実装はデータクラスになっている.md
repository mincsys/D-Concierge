# APIスキーマ設計がPydantic前提だが実装はdataclassになっている

## 内容

`docs/03_内部設計/02_クラス・モジュール設計/01_バックエンド/クラス一覧.md` では、`AppConfigResponseSchema`、`ChatStartRequestSchema`、`ChatDetailResponseSchema` などをPydanticスキーマとして扱う前提になっている。

一方、現行実装の `src/backend/presentation/schemas.py` は `pydantic.BaseModel` ではなく、`dataclasses.dataclass` でAPI request/response schemaを定義している。

また、ディレクトリ構成では `src/backend/presentation/schemas/` 配下にスキーマを置く設計だが、現行実装は `src/backend/presentation/schemas.py` の単一ファイルであり、`src/backend/presentation/schemas/` ディレクトリは空になっている。

## 影響

FastAPIの入力検証・OpenAPI生成・エラー形式の挙動について、設計書を読む人はPydanticモデル前提で判断するが、実装はdataclass変換に依存している。今後フィールド制約やalias、追加プロパティ制御を入れるときに設計と実装の前提差が問題になる。

## 設計と実装の評価

設計の方がよい。API境界の明示的な入力検証、OpenAPI、レスポンスモデルとしての可読性を考えると、Pydantic `BaseModel` を使う方がFastAPI標準に沿う。

対応は `presentation/schemas.py` をPydanticモデルへ戻すか、dataclassを正式採用するなら設計書から「Pydanticスキーマ」という記述を消して、FastAPI dataclass schemaとして制約と限界を明記する。

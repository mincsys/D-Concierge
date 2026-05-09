# codex exec実行環境とセッション管理

## 目的

本メモは、PDF検索アプリ構成時のcodex exec起動例と、後続設計で具体化する検討事項を整理する。

## 起動例

PDF検索アプリを構成する場合の生成用codex exec起動例:

```bash
CODEX_HOME=codex/.codex \
codex exec --json --output-schema codex/output_json_schema/pdf-reference-schema.json \
  -C codex/sessions/<user-id>/<session-id> \
  "<利用者のユーザ指示>"
```

継続指示の起動例:

```bash
CODEX_HOME=codex/.codex \
codex exec --json --output-schema codex/output_json_schema/pdf-reference-schema.json \
  -C codex/sessions/<user-id>/<session-id> \
  resume <codex-thread-id> \
  "<利用者の継続指示>"
```

PDF検索アプリを構成する場合の検証用codex exec起動例:

```bash
CODEX_HOME=codex/.codex_validator \
codex exec --json --output-schema codex/output_json_schema/validator_schema.json \
  -C codex/sessions_validator/<user-id>/<session-id> \
  "<参照元検証依頼>"
```

継続検証の起動例:

```bash
CODEX_HOME=codex/.codex_validator \
codex exec --json --output-schema codex/output_json_schema/validator_schema.json \
  -C codex/sessions_validator/<user-id>/<session-id> \
  resume <validator-codex-thread-id> \
  "<参照元検証依頼>"
```

## 後続設計で決めること

次の項目は、内部設計または実装設計で具体化する。

- `<user-id>/<session-id>/` 全体のサイズ上限
- セッションディレクトリの保存期間
- 古いセッションディレクトリのクリーンアップ方針
- Codex成果物のMIMEタイプと拡張子の許可リスト
- 保存済みCodex成果物領域の容量上限とクリーンアップ方針

# 設定ファイル IF

## 1. 文書の目的

本書は、D-Concierge MVPがアプリケーション設定から読み取る設定項目と、それらが画面表示、codex exec連携、検証、実行制約に与える影響を定義することを目的とする。

## 2. 前提

- 設定ファイル名は `config.yaml` を標準とする。
- 相対パスはアプリケーション実行基準ディレクトリからの相対パスとして扱う。
- 秘密情報を画面向けAPI、SSE、利用者向けエラーに出さない。
- 設定変更を画面から行う機能はMVP対象外である。

## 3. インターフェース概要

### 3.1. 連携目的

| 項目 | 内容 |
| --- | --- |
| 文書名 | 設定ファイル IF |
| 連携目的 | 用途別アプリの画面表示、回答生成、検証、参照元表示、実行制約を制御するため。 |
| 関連機能 | アプリ設定取得、回答生成、回答検証、参照元表示、タイムアウト制御 |

### 3.2. 連携対象

| 項目 | 内容 |
| --- | --- |
| 読み取り元 | `config.yaml` |
| 読み取り先 | バックエンド |
| 方向 | 読み取り |
| 主要情報 | アプリ共通設定、UI設定、共有データソース設定、Codex設定、検証設定、データベース設定、サーバ設定、実行制約 |

## 4. 設定項目一覧

| 設定項目 | 必須 | 内容 | 利用箇所 |
| --- | --- | --- | --- |
| `app.timezone` | 必須 | アプリケーションが運用者向け日時へ使用するIANA timezone名。MVP標準は `Asia/Tokyo`。 | トレースログ、日時表示 |
| `ui.welcome_message` | 任意 | 開始画面の入力欄上に表示する文言。 | `GET /api/app-config` |
| `ui.input_suggestions` | 任意 | 開始画面の入力候補チップ文字列配列。 | `GET /api/app-config` |
| `datasource.dir` | 必須 | 共有データソースのベースディレクトリ。 | 参照元表示、回答生成、回答検証 |
| `codex.home` | 必須 | 生成指示を記載した `AGENTS.md` と生成用Skillsを含む、生成用codex execのホームディレクトリ。 | codex exec IF |
| `codex.workdir` | 必須 | 生成用セッションベースディレクトリ。 | codex exec IF |
| `codex.output_schema` | 必須 | 生成用codex execの出力契約。 | 回答生成、形式検証 |
| `codex.saved_artifacts_dir` | 必須 | 検証済み回答が参照するCodex成果物本体の保存領域。 | Codex成果物配信 |
| `validator.max_retries` | 必須 | 検証失敗後の再生成上限。 | 回答検証 |
| `validator.codex.home` | 必須 | 検証指示を記載した `AGENTS.md` と検証用Skillsを含む、検証用codex execのホームディレクトリ。 | codex exec IF |
| `validator.codex.workdir` | 必須 | 検証用セッションベースディレクトリ。 | codex exec IF |
| `validator.codex.output_schema` | 必須 | 検証用codex execの検証結果出力契約。 | 回答検証 |
| `database.url` | 必須 | データベース接続先。 | 永続化 |
| `server.timeout_seconds` | 必須 | 回答生成から検証完了までのタイムアウト値。 | 実行制約 |
| `trace_log.dir` | 必須 | 異常系トレースログYAMLファイルの保存先。 | ログ設計 |
| `trace_log.retention_days` | 必須 | トレースログの日付ディレクトリを保持する日数。正の整数を指定する。MVP標準は90日。 | ログ設計 |
| `trace_log.max_files_per_day` | 必須 | アプリケーション起動ごとの同日トレースログ最大保存件数。正の整数を指定する。MVP標準は1000件。 | ログ設計 |

## 5. 画面公開設定

`GET /api/app-config` で画面へ返す設定は次に限定する。

| API項目 | 設定元 | 未設定時 |
| --- | --- | --- |
| `welcome_message` | `ui.welcome_message` | 表示しない。 |
| `input_suggestions` | `ui.input_suggestions` | 入力候補チップを表示しない。 |

次の情報は画面へ返さない。

- codex execのホームディレクトリ。
- 作業ディレクトリ。
- 共有データソース配置先。
- Codex成果物保存領域。
- データベース接続先。
- トレースログ保存先。
- アプリ共通タイムゾーン。
- 秘密情報。
- 内部パス。

## 6. パス設定の扱い

- 共有データソース配置先は `datasource.dir` から決まる。
- 生成用 `CODEX_HOME` は `codex.home` から決まる。
- 生成指示と生成用Skillsは、`codex.home` 配下の `AGENTS.md` とSkillsから決まる。
- 生成用作業ディレクトリは、DBに保存された利用者IDとセッションIDを使い、`codex.workdir/<user-id>/<session-id>` から決まる。
- 生成用出力スキーマは `codex.output_schema` から決まる。
- 保存済みCodex成果物領域は `codex.saved_artifacts_dir` から決まる。
- 検証用 `CODEX_HOME` は `validator.codex.home` から決まる。
- 検証指示と検証用Skillsは、`validator.codex.home` 配下の `AGENTS.md` とSkillsから決まる。
- 検証用作業ディレクトリは、DBに保存された利用者IDとセッションIDを使い、`validator.codex.workdir/<user-id>/<session-id>` から決まる。
- 検証用出力スキーマは `validator.codex.output_schema` から決まる。
- トレースログ保存期間は `trace_log.retention_days` から決まる。
- アプリケーション起動ごとの同日トレースログ最大保存件数は `trace_log.max_files_per_day` から決まる。
- トレースログの日付ディレクトリ、ファイル名、発生日時、保存期間判定は `app.timezone` から決まる。
- Windows/Linuxのパス区切り、ドライブ文字、大文字小文字差異はバックエンド内部で正規化する。

## 7. 異常時の扱い

| 事象 | 扱い |
| --- | --- |
| 必須設定不足 | アプリケーション起動または対象機能の実行を失敗させ、トレースログを保存する。 |
| 不正なパス設定 | 許可範囲外参照として拒否する。 |
| UI設定不足 | ウェルカムメッセージまたは入力候補チップを表示しない。 |
| タイムアウト設定不正 | 実行受付を行わず、利用者向けエラーを返す。 |
| タイムゾーン設定不正 | アプリケーション起動または対象機能の実行を失敗させ、トレースログを保存する。 |
| トレースログ保持設定不正 | アプリケーション起動または対象機能の実行を失敗させ、トレースログを保存する。 |

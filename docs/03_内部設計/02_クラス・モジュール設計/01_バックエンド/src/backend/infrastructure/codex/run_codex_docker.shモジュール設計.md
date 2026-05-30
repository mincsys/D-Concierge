# run_codex_docker.shモジュール設計

## 1. 文書の目的

本書は、`run_codex_docker.sh` の責務、不変条件、公開引数、終了コードを定義することを目的とする。

## 2. 前提

- 本書の対象は `src/backend/infrastructure/codex/run_codex_docker.sh` のみとする。
- 本スクリプトは `CodexRunner` から `subprocess.Popen` の引数配列で呼び出され、シェル文字列評価を前提にしない。
- 標準出力はCodex JSONLだけを流し、スクリプト自身のエラーと診断情報は標準エラーへ出力する。

## 3. 責務

- 名前付き引数で受け取ったホスト側パス、コンテナ内パス、Dockerイメージ、コンテナ名をもとに `docker run` を実行する。
- Docker起動オプション、環境変数、bind mount、作業ディレクトリを組み立てる。
- コンテナ内で `codex exec --json --skip-git-repo-check --sandbox workspace-write --output-schema` を実行する。
- `--conversation-id` が指定された場合だけ `codex exec resume` を使う。
- `--host-artifacts` が指定された場合だけ、生成用成果物候補領域を読み取り専用でマウントする。
- 引数不足や不正な `--schema-file` を終了コード `2` の引数不正として返す。

## 4. 不変条件

- `eval` を使わず、bash配列でDocker引数とCodex引数を組み立てる。
- `CODEX_API_KEY` は空文字でもDockerコンテナへ環境変数として渡す。
- `HOME` は `/home/codex`、`CODEX_HOME` は `--codex-home-dir` の値としてDockerコンテナへ渡す。
- チャット作業ディレクトリは `--workspace-dir` へbind mountし、`--workdir` も同じ値にする。
- 共有データソースは `<workspace_dir>/data_source` へ読み取り専用でbind mountする。
- 出力スキーマ親ディレクトリは `/tmp/output_json_schema` へ読み取り専用でbind mountする。
- `--schema-file` はファイル名だけを許可し、`/` または `..` を含む値を拒否する。

## 5. 公開引数

| 引数 | 必須 | 役割 |
| --- | --- | --- |
| `--container-name` | 必須 | Dockerコンテナ名 |
| `--image` | 必須 | Codex実行コンテナのDockerイメージ |
| `--workspace-dir` | 必須 | コンテナ内Codex作業ディレクトリ |
| `--codex-home-dir` | 必須 | コンテナ内Codexホームディレクトリ |
| `--host-codex-home` | 必須 | ホスト側Codexホームディレクトリ |
| `--host-workdir` | 必須 | ホスト側セッション作業ディレクトリ |
| `--host-data-source` | 必須 | ホスト側共有データソースディレクトリ |
| `--host-schema-dir` | 必須 | ホスト側出力スキーマ親ディレクトリ |
| `--schema-file` | 必須 | 出力スキーマファイル名 |
| `--prompt` | 必須 | Codexへ渡すプロンプト |
| `--host-artifacts` | 任意 | 検証用Codexへ提示する生成用成果物候補ディレクトリ |
| `--conversation-id` | 任意 | Codex側resume用ID |

## 6. 終了コード

| 終了コード | 条件 | 扱い |
| --- | --- | --- |
| `0` | Codex実行が正常終了した | 標準出力JSONLを `CodexRunner` が解析する |
| `2` | 必須引数不足、オプション値不足、不正な `--schema-file` | Codex起動失敗として扱う |
| その他 | Docker起動失敗、mount失敗、Codexプロセス異常終了 | JSONL上のCodexエラーがなければプロセス異常終了として扱う |

## 7. 標準入出力

| 種別 | 内容 |
| --- | --- |
| 標準出力 | `codex exec --json` が出力するJSONLだけを流す |
| 標準エラー | スクリプトの引数不正、Docker起動失敗、mount失敗、Codexの標準エラーを流す |

## 8. Docker実行オプション

| オプション | 内容 |
| --- | --- |
| `--rm` | コンテナ終了時に自動削除する |
| `--name` | `CodexRunner` が指定したコンテナ名を使う |
| `--user "$(id -u):$(id -g)"` | バックエンド実行ユーザと同じUID/GIDで実行する |
| `--read-only` | コンテナのroot filesystemを書き込み不可にする |
| `--tmpfs /tmp:rw,nosuid,nodev,size=1g` | `/tmp` だけ一時書き込み領域として提供する |
| `--security-opt seccomp=unconfined` | Codex CLIの実行に必要なseccomp設定を適用する |
| `--cap-drop ALL` | Linux capabilityを追加で持たせない |

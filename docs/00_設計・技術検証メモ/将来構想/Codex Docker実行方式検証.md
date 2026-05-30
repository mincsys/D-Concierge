# Codex Docker実行方式検証

## 目的

本メモは、現在ホスト上で実行している `codex exec` をDockerコンテナ内で実行する方式へ変更できるかを検証し、実装時の変更範囲と注意点を整理する。

## 背景

現行方式では、バックエンドプロセスがホスト上で `codex exec` を起動する。Codexが実行するコマンドはCodex CLIのサンドボックス設定に従うが、プロセス自体はホスト上で動くため、ホストのファイルシステム構造を前提にした設計になっている。

`.issue/2026-05-11_10-47-03_dockerコンテナ内でCodexを実行する.md` では、ホスト内の任意ディレクトリ構造やファイルを読み込めてしまうリスクを下げるため、Codex実行をコンテナ内に閉じる必要があると整理している。

## 調査日と前提

調査日: 2026-05-28

検証対象:

- `infra/codex_docker/Dockerfile`
- `infra/codex_docker/scripts/run_docker_codex_exec.sh`
- `infra/codex_docker/.codex/config.toml`

検証に使用したDockerイメージ:

- `codex-python-runner:latest`

## 実験用Docker構成

実験用スクリプトは、概ね以下の構成で `codex exec` を起動する。

- コンテナは `--read-only` で起動する。
- `/tmp` と `/workspace` は `tmpfs` とする。
- ホスト側の `.codex` を `/home/codex/.codex` にマウントする。
- ホスト側の `data_source` を `/workspace/data_source` に読み取り専用でマウントする。
- ホスト側の `artifacts` を `/workspace/artifacts` に書き込み可能でマウントする。
- 作業ディレクトリは `/workspace` とする。
- Codex CLIは `codex exec --json --skip-git-repo-check --sandbox workspace-write` で起動する。
- コンテナ自体はCodex APIへ接続するためネットワークを持つ。
- Codexが起動するシェルコマンドのネットワークアクセスは `.codex/config.toml` の `sandbox_workspace_write.network_access = false` で禁止する。

## 検証結果

### 基本実行

`infra/codex_docker/scripts/run_docker_codex_exec.sh` を `infra/codex_docker` 直下から実行し、コンテナ内の作業ディレクトリとホストディレクトリの見え方を確認した。

結果:

- `pwd` は `/workspace` になった。
- `/workspace` には `data_source` と `artifacts` が見えた。
- ホスト側の `/home/minami/dev/D-Concierge` はコンテナ内に存在しなかった。

この結果から、実験用スクリプトの範囲では、Codex実行時の作業領域を `/workspace` に限定できている。

### 読み取り専用データと成果物書き込み

Codexが起動したシェルコマンドから、`/workspace/data_source` と `/workspace/artifacts` への書き込み可否を確認した。

結果:

- `/workspace/data_source` には書き込めなかった。
- `/workspace/artifacts` には書き込めた。
- `/workspace/artifacts` に作成したファイルは、ホスト側の `infra/codex_docker/artifacts` に残った。

この結果から、参照データを読み取り専用で提示し、Codex成果物だけをホストへ戻す構成は実現できる。

### ネットワークアクセス

Codexが起動したPythonプロセスから `https://example.com` へ接続できるかを確認した。

結果:

- Codexが起動したシェルコマンドからのネットワーク接続は失敗した。
- 一方で、コンテナ自体はCodex APIへ接続する必要があるため、Dockerのネットワーク自体は有効である。

このため、ネットワーク制御はDockerの `--network none` ではなく、Codex CLIのサンドボックス設定でCodex実行コマンド側を制限する方式になる。

### Codex認証情報の参照可否

実験用構成では、ホスト側の `.codex` を `/home/codex/.codex` にマウントする。APIキーを使わずに `codex login` で認証する場合、`auth.json` がこの領域に保存される。

Codexが起動したシェルコマンドから、`/home/codex/.codex/auth.json` の存在と読み取り可否だけを確認した。

結果:

- `/home/codex/.codex/auth.json` は存在した。
- Codexが起動したシェルコマンドから読み取り可能だった。

この結果から、`.codex` 全体をコンテナへマウントする方式では、Codexが実行するコマンドからCodex認証情報を参照できる。`shell_environment_policy` により環境変数を絞っても、ファイルとしてマウントした認証情報の読み取りは防げない。

正式実装では、Codexの過去履歴、Skills、`AGENTS.md` をCodexへ提示するため、`.codex` 全体をコンテナへマウントする。`auth.json` の有無は利用環境ごとの運用判断に委ねる。不特定多数の利用者が使う環境では `auth.json` を作成せず、Codex認証は `CODEX_API_KEY` をコンテナ環境変数として渡す。少人数利用など `auth.json` がCodex実行コマンドから読めても問題にならない環境では、ログイン方式で作成された `auth.json` を含む `.codex` をそのままマウントしてよい。

`CODEX_API_KEY` を利用する場合は、`shell_environment_policy` によりCodexが起動するシェルコマンドへ `CODEX_API_KEY` を継承させない。

### 出力スキーマ指定

現行の生成用JSON Schemaを `/workspace/output_schema.json` に読み取り専用マウントし、Docker内で `codex exec --json --output-schema /workspace/output_schema.json` を実行した。

結果:

- `thread.started` と `turn.started` がJSONLで出力された。
- 最終 `agent_message` は指定したスキーマに従うJSONになった。
- `turn.completed` で正常終了した。

この結果から、現行の `--output-schema` 指定はDocker内実行でも利用できる。

### 会話継続

同じ `.codex` をマウントした状態で、別コンテナ起動の `codex exec resume <thread_id> ...` を実行した。

結果:

- `thread.started` の `thread_id` は指定したIDになった。
- 最終 `agent_message` が返り、`turn.completed` で正常終了した。

この結果から、生成用・検証用のCodex側会話継続IDをDBに保存し、後続実行で `resume` する現行設計は、Docker内実行でも維持できる。

### 検証用成果物提示

検証用Codexで生成用成果物を提示するケースを想定し、生成用 `artifacts/` の実体ディレクトリをDockerのbind mount元として `/workspace/artifacts` に読み取り専用マウントした。

結果:

- `/workspace/artifacts/result.txt` をコンテナ内から読めた。
- `/workspace/artifacts` への書き込みは失敗した。

この結果から、検証用で成果物提示が必要な場合は、生成用 `artifacts/` の実体ディレクトリを読み取り専用で `/workspace/artifacts` にマウントすることで、生成用と検証用Codexの見える内容を揃えられる。

### タイムアウト時のコンテナ残存

`timeout 2s docker run --rm --name <name> ... sleep 60` を実行し、Dockerクライアント側をタイムアウトさせたときにコンテナが残るかを確認した。

結果:

- `timeout` の終了コードは `124` になった。
- タイムアウト直後も、対象コンテナは起動したまま残っていた。
- 明示的に `docker stop <name>` を実行すると停止し、`--rm` により削除された。

この結果から、バックエンドが単に `docker run` プロセスへ終了要求を送るだけでは不十分である。タイムアウトまたはキャンセル時に確実に停止するため、正式実装ではrun単位で一意なコンテナ名を付け、終了時に `docker stop`、必要に応じて `docker rm -f` を実行できる制御が必要になる。

`docker run --rm` で起動したコンテナに対して停止時間も測定した。通常の `docker stop` は既定の停止猶予時間により約10秒かかった。`docker stop -t 1` では約1.2秒で停止し、`--rm` によりコンテナは削除された。

このため、タイムアウトまたはキャンセル時に利用者を長く待たせないためには、Docker停止時の猶予秒数を明示する。猶予時間を短くしすぎるとCodex CLIや子プロセスの後処理を待てないため、正式設計では短い猶予時間を設定したうえで、必要に応じて強制削除する。

実際の `codex exec` が `sleep 60` をコマンド実行中の状態でも停止時間を測定した。`docker stop -t 1` は約0.28秒、通常の `docker stop` は約0.32秒で停止し、`--rm` によりコンテナは削除された。単純な `sleep` コンテナより短時間で止まったため、Codex CLIはSIGTERMを受けて速やかに終了していると考えられる。

ただし、この挙動はCodex CLIと実行中の子プロセスの状態に依存する。正式実装では、通常は `docker stop -t <秒数>` で停止を要求し、停止できない場合は `docker rm -f` で強制削除する。

## 実装上の変更点

Docker内実行では、`CodexRunner` が以下の流れでCodexを起動する。

1. `CodexGenerationRunnerAdapter` または `CodexValidationRunnerAdapter` が、ホスト上のセッション作業領域を作る。
2. 共有データソースと成果物領域をCodex実行コンテナへマウントする。
3. `CodexRunner` が `codex exec --json --output-schema <schema>` をコンテナ内で起動する。
4. キャンセルやタイムアウトでは、対象コンテナへ終了要求を送る。

Docker内実行では、`codex exec` の起動先をホストからコンテナへ変えるだけでは不十分である。コンテナ内から見えるパスへ、次の値を変換する必要がある。

| ホスト側の値 | Docker内の値 |
| --- | --- |
| `request.workdir` | `/workspace` |
| `request.workdir/artifacts` | `/workspace/artifacts` |
| `request.output_schema` | `/workspace/output_schema.json` など |
| `request.codex_home` | `/home/codex/.codex` |
| `data_source_dir` | `/workspace/data_source` |

また、単純な `ProcessFactory.start(command, cwd, env)` だけでは、Dockerに必要なマウント元を安全に決めにくい。Docker実行を正式採用する場合は、`CodexRunRequest` 全体を見てDockerコマンドを組み立てられる境界に整理する方がよい。

## 変更可能性

現在のシステムをDocker内Codex実行方式へ変更することは可能である。

理由:

- `codex exec --json` のJSONL出力形式は維持できる。
- `--output-schema` はDocker内でも動作する。
- `resume <conversation_id>` も同じ `.codex` をマウントすれば動作する。
- 共有データソースを読み取り専用、`artifacts` を書き込み可能として分離できる。
- ホストのプロジェクトルート全体をコンテナに見せずに実行できる。
- コンテナ名を管理すれば、現行のキャンセル・タイムアウトと同じ考え方で実行単位を停止対象にできる。

ただし、正式実装では以下の整理が必要になる。

- Dockerイメージ名、`.codex` マウント元、Codex実行時の内部パスを設定化する。
- 生成用と検証用で `artifacts` を提示する条件を分ける。
- `output_schema` はコンテナ内パスへマウントして渡す。
- `data_source_dir` はコンテナ内 `/workspace/data_source` へ読み取り専用マウントする。
- `workdir/artifacts` はコンテナ内 `/workspace/artifacts` へ書き込み可能マウントする。
- Docker未起動、イメージ未作成、マウント元不足、Docker実行権限不足をシステムエラーとして扱う。
- キャンセル時とタイムアウト時は、`docker run` プロセスだけでなく、コンテナ内のCodex実行も確実に終了することをテストする。
- 不特定多数の利用者が使う環境では `.codex/auth.json` を作成しない運用にする。
- `CODEX_API_KEY` はCodex CLIプロセスへ渡し、Codexが起動するシェルコマンドへは継承させない。

## 推奨方針

Docker内実行方式を採用する場合は、現行の `CodexRunner` のJSONL解析、エラー分類、会話ID保存、出力スキーマ解析は維持し、プロセス起動境界だけを差し替える。

推奨する実装方針:

- `CodexRunner` の責務は、JSONL解析、最終出力確定、キャンセル管理に寄せる。
- プロセス起動境界にDocker用実装を追加し、`docker run ... codex exec ...` を起動する。
- Docker用実装は `CodexRunRequest` からマウントとコンテナ内コマンドを組み立てる。
- Docker用実装はrun単位で一意なコンテナ名を付け、タイムアウト時とキャンセル時に対象コンテナを明示的に停止する。
- 停止時は `docker stop -t <秒数>` のように停止猶予時間を明示し、停止できない場合は強制削除する。
- 生成用セッションの `artifacts/` はホストのセッション作業領域へマウントし、採用済み成果物保存処理は現行どおりホスト側ファイルとして扱う。
- 検証用では、成果物リンクを含む回答候補を検証するときだけ生成用 `artifacts/` の実体ディレクトリを読み取り専用で提示する。

`infra/codex_docker` の実験用スクリプトは、正式実装のたたき台として利用できる。ただし、現在のスクリプトは `PWD` 配下の固定ディレクトリを前提にしているため、そのままバックエンドに組み込むのではなく、設定値と `CodexRunRequest` に基づいてDockerコマンドを生成する実装へ置き換える。

## 追加検証観点

正式実装前に、以下を追加で確認する。

- キャンセル時にDockerコンテナが残らないこと。
- 同時に複数runを実行しても、各コンテナの `/workspace`、`.codex`、`artifacts` が混線しないこと。
- Dockerイメージが存在しない場合のエラーメッセージ。
- Dockerデーモンへ接続できない場合のエラーメッセージ。
- Linux以外の開発環境で必要なパス変換。
- APIキー方式で、Codex CLIには `CODEX_API_KEY` を渡し、Codexが起動するシェルコマンドには渡らないこと。
- 利用環境に応じて、APIキー方式とログイン方式のどちらで認証するかを運用で選べること。
- Dockerイメージの更新手順とCIでの扱い。

## 現時点の結論

Docker内で `codex exec` を実行する方式へ変更できる見込みは高い。

この方式により、Codex実行時に見えるファイルシステムを `/workspace/data_source` と `/workspace/artifacts` に限定しやすくなる。現行の `codex exec --json`、`--output-schema`、`resume` を維持できるため、`codex app-server` へ切り替えるよりも現在の実装への影響は小さい。

正式採用する場合は、Docker実行を単なるシェルスクリプト呼び出しにせず、バックエンドのCodexプロセス起動境界として設計し、マウント、パス変換、キャンセル、タイムアウト、認証情報の露出防止をテスト対象にする。

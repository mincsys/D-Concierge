# Codex exec JSONL出力検証

## 目的

`codex exec --json --output-schema <schema>` の実出力を確認し、D-Conciergeのバックエンドで中間メッセージと最終回答JSONをどう扱うかを明確にする。

## 検証条件

- 実施日: 2026-05-07
- Codex CLI: `codex-cli 0.128.0`
- 生成用ホーム: `codex/.codex`
- 作業ディレクトリ: `codex/sessions/user-id-xxxxx/id-xxxxx`
- 出力スキーマ: `codex/sessions/user-id-xxxxx/id-xxxxx/tmp/verification-output-schema.json`
- 最終メッセージファイル: `codex/sessions/user-id-xxxxx/id-xxxxx/tmp/last-message-*.json`

検証用作業ディレクトリには次の要素を配置した。

```text
codex/sessions/user-id-xxxxx/id-xxxxx/
  readonly -> ../../../readonly
  tmp/
  artifacts/
```

実行形は次の通りである。

```bash
CODEX_HOME=codex/.codex codex exec --json --output-schema codex/sessions/user-id-xxxxx/id-xxxxx/tmp/verification-output-schema.json --output-last-message codex/sessions/user-id-xxxxx/id-xxxxx/tmp/last-message-normal.json -C codex/sessions/user-id-xxxxx/id-xxxxx "<検証用プロンプト>"
```

継続質問の実行形は次の通りである。

```bash
CODEX_HOME=codex/.codex codex exec --json --output-schema codex/sessions/user-id-xxxxx/id-xxxxx/tmp/verification-output-schema.json --output-last-message codex/sessions/user-id-xxxxx/id-xxxxx/tmp/last-message-resume.json -C codex/sessions/user-id-xxxxx/id-xxxxx resume <codex-thread-id> "<継続質問プロンプト>"
```

`resume` と `--output-schema` を併用する場合は、`--json`、`--output-schema`、`--output-last-message`、`-C` を `resume` より前に指定する。

## resume検証

初回実行時のJSONLに含まれる `thread.started` の `thread_id` を指定して、`codex exec resume` で継続質問を実行できることを確認した。

確認結果:

- `resume <codex-thread-id>` 実行時も、標準出力には `thread.started`、`turn.started`、`item.completed`、`turn.completed` がJSONLとして出力された。
- `thread.started` の `thread_id` は、指定したCodex側の会話継続IDと同じ値だった。
- `--output-schema` は、`resume` より前の `codex exec` オプションとして指定すれば有効だった。
- `--output-last-message` には、通常実行時と同じく最後の `agent_message.text` と同等のJSON文字列が保存された。
- `-C` を `resume` より前に指定することで、継続質問時も `codex/sessions/user-id-xxxxx/id-xxxxx` が作業ディレクトリになった。

resume時の最小例:

```json
{"type":"thread.started","thread_id":"019e00ec-fec8-7612-ac3e-81151b6731c3"}
```

```json
{"type":"item.completed","item":{"type":"agent_message","text":"{\"answers\":[{\"text\":\"はい。resumeでも中間JSONLの継続と最終回答の受け取りを検証できます。\",\"references\":[]}]}"}}
```

設計上は、D-ConciergeのチャットセッションIDとは別に、Codex側の会話継続IDを保存する。新規チャットの初回実行では通常の `codex exec` を使い、2ターン目以降の継続質問では同じ作業ディレクトリを指定して `codex exec resume <codex-thread-id>` を使う。

## 確認したイベント

通常完了時に確認した主なJSONLイベントは次の通りである。

| イベント | 内容 | 画面表示での扱い |
| --- | --- | --- |
| `thread.started` | スレッド開始。`thread_id` を含む。 | 利用者には表示しない。 |
| `turn.started` | 1回の実行開始。 | 定型の中間メッセージへ変換できる。 |
| `item.started` | ツール実行などの開始。 | 生データは表示しない。必要なら定型の中間メッセージへ変換する。 |
| `item.completed` | エージェントメッセージまたはツール実行の完了。 | 種別に応じて扱う。 |
| `turn.completed` | 実行完了。使用量情報を含む。 | 最終回答確定処理のトリガーにする。 |
| `error` | 再接続やAPIエラーなど。 | 利用者向けエラーまたは再接続中表示へ変換する。 |
| `turn.failed` | 実行失敗。 | 最終回答を採用せず、エラー処理へ進める。 |

`item.completed` のうち、`item.type` が `agent_message` のイベントでは、`item.text` にJSON文字列が入った。

通常完了時の最小例:

```json
{"type":"item.completed","item":{"type":"agent_message","text":"{\"answers\":[{\"text\":\"テスト用の短い回答です。\",\"references\":[]}]}"}}
```

ツール実行を伴う場合は、`command_execution` の開始・完了イベントも出力された。

```json
{"type":"item.started","item":{"type":"command_execution","command":"<コマンド>","status":"in_progress"}}
```

```json
{"type":"item.completed","item":{"type":"command_execution","command":"<コマンド>","aggregated_output":"<出力>","exit_code":0,"status":"completed"}}
```

`command_execution` にはコマンド文字列、出力、パスが含まれ得るため、利用者画面へそのまま出さない。

## 最終回答JSONの抽出ルール

採用する抽出ルールは次の通りである。

1. 標準出力JSONLを行単位で読み取る。
2. `item.completed` かつ `item.type` が `agent_message` の `item.text` を未分類メッセージとして一時保持する。
3. `turn.completed` を受信した時点で、保持中の未分類メッセージを最終回答候補としてJSONパースする。
4. パース後、`codex.output_schema` が指すJSON Schemaで固定検証する。
5. `--output-last-message` を併用している場合は、ファイル内容も読み取り、最後の最終回答候補と整合することを確認する。
6. `turn.failed` またはプロセス異常終了の場合、保持済みの最終回答候補は採用しない。

`--output-last-message` には、通常完了時に最後の `agent_message.text` と同じJSON文字列が保存された。

```json
{"answers":[{"text":"テスト用の短い回答です。","references":[]}]}
```

## 中間メッセージの抽出ルール

`--output-schema` 指定時は、途中の `agent_message` も回答スキーマに沿ったJSON文字列になった。ツール実行前に出た途中メッセージも、次のような回答JSON形だった。

```json
{"answers":[{"text":"指定された3項目の有無を確認します。","references":[]}]}
```

追加検証では、プロンプトで途中メッセージの内容を指示すると、`answers[].text` 内の自然文はある程度操作できた。一方で、標準出力JSONL上はプレーンな自然文ではなく、最終回答と同じスキーマ形JSONとして出力された。

採用する中間メッセージ抽出ルールは次の通りである。

1. `item.completed` かつ `item.type` が `agent_message` の `item.text` を受信したら、最新のエージェントメッセージ候補として一時保持する。
2. 次のイベントが到着し、保持中のエージェントメッセージが最終回答ではないことが分かった時点で、中間メッセージ候補として扱う。
3. 中間メッセージ候補が回答スキーマに適合し、表示本文に相当する項目を持つ場合は、その本文だけを抽出して画面表示に使える。
4. `turn.completed` 時点で保持している最後のエージェントメッセージは、最終回答候補として扱い、中間メッセージとしては表示しない。
5. 回答スキーマから安全に表示本文を抽出できない場合は、JSONLイベントと実行段階から生成する定型文を使う。

PDF検索アプリを構成する場合の回答スキーマでは、`answers[].text` を中間メッセージ本文として抽出できる。ただし、`references` は中間メッセージ表示には使わない。

定型文にフォールバックする場合の例は次の通りである。

- `turn.started`: 回答生成を開始しています。
- `item.started` の `command_execution`: 必要な情報を確認しています。
- `item.completed` の `command_execution`: 確認した情報を整理しています。
- 検証用Codex exec開始: 回答と参照元を検証しています。
- 再生成開始: 検証結果をもとに回答を修正しています。

内部コマンド、標準出力、絶対パス、秘密情報、APIキー、環境情報は利用者向け中間メッセージに含めない。

## メッセージ判定アルゴリズム

`agent_message` は、受信した瞬間には中間メッセージか最終回答かを確定しない。バックエンドは未分類メッセージを1件だけ保持する。

状態変数:

- `pending_agent_message`: 中間メッセージか最終回答か未確定の最新 `agent_message`。
- `cancel_requested`: 利用者がキャンセルを要求済みか。
- `terminal_state`: 完了、エラー、タイムアウト、キャンセル済みなどの終端状態。

イベントごとの扱い:

| 受信イベント | `pending_agent_message` の扱い | 補足 |
| --- | --- | --- |
| `item.completed` かつ `item.type == agent_message` | 既存の `pending_agent_message` があれば中間メッセージ候補にし、新しい `agent_message` を保持する。 | 連続して回答候補が出た場合、直前分は最終回答ではないと判断できる。 |
| `item.started` かつ `item.type == command_execution` | `pending_agent_message` があれば中間メッセージ候補にして空にする。 | 後続処理が続くため、保持中メッセージは最終回答ではない。 |
| `item.completed` かつ `item.type == command_execution` | `pending_agent_message` があれば中間メッセージ候補にして空にする。 | コマンド内容と出力は利用者画面へ直接表示しない。 |
| その他の処理継続イベント | `pending_agent_message` があれば中間メッセージ候補にして空にする。 | 処理が続くことを示すイベントであれば、保持中メッセージは最終回答ではない。 |
| `turn.completed` | `pending_agent_message` を最終回答候補にして空にする。 | JSONパースとスキーマ検証に成功した場合だけ最終回答として採用する。 |
| `turn.failed` | `pending_agent_message` を破棄する。 | 受信済みメッセージを最終回答として採用しない。 |
| `type == error` | 原則として `pending_agent_message` は確定しない。 | 再接続中など一時エラーの可能性があるため、終端状態と組み合わせて扱う。 |
| キャンセル要求後のイベント | `pending_agent_message` を破棄し、以後の `agent_message` を最終回答に採用しない。 | キャンセル済み判定はプロセス終了結果と組み合わせる。 |
| プロセス異常終了 | `pending_agent_message` を破棄する。 | `turn.failed` が出ない場合もある。 |

最終回答として採用する条件:

- `turn.completed` を受信している。
- `pending_agent_message` が存在する。
- `pending_agent_message.text` がJSONとしてパースできる。
- パース結果が `codex.output_schema` に適合する。
- キャンセル要求中、タイムアウト、プロセス異常終了ではない。
- `--output-last-message` を併用する場合、ファイル内容と `pending_agent_message.text` が一致または同等である。

中間メッセージとして採用する条件:

- 後続イベントにより、保持中の `agent_message` が最終回答ではないと判断できる。
- `agent_message.text` がJSONとしてパースできる。
- 回答スキーマから表示本文を安全に抽出できる。
- 表示本文に絶対パス、コマンド、標準出力、秘密情報、APIキー、実行環境の詳細が含まれていない。

中間メッセージ候補から表示本文を抽出できない場合、その候補は利用者画面に出さず、処理段階に応じた定型文を表示する。

擬似コード:

```text
pending_agent_message = null

on_agent_message(message):
  if cancel_requested:
    discard(message)
    return
  if pending_agent_message exists:
    emit_intermediate_if_safe(pending_agent_message)
  pending_agent_message = message

on_processing_continues(event):
  if pending_agent_message exists:
    emit_intermediate_if_safe(pending_agent_message)
    pending_agent_message = null
  handle_internal_event(event)

on_turn_completed():
  if pending_agent_message does not exist:
    mark_error("final answer missing")
    return
  final_candidate = pending_agent_message
  pending_agent_message = null
  validate_and_adopt_final_answer(final_candidate)

on_turn_failed_or_process_error():
  pending_agent_message = null
  mark_error()

on_cancel_requested():
  cancel_requested = true
  pending_agent_message = null
```

この方式では、中間メッセージ表示は次のイベント到着まで最大1イベント分遅延する。最終回答を誤って中間メッセージとして表示しないことを優先するため、この遅延を許容する。

## エラー時の扱い

無効なJSON Schemaを指定した場合、標準出力JSONLには `error` と `turn.failed` が出力された。

確認したエラー分類:

```text
invalid_json_schema
```

この場合、最終回答ファイルは作成されず、回答JSONも採用しない。

技術検証では、既存のPDF参照用スキーマに `const` のみで `type` がないプロパティがあり、Codex CLIの `--output-schema` では受理されなかった。`--output-schema` に渡すスキーマは、アプリケーション起動前または設定読込時にCodex execで受理可能な形であることを確認する。

## スキーマ不適合指示時の扱い

利用者指示でスキーマを無視するよう求めた場合でも、`--output-schema` が有効な実行では、最終的にスキーマ適合JSONが出力された。

ただし、これは固定検証を省略できるという意味ではない。D-Concierge側では、最終回答候補を必ずJSONとしてパースし、設定されたJSON Schemaで検証する。

## キャンセル時の扱い

PTY付きでCodex exec実行中に割り込みを入れたところ、プロセスは終了コード1で終了した。割り込み時点では `turn.failed` が出力されず、`--output-last-message` のファイルも作成されなかった。

そのため、キャンセル済み判定はJSONLイベントだけに依存しない。バックエンドは、利用者のキャンセル要求状態、対象プロセスへの終了要求、プロセス終了結果を組み合わせてキャンセル済みを確定する。

キャンセル要求後に受信済みの `agent_message` があっても、最終回答として採用しない。

## 設計判断

- 回答生成のCodex execは、常に `--json` と `--output-schema` を併用する。
- 標準出力JSONLは逐次イベント処理の主経路とする。
- 最終回答JSONは、最後の `agent_message.text` を `turn.completed` 後に採用候補とする。
- `--output-last-message` は、最終メッセージの確認用として併用する。
- 中間メッセージは、最後の `agent_message` と区別できた過去の `agent_message.text` から表示本文を抽出できる場合だけ採用する。
- 表示本文を安全に抽出できない場合は、バックエンドの状態変換で定型文を作る。
- `command_execution` の内容は利用者画面へ直接表示しない。
- `turn.failed`、プロセス異常終了、キャンセル済みでは、受信済みの回答候補を最終回答として採用しない。

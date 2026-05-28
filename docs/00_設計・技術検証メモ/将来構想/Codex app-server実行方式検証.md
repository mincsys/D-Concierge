# Codex app-server実行方式検証

## 目的

本メモは、現在の `codex exec` によるCodex実行方式を、将来 `codex app-server` に変更できるかを検証し、Codex最終出力スキーマと中間メッセージ受信方式を簡素化できるかを整理する。

## 調査日と前提

調査日: 2026-05-28

ローカル環境のCodex CLI:

- `codex-cli 0.133.0`

現行実装では、バックエンドが `codex exec --json --output-schema <schema> -C <workdir>` を起動し、標準出力JSONLを解析する。生成用・検証用のCodex側会話継続IDが存在する場合は `codex exec ... resume <conversation_id> <prompt>` を使う。

現行の `codex/output_json_schema/` は、中間メッセージと最終出力を同じJSON Schema内に定義している。

- 中間メッセージ: `payload.kind = "progress"`
- 最終出力: `payload.kind = "final"`

## 参照情報

- [Codex CLI reference](https://developers.openai.com/codex/cli/reference)
- [Codex App Server](https://developers.openai.com/codex/app-server)
- [Feature Maturity](https://developers.openai.com/codex/feature-maturity)

## ローカル確認結果

実行した主な確認コマンド:

- `codex --version`
- `codex --help`
- `codex exec --help`
- `codex app-server --help`
- `codex app-server generate-json-schema --experimental --out /tmp/dconcierge-codex-app-schema`
- `codex debug app-server send-message-v2 ...`

`codex app-server` には、以下のサブコマンドが存在する。

- `daemon`
- `proxy`
- `generate-ts`
- `generate-json-schema`

`generate-json-schema` により、app-serverプロトコルのJSON Schemaを生成できる。生成されたスキーマでは、`turn/start` の入力に `outputSchema` が存在し、説明上は「このターンの最終assistant messageを制約するJSON Schema」とされている。

`codex debug app-server send-message-v2` で短い指示を送信したところ、概ね以下の流れでJSON-RPCメッセージと通知が流れることを確認した。

1. `initialize`
2. `initialized`
3. `thread/start`
4. `turn/start`
5. `thread/status/changed`
6. `turn/started`
7. `item/started`
8. `item/completed`
9. `turn/completed`

最終回答は `item/completed` の `item.type = "agentMessage"`、`item.text` として受け取れる。中間的なassistant textは `item/agentMessage/delta` または `item/completed` の `agentMessage.text` として扱える。

生成スキーマ上、`agentMessage` には `phase` があり、値として `commentary` と `final_answer` が定義されている。ただしスキーマ説明では、プロバイダが常に一貫して出すとは限らないため、`phase` がない場合を考慮する必要がある。

`turn/start.outputSchema` に簡単なJSON Schemaを指定し、プロンプトで最終回答前に自然文の中間メッセージを出すよう指示したところ、実際には `phase = "commentary"` の `agentMessage` も最終回答と同じJSON Schema形状のテキストになった。

同じプロンプトを `outputSchema` なしで実行した場合は、自然文の中間メッセージと最終JSONが別々の `agentMessage` として流れた。

このため、app-serverに切り替えても、`outputSchema` を指定する限り、Codexが生成する中間assistant textを自然文の進捗メッセージとして安定利用できるとは扱わない。app-serverでは `phase` により中間候補と最終回答候補を区別しやすくなるが、`outputSchema` の影響を受けた中間assistant textが発生し得る。

短いJSON応答だけを返す条件で、処理時間も測定した。モデル応答時間は外部要因で揺らぐため、値は目安として扱う。

| 測定対象 | 測定結果 |
| --- | ---: |
| `codex app-server` 起動、`initialize`、`thread/start`、終了 | 約0.49秒 |
| 起動済みapp-serverで `thread/start` だけを3回 | 1回あたり約0.26秒から0.33秒 |
| `codex exec --json --output-schema` で1ターン完了 | 約4.45秒 |
| app-serverを毎回起動して1ターン完了 | 約4.39秒 |

この測定では、app-serverをチャット実行処理ごとに起動しても、短い1ターン全体の処理時間は `codex exec` と同程度だった。起動固定費は約0.5秒であり、通常のCodex応答時間に比べると小さい。

## 公式ドキュメント上の位置づけ

`codex exec` は、非対話・CI形式の実行に使うStableなコマンドとして位置づけられている。`--json` により状態変化ごとのJSONLイベントを受け取り、`--output-schema` により最終レスポンス形状を指定できる。

`codex app-server` は、VS Code拡張などのrich client向けに、認証、会話履歴、承認、streamed agent eventsを扱うためのインターフェースとして説明されている。通信はJSON-RPC 2.0相当で、stdio、WebSocket、Unix socketを利用できる。

一方で、`codex app-server` はExperimentalであり、OpenAIが変更または削除する可能性がある機能として扱われる。また公式ドキュメントでは、ジョブ自動化やCI用途ではCodex SDKの利用が案内されている。

## `codex app-server` への変更可否

技術的には変更可能である。

ただし、`codex exec` のコマンド文字列を差し替えるだけでは対応できない。`codex app-server` を利用する場合は、バックエンド側にJSON-RPCクライアントを実装し、以下を扱う必要がある。

- app-serverプロセスまたはdaemonの起動と停止。
- `initialize` / `initialized` の接続初期化。
- `thread/start` と `thread/resume` による会話開始・再開。
- `turn/start` による実行開始。
- `item/*`、`turn/*`、`thread/*` 通知の購読と分類。
- `turn/completed` 到達時の最終出力確定。
- `turn/interrupt` によるキャンセル。
- `ErrorNotification`、`TurnError.codexErrorInfo`、JSON-RPCエラーの分類。
- app-serverプロトコル変更への追従。

そのため、設計・実装上は `CodexRunner` の単純改修ではなく、`AppServerCodexRunner` のような別アダプタを追加し、既存の `codex exec` 実装と差し替え可能にする方がよい。

## app-serverのプロセス寿命

app-serverを採用する場合、長寿命プロセスとしてバックエンド起動中に維持する方式と、チャット実行処理ごとに起動して終了する方式が考えられる。

### チャット実行処理ごとに起動する方式

この方式では、生成用Codex実行または検証用Codex実行のたびに `codex app-server --listen stdio://` を起動し、`turn/completed` 到達後に終了する。

利点:

- 現行の `codex exec` に近く、実行単位とプロセス寿命が一致する。
- タイムアウト時は対象app-serverプロセスを終了できる。
- キャンセル時は対象実行処理のapp-serverプロセスだけを停止対象にできる。
- 実行後にapp-server内部状態が残りにくい。
- ユーザ別、チャット別、生成用、検証用の分離を考えやすい。
- 長寿命プロセス監視、接続再確立、購読解除、プロセス再起動、DB状態との整合管理を単純化できる。

懸念:

- 実行ごとに約0.5秒の起動固定費が発生する。
- app-serverのrich client向け機能を継続的に活用する設計にはなりにくい。

### 長寿命プロセスとして維持する方式

この方式では、バックエンド起動時または初回利用時にapp-serverを起動し、複数のチャット実行処理で同じapp-serverプロセスを使う。

利点:

- app-server起動固定費を初回だけにできる。
- 起動済みapp-serverに対する `thread/start` は短時間で完了する。
- 将来的にrich client相当の会話履歴操作や購読管理を直接活用しやすい。

懸念:

- app-serverプロセス監視、異常終了時の再起動、接続再確立が必要になる。
- 同時実行時のthread管理、通知振り分け、購読解除、キャンセル対象の特定が複雑になる。
- ユーザ別または実行単位の分離を設計する必要がある。
- app-server内部状態とDB上のチャット実行状態がずれた場合の復旧方針が必要になる。

### プロセス寿命の推奨

現時点では、app-serverを採用する場合でも、チャット実行処理ごとに起動して終了する方式を優先する。

理由:

- 実測上、起動固定費は約0.5秒であり、通常のCodex応答時間に比べると小さい。
- 長寿命化による設計・実装・障害対応の複雑化が大きい。
- D-Conciergeの現行実行モデルは、実行処理単位でCodexを起動し、キャンセルやタイムアウトも対象実行処理単位で扱う設計である。
- 毎回起動方式であれば、既存の `CodexRunner`、キャンセル、タイムアウト、エラー分類の考え方に寄せやすい。

将来、app-server起動固定費が利用者体験上の問題になる、または同時実行数の増加によりプロセス起動数が問題になる場合は、長寿命プロセス方式を再検討する。

## 中間メッセージ簡素化の可能性

`codex app-server` に切り替える場合でも、中間メッセージを現在のように `payload.kind = "progress"` のJSONとしてCodexに出力させる方式は採用しない。

app-serverでは、assistant textをプロトコル通知として受け取れるため、アプリケーション側では以下のように扱える。

- `item/agentMessage/delta` を逐次表示用のテキスト差分として扱う。
- `item/completed` の `agentMessage.text` をメッセージ単位の本文として扱う。
- `phase = "commentary"` は中間メッセージ候補として扱う。
- `phase = "final_answer"` は最終回答候補として扱う。
- `phase` がない場合は、`turn/completed` 時点の最後の `agentMessage.text` を最終出力候補として扱う。

ただし、`turn/start.outputSchema` を指定した場合、`phase = "commentary"` のassistant textもスキーマ形状になることがある。そのため、D-Conciergeで利用者に表示する中間メッセージは、Codexが生成するassistant textには依存せず、アプリケーション側の固定メッセージまたはプロトコルイベントから生成する。

この場合、`codex/output_json_schema/` は最終出力だけを定義すればよい。最終出力かどうかは、`phase` と `turn/completed` に基づくapp-serverイベント制御で判定する。

## `codex/output_json_schema` の変更方針

スキーマ簡素化を優先し、`payload` envelopeを削除する。

生成用スキーマを、回答本文と参照元だけにする。

```json
{
  "answers": []
}
```

検証用スキーマを、検証結果だけにする。

```json
{
  "valid": true,
  "comment": ""
}
```

利点:

- 最終出力スキーマが最も単純になる。
- Codexへの指示も短くできる。

懸念:

- `parse_generation_final_output`、`parse_validator_final_output`、テスト、プロンプト、設計書の修正が必要になる。
- 最終出力であることはCodex実行境界側のイベント制御で保証する必要がある。

## 推奨方針

直近でスキーマを簡素化する場合は、最終出力スキーマから `payload` envelopeを削除する。

理由:

- 公式ドキュメント上、`--output-schema` は最終レスポンス形状を指定する機能である。
- 中間メッセージを最終出力スキーマに同居させる必要性は低い。
- `payload.kind` による中間メッセージと最終出力の同居をやめることで、Codexへの出力指示を短くできる。
- app-server採用時も、`turn/start.outputSchema` で最終出力だけを制約する形に合わせやすい。

ただし、app-serverで `outputSchema` を指定しても、中間assistant textがスキーマ形状になる可能性は残る。そのため、利用者向けの中間メッセージはCodex出力から取得せず、D-Concierge側で制御する。

`codex app-server` への切り替えは、将来の検証テーマとして扱うのがよい。採用する場合は、まず生成処理1回分だけを対象にしたスパイク実装を行い、毎回起動方式で既存仕様を満たせることを確認する。

## app-server採用時の追加検証観点

- D-Conciergeの生成用JSON Schemaを `turn/start.outputSchema` に渡し、期待どおり最終出力だけを制約できること。
- 検証用JSON Schemaも同様に制約できること。
- `phase = "commentary"` のassistant textがスキーマ形状になった場合でも、最終出力として誤採用しないこと。
- `phase` がない場合でも最終出力を安定して確定できること。
- `thread/resume` が現行の生成用・検証用Codex側会話継続IDの用途を満たすこと。
- キャンセル時に `turn/interrupt` を使い、既存のキャンセル済み状態と矛盾しないこと。
- app-serverプロセス異常終了時の扱いを現行の `CodexProcessFailureError` 相当へ対応づけられること。
- AIサービスプロバイダ側エラーを `ErrorNotification`、`TurnError.codexErrorInfo`、JSON-RPCエラーから分類できること。
- app-server由来の通知が多いため、D-Conciergeで不要な通知を `initialize.params.capabilities.optOutNotificationMethods` で抑制できること。
- Experimental機能の変更に備え、プロトコルスキーマ生成結果をバージョン固定してテストできること。

## 現時点の結論

`codex app-server` への切り替えは可能だが、現時点ではStableな `codex exec` より実装・運用リスクが高い。

中間メッセージスキーマの複雑さを解消する目的であれば、`codex/output_json_schema/` を最終出力専用にし、`payload` envelopeを持たない単純なスキーマへ寄せる方がよい。

app-serverを採用する場合でも、まずはチャット実行処理ごとにapp-serverを起動して終了する方式を基本とする。将来的に、rich client相当の細かいイベント制御、長寿命接続、会話履歴操作、承認制御をD-Concierge側で直接扱いたくなった場合に、長寿命app-server方式を改めて検討する。

# ExecuteChatRunUseCaseクラス設計

## 1. 文書の目的

本書は、`ExecuteChatRunUseCase` クラスの責務、不変条件、公開メソッドを定義することを目的とする。

## 2. 前提

- 本クラスは `クラス一覧.md` で詳細設計対象としたクラスである。
- REST受付後の非同期実行またはバックグラウンド実行から呼び出される。
- 生成用codex execは `CodexGenerationRunnerPort`、検証は `ValidateAnswerUseCase`、DBは `TransactionManagerPort` と `ChatExecutionRepositoryPort`、作業領域解決は `SessionWorkdirResolverPort`、トレースログは `TraceLoggerPort` 経由で利用する。
- 現在時刻取得とID発番は `ClockPort`、`IdGeneratorPort` としてcomposition rootから注入され、本クラス内でruntime具象実装を生成しない。
- `server.timeout_seconds` は実行全体の上限として扱い、個々のcodex execには全体deadlineから算出した残り秒数を渡す。

## 3. 責務

- チャット実行処理を `running`、`validating`、`completed`、`error`、`timed_out` の各状態へ遷移させる。
- `CodexGenerationRunnerPort` で生成用codex execを起動し、JSONL中間メッセージをSSE配信へ渡す。
- 初回生成時と再生成時の生成用Codex promptを組み立て、元のユーザ指示と検証による修正指示をタグ付きブロックで分離する。
- 検証用codex execのJSONL中間メッセージ通知先を `ValidateAnswerUseCase` へ渡し、検証中の中間メッセージもSSE配信へ渡す。
- 生成開始、生成完了、検証開始、検証完了、再生成開始の節目でシステム固定の中間メッセージを保存し、SSE `message` として即時配信する。
- 回答候補を `ValidateAnswerUseCase` へ渡し、検証成功時だけ回答採用へ進める。
- `ValidateAnswerUseCase` から再生成指示を受けた場合、retry回数を処理中カウンタとして進め、`running` と `validating` をSSE `state` で通知しながら生成用codex execを再実行する。
- 検証済み回答ブロック、ブロックごとの参照元、保存済みCodex成果物情報を状態条件付き更新で保存する。保存済みCodex成果物実体は対象チャットのユーザID配下へ保存する。
- 検証済み回答を保存する前に、各回答ブロック内で同一PDF内の重複または隣接する参照ページ範囲を結合し、PDFパスと開始ページ順に整列する。
- 生成用/検証用codex execから返ったCodex側resume用IDを `ChatRuntimeRepositoryPort` へ保存する。
- `running` 遷移時に `execution_deadline_at` を計算して保存し、再生成を含む処理全体で同じdeadlineを使う。
- 生成失敗、Codex側エラー、Codexプロセス異常終了、検証上限超過、参照元PDF読み取り失敗、タイムアウト、設定不備、検証完了後の回答採用失敗を利用者向けエラーとトレースログへ変換する。

## 4. 不変条件

- `cancel_requested` または終端状態の実行処理に対して、回答候補、参照元、Codex成果物を最終結果として保存しない。
- `completed` になる実行処理には検証済み回答が1件存在し、回答は1件以上の回答ブロックを含む。
- `error` または `timed_out` になる実行処理には利用者向けメッセージが存在する。
- 中間メッセージとして保存する本文は、画面表示用に整形・マスク済みである。
- `作業を開始します。` は初回生成前だけ保存・配信し、再生成時は保存・配信しない。
- 検証不合格で再生成可能な場合だけ、次の生成用codex exec起動前に `回答を修正します。` を保存・配信する。
- DBへ保存する参照元pathは共有データソースルートからの相対パスとし、Codex作業領域上の `readonly/` 接頭辞を含めない。
- 再生成は `ExecuteChatRunUseCase` だけが起動し、`ValidateAnswerUseCase` は生成用codex execを起動しない。
- 初回生成時は `<ユーザ指示>` ブロックだけを生成用Codexへ渡す。再生成時は再生成説明文、`<ユーザ指示>` ブロック、`<検証による修正指示>` ブロックをこの順序で生成用Codexへ渡す。
- 全体deadlineを超過した場合、以後の再生成または検証用codex execを起動しない。
- 参照元PDF読み取り失敗は検証段階のシステムエラーとして扱い、生成用codex execの再実行へ戻さない。
- runtime、DB、Codex、ファイル保存、トレースログの副作用は注入されたportだけを通じて利用する。

## 5. 公開メソッド

| メソッド | 役割 | 入力 | 出力 | 事前条件 | 事後条件 |
| --- | --- | --- | --- | --- | --- |
| `execute` | 1件のチャット実行処理を生成から結果確定まで進める | チャットID、チャット実行処理ID、trace_id | 終了状態 | 対象実行処理が `accepted` で保存済みであること<br>対象チャットにユーザIDとセッションIDが保存済みであること<br>必要な設定値が利用できること | `accepted` から `running` への遷移時に `execution_deadline_at` が保存されること<br>成功時は状態が `completed` になり、回答ブロック、各ブロック内でページ範囲を結合済みの参照元、Codex成果物情報が保存されること<br>生成中および検証中のCodex由来中間メッセージが保存され、SSE `message` として配信されること<br>初回生成前に `作業を開始します。`、生成完了後に `作業が完了しました。`、検証開始前に `回答の検証を開始します。`、検証合格後に `回答の検証を完了しました。` がSSE `message` として配信されること<br>再生成指示時はretry回数を増やして `validating` から `running` へ戻し、次の生成用codex exec起動前に `回答を修正します。` とSSE `state` を配信すること<br>通常の検証不合格とユーザキャンセルはトレースログへ保存しないこと<br>最大試行回数まで検証が不合格になった場合は `error` 終端し、最後の検証失敗理由だけをトレースログへ保存すること<br>参照元PDF読み取り失敗時は `PDF読み取り中にエラーが発生しました。` を利用者向けメッセージとして `error` 終端し、検証段階のトレースログへ対象PDF相対パス、例外種別、スタックトレースを保存すること<br>検証完了後の回答採用で予期しない例外が発生した場合は `予期しないエラーが発生しました。開発者にお問い合わせください。` を利用者向けメッセージとして `error` 終端し、実行段階のトレースログへ例外種別とスタックトレースを保存すること<br>タイムアウト時は状態が `timed_out` になり、利用者向けメッセージとトレースログが保存されること<br>キャンセル競合時は先に成立した終端状態を維持すること |

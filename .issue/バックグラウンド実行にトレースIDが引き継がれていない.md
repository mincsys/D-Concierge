# バックグラウンド実行にtrace_idが引き継がれていない

## 内容

`docs/03_内部設計/03_内部IF設計/RunExecutionDispatcherIF.md`、`docs/03_内部設計/04_処理設計/新規チャット開始処理設計.md`、`docs/03_内部設計/04_処理設計/継続指示受付処理設計.md` では、受付APIで生成した `trace_id` を `RunExecutionDispatcher` 経由で `ExecuteChatRunUseCase.execute(chat_id, run_id, trace_id)` へ渡す前提になっている。

一方、現行実装では `StartChatUseCase` と `AppendChatRunUseCase` が `trace_id` を受け取るものの使用せず、`register_accepted_run()` は `run_dispatcher.register(chat_id, run_id)` だけを呼び出す。`InProcessRunExecutionDispatcher` も `execute(chat_id, run_id)` だけを呼び出すため、実行処理のtraceログは受付APIのtrace_idと相関しない。

## 影響

受付API、バックグラウンド実行、Codex実行、検証、回答保存のログを同じtrace_idで追跡できない。障害調査時に、受付直後の処理とバックグラウンド実行の対応をrun_idだけで追う必要がある。

## 設計と実装の評価

設計の方がよい。trace_idは処理横断の相関IDであり、バックグラウンド実行へ渡さないとトレースログIFとログ設計の目的を満たしにくい。

対応は、`RunExecutionDispatcherPort.register(chat_id, run_id, trace_id)` と `ChatRunExecutorPort.execute(chat_id, run_id, trace_id)` に揃え、起動時回復のように受付API由来のtrace_idがない場合は回復処理用に生成したtrace_idを渡すのがよい。

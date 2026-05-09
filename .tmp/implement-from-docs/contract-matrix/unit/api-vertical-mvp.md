# API縦断MVP 単体契約マトリクス

| 契約ID | 対象 | 設計根拠 | 契約 | 状態 |
| --- | --- | --- | --- | --- |
| U-API-001 | ConfigLoader | 設定読込IF、アプリ設定取得処理設計 | `config.yaml` を型付き設定へ変換し、画面公開項目だけを取得できる。 | 単体テスト済み |
| U-API-002 | ConfigLoader | 設定ファイルIF | 必須設定欠落、`server.timeout_seconds <= 0`、型不正、任意設定不正を設定不備として扱う。 | 単体テスト済み |
| U-API-003 | RunStatePolicy | RunStatePolicyクラス設計、機能一覧 | `受付`、`実行中`、`検証中`、`キャンセル要求中` を未完了として判定する。 | 単体テスト済み |
| U-API-004 | RunStatePolicy | キャンセル処理設計 | `受付`、`実行中`、`検証中` だけをキャンセル可能として判定する。 | 単体テスト済み |
| U-API-005 | StartChatUseCase | 新規チャット開始処理設計 | 空白だけの初回指示を入力不正として拒否する。 | 単体テスト済み |
| U-API-006 | StartChatUseCase | 新規チャット開始処理設計 | チャット、run、指示を保存し、`受付` 状態とSSE URLを返し、dispatcherへ登録する。 | 単体テスト済み |
| U-API-007 | AppendChatRunUseCase | 継続指示受付処理設計 | 対象チャットなしを対象なし、未完了runありを競合として扱う。 | 単体テスト済み |
| U-API-008 | CancelChatRunUseCase | キャンセル処理設計 | `受付` runは `キャンセル要求中` 後に `キャンセル済み` へ終端し、Codex終了要求を呼ばない。 | 単体テスト済み |
| U-API-009 | CancelChatRunUseCase | キャンセル処理設計 | 終端済みrunへのキャンセルは競合として扱う。 | 単体テスト済み |
| U-API-010 | PathSecurityService | 参照元PDF取得処理設計、Codex成果物配信処理設計 | 許可ルート外、絶対パス、親ディレクトリ参照、NUL文字、許可外拡張子を拒否する。 | 単体テスト済み |
| U-API-011 | AnswerCandidateParser | AnswerCandidateクラス設計、チャット実行処理設計 | 生成用CodexのJSON回答候補をMarkdown、PDF参照元、`page_start` / `page_end` へ正規化する。 | 単体テスト済み |
| U-API-012 | AnswerCandidateParser | AnswerCandidateクラス設計、回答検証観点 | JSON不正、空回答、本文不正、参照元不正、ページ範囲不正を固定検証エラーとして扱う。 | 単体テスト済み |
| U-API-013 | ExecuteChatRunUseCase | ExecuteChatRunUseCaseクラス設計、チャット実行処理設計 | 生成結果を中間メッセージ、検証済み回答、参照元として保存し、`state`、`message`、`answer` を発行する。 | 単体テスト済み |
| U-API-014 | ExecuteChatRunUseCase | ExecuteChatRunUseCaseクラス設計、回答検証観点 | 固定検証に失敗した回答候補を保存せず、runを `エラー` 終端して `error` を発行する。 | 単体テスト済み |
| U-API-015 | SqlAlchemyChatRepository / InMemoryChatRepository | 物理データ設計、履歴詳細取得処理設計 | 状態、中間メッセージ、回答、参照元、成果物を保存し、履歴詳細と配信メタ情報として再取得できる。 | 単体テスト済み |
| U-API-016 | InProcessRunExecutionDispatcher | RunExecutionDispatcher IF | 受付済みrunをバックグラウンドへ登録し、同一runの多重登録を `already_registered` として扱う。 | 単体テスト済み |
| U-API-017 | InProcessRunExecutionDispatcher | RunExecutionDispatcher IF | バックグラウンド登録失敗を `failed` として返し、登録中状態を残さない。 | 単体テスト済み |
| U-API-018 | RunEventBroker | SSEイベント配信IF | 購読中runへ `state`、`message`、終端イベントを発生順に配信し、終端後は購読を閉じる。 | 単体テスト済み |
| U-API-019 | RunEventBroker | SSEイベント配信IF | 購読者なしのpublishと購読解除後のpublishをエラーにせず、解除済み接続へ配信しない。 | 単体テスト済み |
| U-API-020 | JsonlEventParser | Codex実行IF、JsonlEventParserクラス設計 | `thread.started`、`turn.started`、`item.started`、`item.completed`、`turn.completed`、`turn.failed`、`error`、未知イベントを構造化イベントへ変換する。 | 単体テスト済み |
| U-API-021 | JsonlEventParser | Codex実行IF、JsonlEventParserクラス設計 | `item.completed`、`event_msg`、`response_item` 形式を構造化イベントへ変換し、`agent_message` を未分類の回答候補として返す。`command_execution` のコマンドや出力は利用者向け本文として直接返さない。 | 単体テスト済み |
| U-API-022 | JsonlEventParser | Codex実行IF、JsonlEventParserクラス設計 | JSON構文不正、ルート形式不正、必須項目欠落をJSONL解析失敗として扱う。 | 単体テスト済み |
| U-API-023 | ValidateAnswerUseCase | 回答検証・再生成処理設計、ValidateAnswerUseCaseクラス設計 | 固定検証と参照元検証に合格した回答候補を `採用可能` として返す。 | 単体テスト済み |
| U-API-024 | ValidateAnswerUseCase | 回答検証・再生成処理設計、ValidateAnswerUseCaseクラス設計 | 固定検証または参照元検証に失敗し、再生成上限未満の場合は `再生成指示` を返す。 | 単体テスト済み |
| U-API-025 | ValidateAnswerUseCase | 回答検証・再生成処理設計、エラーメッセージ設計 | 再生成上限到達時は `失敗` としてMSG-005相当の利用者向けメッセージを返す。 | 単体テスト済み |
| U-API-026 | SaveAdoptedArtifactsUseCase | SaveAdoptedArtifactsUseCaseクラス設計、成果物ファイルIF | 回答本文内のMarkdown/HTML `artifacts/` 参照を保存済み成果物URLへ置換し、DB保存用メタ情報を返す。 | 単体テスト済み |
| U-API-027 | SaveAdoptedArtifactsUseCase | SaveAdoptedArtifactsUseCaseクラス設計、成果物ファイルIF | 同一候補参照を1件の成果物IDへ集約し、共有データソース参照や既存API URLを保存対象にしない。 | 単体テスト済み |
| U-API-028 | FileArtifactStore | FileArtifactStoreクラス設計、成果物ファイルIF | セッション内 `artifacts/` 配下の候補ファイルを `codex.saved_artifacts_dir/<run_id>/<artifact_id>.<拡張子>` へコピーし、保存済みファイルを配信用に開く。 | 単体テスト済み |
| U-API-029 | FileArtifactStore | FileArtifactStoreクラス設計、成果物ファイルIF | 絶対パス、親ディレクトリ参照、共有データソース側参照、許可外拡張子、外部実体へのシンボリックリンク、候補ファイルなしを拒否する。 | 単体テスト済み |
| U-API-030 | FileArtifactStore | Codex成果物配信処理設計、成果物ファイルIF | 保存済み成果物メタ情報の保存領域外参照と許可外MIMEタイプを拒否する。 | 単体テスト済み |
| U-API-031 | StartChatUseCase / AppendChatRunUseCase | 新規チャット開始処理設計、継続指示受付処理設計、RunExecutionDispatcher IF | dispatcher登録失敗時は保存済みrunを `エラー` へ更新し、システムエラーとして扱う。 | 単体テスト済み |
| U-API-032 | RecoverUnfinishedRunsUseCase | 起動時実行回復処理設計、RunExecutionDispatcher IF | `受付` runをdispatcherへ再登録し、再登録失敗時は対象runを `エラー` へ更新して他runの回復を継続する。 | 単体テスト済み |
| U-API-033 | RecoverUnfinishedRunsUseCase / ChatRepository | 起動時実行回復処理設計、チャットRepository IF | `実行中` / `検証中` を `エラー`、`キャンセル要求中` を `キャンセル済み` へ整合し、終端済みrunを変更しない。 | 単体テスト済み |
| U-API-034 | CodexRunner | CodexRunnerクラス設計、codex exec IF | `codex exec --json --output-schema --output-last-message -C` を生成用ホーム・作業領域・出力スキーマで起動し、JSONLからCodex側resume IDと最終候補を返す。 | 単体テスト済み |
| U-API-035 | CodexRunner | CodexRunnerクラス設計、codex exec IF | `resume` 利用時も `--json`、`--output-schema`、`--output-last-message`、`-C` を `resume` より前に指定する。 | 単体テスト済み |
| U-API-036 | CodexRunner | CodexRunnerクラス設計、codex exec IF | JSONL最終 `agent_message` と `--output-last-message` ファイル内容が一致しない場合は正常終了として扱わない。 | 単体テスト済み |
| U-API-037 | CodexRunner | CodexRunnerクラス設計、codex execキャンセルIF | 登録済み生存プロセスへの終了要求は `sent`、登録なしは `not_registered` として返す。 | 単体テスト済み |
| U-API-038 | ExecuteChatRunUseCase | チャット実行処理設計、回答検証・再生成処理設計 | 検証結果が `再生成指示` の場合はretry回数を進め、再生成指示を付加して生成へ戻る。 | 単体テスト済み |
| U-API-039 | ExecuteChatRunUseCase | チャット実行処理設計、成果物ファイルIF | 検証済み回答本文のCodex成果物参照を保存済みURLへ置換し、成果物メタ情報を回答と一緒に保存する。 | 単体テスト済み |
| U-API-040 | CodexGenerationRunnerAdapter / CodexReferenceValidator | Codex実行IF、チャットRepository IF | D-Conciergeの `session_id` から用途別作業領域を解決し、生成用/検証用Codex側resume IDを保存する。 | 単体テスト済み |
| U-API-041 | ExecuteChatRunUseCase | チャット実行処理設計、キャンセル処理設計 | Codex失敗は `エラー`、タイムアウトは `タイムアウト`、キャンセル競合は `キャンセル済み` として終端し、未検証回答を採用しない。 | 単体テスト済み |
| U-API-042 | CancelChatRunUseCase | キャンセル処理設計、SSEイベント配信IF | `受付` は同一処理内で `キャンセル済み`、`実行中` / `検証中` は終了要求結果に応じて `キャンセル要求中` 維持または `キャンセル済み` 整合を行う。 | 単体テスト済み |
| U-API-043 | TraceLogWriter | トレースログIF、TraceLogWriterクラス設計 | trace_id、chat_id、run_id、stage、例外分類、タイムアウト、キャンセル、検証失敗理由をJSONLへ追記し、絶対パスや長文を保存しない。 | 単体テスト済み |
| U-API-044 | ExecuteChatRunUseCase / ChatRepository / Codex実行アダプタ | チャット実行処理設計、チャットRepository IF、Codex実行IF | `実行中` 遷移時に `execution_deadline_at` を保存し、生成用/検証用Codexへ全体deadlineから算出した残り秒数を渡す。 | 単体テスト済み |
| U-API-045 | CodexGenerationRunnerAdapter / CodexReferenceValidator | Codex実行IF、設定ファイルIF | 生成用session `readonly/` へ共有データソース、検証用session `readonly/` へ共有データソースと現在の回答候補を提示してからCodexを起動する。 | 単体テスト済み |
| U-API-046 | CodexRunner / CodexGenerationRunnerAdapter / ExecuteChatRunUseCase | Codex実行IF、チャット実行処理設計 | `codex exec` 標準出力JSONLを逐次読み取り、生成用エージェントメッセージが通常本文の場合は本文を保存・SSE配信する。生成結果JSONの場合は最終回答候補として保留し、後続の別 `agent_message` で最終回答ではないと確定した場合だけ `answers[].text` を保存・SSE配信する。安全なecho進捗出力はCodex由来中間メッセージとして保存・SSE配信する。 | 単体テスト済み |
| U-API-047 | ValidateAnswerUseCase / CodexReferenceValidator / ExecuteChatRunUseCase | Codex実行IF、回答検証処理設計、チャット実行処理設計 | 検証用CodexのJSONLイベント通知先を参照元検証へ渡し、検証結果JSONではないエージェントメッセージ本文と安全なecho進捗出力だけを検証完了前に中間メッセージとして保存・SSE配信する。 | 単体テスト済み |
| U-API-048 | ExecuteChatRunUseCase | チャット実行処理設計、SSEイベント配信IF | 初回生成前に `作業を開始します。`、生成完了後に `作業が完了しました。`、検証開始前に `回答の検証を開始します。`、検証合格後に `回答の検証を完了しました。`、再生成前に `回答を修正します。` を保存・SSE配信する。`作業を開始します。` は同一run内で1回だけ配信する。 | 単体テスト済み |
| U-API-049 | CodexGenerationRunnerAdapter / CodexReferenceValidator | Codex実行IF | 最終回答の生成結果JSONは中間メッセージとして通知しない。最終回答ではないと確定した生成結果JSONは `answers[].text` だけを通知し、検証結果JSONは中間メッセージとして通知しない。 | 単体テスト済み |
| U-API-050 | CodexRunner / JsonlEventParser / CodexIntermediateMessageStreamer | Codex実行IF、JsonlEventParserクラス設計、CodexRunnerクラス設計 | `event_msg.task_complete.last_agent_message` を最終候補として照合し、`response_item.function_call` と `response_item.function_call_output` を `call_id` で対応付けて安全なecho進捗だけを中間メッセージへ変換する。 | 単体テスト済み |
| U-API-051 | CodexReferenceValidator / ExecuteChatRunUseCase | 回答検証・再生成処理設計、エラーメッセージ設計、トレースログIF | 参照元PDFが存在するのに読み取れない場合は再生成指示にせず、runを `エラー` 終端して `PDF読み取り中にエラーが発生しました。` を配信し、検証段階のトレースログへ対象PDF相対パスと例外要約を保存する。 | 単体テスト済み |

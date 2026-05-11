# バックエンド層境界を越えたimportが残っている

## 現行設計

`docs/03_内部設計/01_アーキテクチャ設計/アーキテクチャ設計.md` では、バックエンドを `presentation`、`application`、`domain`、`infrastructure`、`shared` に分け、依存方向を次のように整理している。

- `presentation` は HTTP/SSE の入出力を扱い、業務判断は `application` へ委譲する。
- `application` はユースケースとトランザクション境界を扱い、外部副作用は `application/ports` を介して利用する。
- `domain` はDB、Codex、ファイル、時刻、ID、ログなどの副作用へ依存しない。
- `infrastructure` は `application/ports` の実装として外部副作用を扱う。
- `app` と `main` は composition root として各層を組み立てる。

## 現行実装との差分

`src/backend` の production code をASTで確認したところ、composition root を除き、次の層越え import が残っている。

- `src/backend/presentation/rest/router.py`
  - `backend.domain.execution.run_state`
  - `backend.domain.references.source_type`
  - `backend.infrastructure.trace_log.trace_log_writer`
- `src/backend/application/execution/execute_chat_run.py`
  - `backend.infrastructure.runtime.system_clock`
  - `backend.infrastructure.runtime.uuid_generator`
- `src/backend/application/artifacts/save_adopted_artifacts.py`
  - `backend.infrastructure.runtime.uuid_generator`
- `src/backend/infrastructure/codex/generation_runner.py`
  - `backend.application.transactions`
- `src/backend/infrastructure/codex/reference_validator.py`
  - `backend.application.transactions`

## 影響

- `presentation` が `domain` のEnumと `infrastructure` の具象 `TraceLogWriter` を直接知っている。
- `application` が `ClockPort` / `IdGeneratorPort` を受け取れる設計になっている一方で、未指定時に `SystemClock` / `UuidGenerator` という infrastructure 具象を生成している。
- `infrastructure` が `application/ports` ではなく `application.transactions.NoopTransactionManager` に依存している。

これにより、設計上の依存方向が曖昧になり、層単位の差し替え、単体テスト、責務分離が弱くなる。

## 判断

設計の方がよい。

ただし、`app/factory.py` と `backend.main` は composition root なので、各層の具象実装を import して組み立てることは許容する。

## 対応案

- `presentation/rest/router.py` は `TraceLogWriter` 具象ではなく、`TraceLoggerPort` などの抽象へ依存する。
- `presentation/rest/router.py` が `RunState` / `SourceType` を直接 import しなくてよいように、API/SSE出力直前で必要な外部文字列へ変換済みのDTOを `application` 側から返すか、presentation専用の変換境界を明確化する。
- `ExecuteChatRunUseCase` と `SaveAdoptedArtifactsUseCase` は `SystemClock` / `UuidGenerator` を自前生成せず、composition root から必ず `ClockPort` / `IdGeneratorPort` 実装を注入する。
- `generation_runner.py` と `reference_validator.py` は `NoopTransactionManager` のデフォルト生成をやめ、`TransactionManagerPort` を必須注入する。テストでno-opが必要な場合は `tests/support` 側へ置く。
- `application/ports` への依存、`infrastructure` から `domain` / `shared` への依存、composition root から各層への依存は現行設計上は許容する。


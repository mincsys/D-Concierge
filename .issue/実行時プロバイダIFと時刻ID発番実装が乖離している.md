# RuntimeProvider IFと時刻・ID発番実装が乖離している

## 内容

`docs/03_内部設計/03_内部IF設計/RuntimeProviderIF.md` と `docs/03_内部設計/06_共通設計/共通設計.md` では、現在時刻取得とID発番を `ClockPort`、`IdGeneratorPort`、`SystemClock`、`UuidGenerator` で抽象化し、application層が `datetime.now()` や `uuid4()` を直接呼ばない前提になっている。

一方、現行実装では該当portや実装クラスは存在せず、次のように直接呼び出している。

- `src/backend/infrastructure/database/repositories/sqlalchemy_chat_repository.py` が `datetime.now(UTC)` と `uuid4()` を直接使用する。
- `src/backend/application/execution/execute_chat_run.py` が既定clockとして `datetime.now(UTC)` を使い、参照元IDに `uuid4()` を使う。
- `src/backend/app/factory.py` がtrace_id生成に `uuid4()` を直接使用する。

## 影響

設計書上は時刻・ID発番を差し替え可能な副作用境界として扱うが、実装ではRepositoryやFactoryに散っているため、固定ID・固定時刻を使った結合テストやログ相関の再現性が設計どおりにならない。

## 設計と実装の評価

設計の方がよい。IDと時刻はテスト再現性、trace_id相関、DB保存時刻の一貫性に関わるため、境界として明示しておく価値がある。

ただし、全IDを一気に値オブジェクト化すると修正範囲が大きい。第3案として、まず `ClockPort` とUUID生成portだけを `application/ports/runtime` に追加し、Repository、Factory、実行UseCaseへ注入する。`ChatId` などの値オブジェクト化は別段階で検討する。

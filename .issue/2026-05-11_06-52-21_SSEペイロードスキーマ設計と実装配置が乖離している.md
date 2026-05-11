# SSEペイロードスキーマ設計と実装配置が乖離している

## 内容

`docs/03_内部設計/02_クラス・モジュール設計/01_バックエンド/クラス一覧.md` では、SSE `state` / `message` / `answer` / `error` / `canceled` のpayloadを `src/backend/presentation/schemas/api.py` のPydanticスキーマとして定義する前提になっている。

一方、現行実装では `src/backend/presentation/rest/router.py` 内の `TypedDict` として `StateEventPayload`、`MessageEventPayload`、`AnswerEventPayload`、`EndEventPayload` が定義されており、Pydanticスキーマは存在しない。

## 影響

SSE wire形式の定義場所と型の種類が設計書と実装で一致していない。REST API応答はPydanticスキーマ、SSE payloadはTypedDictという実装上の切り分けは成立しているが、設計書を見た実装者が存在しない `SseStatePayloadSchema` などを前提に修正する可能性がある。

## 設計と実装の評価

第3案がよい。REST APIのrequest/responseはPydanticスキーマで定義し、SSE payloadは内部生成関数の戻り値としてTypedDictで定義する方が現行実装には合っている。ただし、SSE payloadの契約は内部IF設計上重要なため、`presentation/rest/router.py` に閉じ込めるのではなく、専用モジュールへ分離する案も検討余地がある。

対応は、SSE payloadをPydantic化するか、設計書をTypedDictベースの実装へ合わせるかを決めてから行う。

# SessionTokenProvider IF

## 1. 文書の目的

本書は、`application/account` と `infrastructure/security` の間で、`application/ports/security/interface.py` を通じて利用するログインセッショントークンIFの契約を定義することを目的とする。

## 2. 前提

- 呼出方式: PythonのProtocol相当のメソッド呼出。
- 呼出主体: `AuthenticateSessionUseCase`、`RegisterAccountUseCase`、`LoginUseCase`、`LogoutUseCase`。
- 呼出先: `SessionTokenProviderPort`。具象実装は `SecretsSessionTokenProvider` とする。
- Cookieへ設定するトークン生値は推測困難なランダム文字列とする。
- DBにはトークン生値を保存せず、照合用ハッシュだけを保存する。

## 3. IF概要

| 項目 | 内容 |
| --- | --- |
| IF名 | SessionTokenProvider IF |
| 呼出元 | `src/backend/application/account` |
| 呼出先 | `src/backend/application/ports/security/interface.py`。具象実装は `src/backend/infrastructure/security/SecretsSessionTokenProvider` |
| 目的 | ログインセッショントークンの発行と照合用ハッシュ生成をapplication層から抽象化する。 |
| 冪等性 | トークン発行は非冪等。照合用ハッシュ生成は同一トークンに対して同じ値を返す。 |

## 4. 事前条件 / 事後条件 / 不変条件

### 4.1. 事前条件

- 呼出元はCookieから取得したトークン文字列を本IFへ渡す。
- トークン発行時は保存先ユーザと有効期限がユースケース側で確定している。

### 4.2. 事後条件

- `issue_token` はCookieへ設定できるトークン生値を返す。
- `hash_token` はDB検索と保存に使う照合用ハッシュを返す。

### 4.3. 不変条件

- トークン生値はDB、トレースログ、利用者向けメッセージへ出さない。
- Cookie値の検証は生値同士の比較ではなく、照合用ハッシュによる検索で行う。
- セッションの有効期限計算はClock portを使うユースケース側で行う。

## 5. 入出力とデータ項目

| メソッド | 役割 | 主な入力 | 主な出力 |
| --- | --- | --- | --- |
| `issue_token` | Cookieへ設定するログインセッショントークンを発行する | なし | トークン生値 |
| `hash_token` | トークン生値からDB照合用ハッシュを生成する | トークン生値 | token_hash |

## 6. 例外処理

| 条件 | 扱い |
| --- | --- |
| トークン発行失敗 | `ErrorType.SYSTEM` かつトレース対象の `AppError` へ変換する |
| 空トークン | 未ログインとして扱い、通常はトレースログへ記録しない |

# PasswordHasher IF

## 1. 文書の目的

本書は、`application/account` と `infrastructure/security` の間で、`application/ports/security/interface.py` を通じて利用するパスワードハッシュIFの契約を定義することを目的とする。

## 2. 前提

- 呼出方式: PythonのProtocol相当のメソッド呼出。
- 呼出主体: `RegisterAccountUseCase`、`LoginUseCase`、`ChangePasswordUseCase`。
- 呼出先: `PasswordHasherPort`。具象実装は `PasslibPasswordHasher` とする。
- 具象実装はpasslibとbcryptを使用する。

## 3. IF概要

| 項目 | 内容 |
| --- | --- |
| IF名 | PasswordHasher IF |
| 呼出元 | `src/backend/application/account` |
| 呼出先 | `src/backend/application/ports/security/interface.py`。具象実装は `src/backend/infrastructure/security/PasslibPasswordHasher` |
| 目的 | パスワード生値のハッシュ化と、入力パスワードの検証をapplication層から抽象化する。 |
| 冪等性 | 同一パスワードのハッシュ化結果はソルトにより同一とは限らない。検証は同一入力に対して同じ真偽値を返す。 |

## 4. 事前条件 / 事後条件 / 不変条件

### 4.1. 事前条件

- 呼出元はパスワード入力の基本制約を検証済みである。
- 保存済みハッシュは本IFが過去に生成した形式である。

### 4.2. 事後条件

- `hash_password` はDB保存可能なハッシュ文字列を返す。
- `verify_password` は入力パスワードと保存済みハッシュの一致結果だけを返す。

### 4.3. 不変条件

- パスワード生値をログ、例外メッセージ、DTOへ出さない。
- application層はpasslibやbcryptの具象APIに直接依存しない。

## 5. 入出力とデータ項目

| メソッド | 役割 | 主な入力 | 主な出力 |
| --- | --- | --- | --- |
| `hash_password` | パスワード生値から保存用ハッシュを生成する | パスワード生値 | パスワードハッシュ |
| `verify_password` | 入力パスワードと保存済みハッシュを検証する | パスワード生値、保存済みハッシュ | 一致結果 |

## 6. 例外処理

| 条件 | 扱い |
| --- | --- |
| ハッシュ生成失敗 | `ErrorType.SYSTEM` かつトレース対象の `AppError` へ変換する |
| 保存済みハッシュ形式不正 | パスワード不一致ではなくデータ不整合として `ErrorType.SYSTEM` のトレース対象にする |

# codex exec実行環境とセッション管理

## 目的

本メモは、codex execのホームディレクトリ、作業ディレクトリ、セッション管理、生成物保存、パス検証の詳細を整理する。

D-Conciergeでは、利用者ごと、かつチャットセッションごとにcodex execの作業ディレクトリを分離する。

利用者が新しいチャットを開始した場合は新しい作業ディレクトリを作成し、過去チャットを継続する場合は既存の作業ディレクトリをそのまま利用する。これにより、codex execがセッション内で作成した中間ファイル、調査メモ、生成物を同じ文脈として扱えるようにする。

MVPではログインを必須にしないが、DB上のローカル利用者IDを使って利用者別ディレクトリを分ける。将来ログインユーザへ移行する場合も、同じディレクトリ階層を維持する。

## 設定項目

codex execのホームディレクトリ、セッションベースディレクトリ、共有データソース配置は、アプリケーション設定で指定する。

設定項目と役割は次の通りである。

- `codex.home`: 生成用codex execが読み込む `AGENTS.md`、Skills、Codex設定の配置先。
- `codex.workdir`: 生成用セッションベースディレクトリ。
- `codex.output_schema`: 生成用codex execの出力スキーマ。
- `codex.saved_artifacts_dir`: 生成用codex execのセッション内 `artifacts/` からコピーした保存済みCodex成果物本体の保存領域。
- `datasource.dir`: 共有データソースのベースディレクトリ。
- `validator.max_retries`: 検証失敗後に生成用codex execへ修正を依頼する最大回数。
- `validator.codex.home`: 検証用codex execが読み込む `AGENTS.md`、Skills、Codex設定の配置先。
- `validator.codex.workdir`: 検証用セッションベースディレクトリ。
- `validator.codex.output_schema`: 検証用codex execの出力スキーマ。

生成用・検証用codex execの用途別の振る舞いは、それぞれの `home` 配下にある `AGENTS.md` とSkillsに従って制御する。

設定値が相対パスの場合は、アプリケーション実行基準ディレクトリからの相対パスとして扱う。Windows/Linuxの両方で動作するよう、パスの結合と正規化はOSごとの標準的なパス処理に委ねる。

## ディレクトリ構成

共有データソース、生成用codex exec、検証用codex execのディレクトリは、設定値により決まる。PDF検索アプリを構成する場合の設定例では、`datasource.dir` に `codex/readonly` を指定し、生成用codex execと検証用codex execのセッションディレクトリを分離する。

Linuxでは、セッションディレクトリから共有データソースへの参照にシンボリックリンクを使える。Windowsでは、シンボリックリンク作成に権限やDeveloper Modeの制約があるため、ジャンクション、コピーしない共有参照、または設定値から共有データソースを直接解決する方式を後続設計で選択できるようにする。いずれの方式でも、共有データソースはセッションごとに複製しない。

```text
codex/
  readonly/
    raw/
      pdf/
      meta/
    html/
  sessions/
    <user-id>/
      <session-id>/
        readonly -> ../../../readonly
        tmp/
        artifacts/
  sessions_validator/
    <user-id>/
      <session-id>/
        readonly -> ../../../readonly
        tmp/
```

生成用は `codex.workdir/<user-id>/<session-id>/` 全体を永続化対象とする。セッションを再開する場合は、同じ `<user-id>/<session-id>/` をワーキングディレクトリとしてcodex execを起動する。PDF検索アプリを構成する場合の設定例では、生成用セッションディレクトリは `codex/sessions/<user-id>/<session-id>/` になる。

検証用は `validator.codex.workdir/<user-id>/<session-id>/` を作業ディレクトリとする。検証用セッションは最小構成とし、生成物保存用の `artifacts/` は作成しない。PDF検索アプリを構成する場合の設定例では、検証用セッションディレクトリは `codex/sessions_validator/<user-id>/<session-id>/` になる。

## codex exec の起動

codex execは、設定されたホームディレクトリを `CODEX_HOME` に指定し、対象セッションのディレクトリを `-C` に指定して起動する。

生成用codex execでは、`CODEX_HOME` に `codex.home`、`-C` に `codex.workdir/<user-id>/<session-id>` を指定する。

PDF検索アプリを構成する場合の設定例:

```bash
CODEX_HOME=codex/.codex \
codex exec --json --output-schema codex/output_json_schema/pdf-reference-schema.json \
  --output-last-message codex/sessions/<user-id>/<session-id>/tmp/last-message.json \
  -C codex/sessions/<user-id>/<session-id> \
  "<利用者のユーザ指示>"
```

継続指示では、初回実行時のJSONLに含まれる `thread.started` の `thread_id` を生成用Codex側の会話継続IDとして保存しておき、同じ生成用作業ディレクトリを指定して `resume` する。

PDF検索アプリを構成する場合の継続指示の設定例:

```bash
CODEX_HOME=codex/.codex \
codex exec --json --output-schema codex/output_json_schema/pdf-reference-schema.json \
  --output-last-message codex/sessions/<user-id>/<session-id>/tmp/last-message.json \
  -C codex/sessions/<user-id>/<session-id> \
  resume <codex-thread-id> \
  "<利用者の継続指示>"
```

`resume` と `--output-schema` を併用する場合、`--json`、`--output-schema`、`--output-last-message`、`-C` は `resume` より前の `codex exec` オプションとして指定する。`resume` の後ろには、生成用Codex側の会話継続IDと継続指示を渡す。

検証用codex execでは、`CODEX_HOME` に `validator.codex.home`、`-C` に `validator.codex.workdir/<user-id>/<session-id>` を指定する。

PDF検索アプリを構成する場合の設定例:

```bash
CODEX_HOME=codex/.codex_validator \
codex exec --json --output-schema codex/output_json_schema/validator_schema.json \
  -C codex/sessions_validator/<user-id>/<session-id> \
  "<参照元検証依頼>"
```

同一チャットの初回参照元検証では通常の `codex exec` を使い、JSONLに含まれる `thread.started` の `thread_id` を検証用Codex側の会話継続IDとして保存する。2回目以降の参照元検証では、同じ検証用作業ディレクトリを指定して `resume` する。

PDF検索アプリを構成する場合の継続検証の設定例:

```bash
CODEX_HOME=codex/.codex_validator \
codex exec --json --output-schema codex/output_json_schema/validator_schema.json \
  -C codex/sessions_validator/<user-id>/<session-id> \
  resume <validator-codex-thread-id> \
  "<参照元検証依頼>"
```

生成用・検証用とも、`--json`、`--output-schema`、`-C` は `resume` より前の `codex exec` オプションとして指定する。

`CODEX_HOME` は、codex execが読み込む `AGENTS.md`、Skills、Codex設定を含む `.codex` ディレクトリを指す。PDF検索アプリを構成する場合の設定例では、生成用に `CODEX_HOME=codex/.codex`、検証用に `CODEX_HOME=codex/.codex_validator` を使う。

`-C` は、codex execの作業ディレクトリを指す。D-Conciergeでは、DB上の利用者IDとセッションIDを組み合わせたディレクトリを指定する。

`resume` に渡すIDは、codex execが返す会話継続IDである。生成用Codex側の会話継続IDと検証用Codex側の会話継続IDは別々に管理し、D-ConciergeのチャットセッションIDとは別の値としてチャット履歴に紐づけて保存する。

生成用codex execからは、セッションディレクトリ直下に次のパスが見える。

```text
./readonly/
./tmp/
./artifacts/
```

検証用codex execからは、セッションディレクトリ直下に次のパスが見える。

```text
./readonly/
./tmp/
```

`readonly/` は共有データソースへの参照である。Linuxの設定例ではシンボリックリンクとして表現するが、Windowsではジャンクションまたは設定値による共有参照でもよい。PDF、HTML化済み文書、メタデータなど、セッション間で共有する読み取り用データを配置する。

`tmp/` はCodexの中間作業、調査メモ、生成途中ファイルなどを保持する領域である。セッション再開時にもCodexが前回の作業状態を参照できるよう、`<user-id>/<session-id>/` と一緒に永続化する。

`artifacts/` は生成用codex execが生成した画像、HTML、CSV、その他の出力ファイルを置く領域である。回答Markdownから参照される生成物は、まずこの領域に出力される。

## JSONLと最終回答の受信

生成用codex execは、`--json` と `--output-schema` を併用して起動する。`--output-schema` を指定しないパターンは、D-Conciergeの回答生成経路では使わない。

`--json` は、標準出力へJSONLイベントを逐次出すために使う。バックエンドはこの標準出力を行単位で読み取り、実行開始、ツール実行、エラー、完了などのイベントを処理する。

`--output-schema` は、最終回答を設定された回答JSON Schemaへ寄せるために使う。技術検証では、最終回答JSONは `item.completed` の `agent_message.text` に文字列として出力された。

`--output-last-message` は、最後のエージェントメッセージをファイルとして残すために併用できる。標準出力JSONLの読み取りを主経路としつつ、最終回答の取りこぼし確認やプロセス終了後の再読込に使う。

採用する使い分けは次の通りである。

- 標準出力JSONL: 実行状態、エラー、ツール実行、最後の `agent_message` を逐次受け取る。
- `--output-last-message`: 正常完了時の最後のメッセージをファイルから確認する。
- 回答JSONの固定検証: JSONLまたは `--output-last-message` から得た最終回答候補に対して必ず実施する。

`--output-schema` に渡すJSON Schemaは、Codex CLIが内部で利用する応答形式として受理される必要がある。技術検証では、`const` を使うプロパティにも `type` が必要だった。アプリケーション設定で指定するスキーマは、事前にcodex exec起動時の受理条件を満たすことを確認する。

## セッションの扱い

新規チャットでは、DB上の利用者ID配下に新しい `<session-id>/` を作成する。他利用者、他セッションの `tmp/` や `artifacts/` は参照しない。

過去チャットを継続する場合は、既存の `codex.workdir/<user-id>/<session-id>/` をそのまま利用し、初回実行時に保存した生成用Codex側の会話継続IDを使って `codex exec resume` で起動する。同じ作業ディレクトリを使うことで、codex execは前回までの `tmp/` や `artifacts/` を参照できる。

検証用セッションは、生成用セッションと同じ `<user-id>` と `<session-id>` を使って `validator.codex.workdir/<user-id>/<session-id>/` に作成する。

検証用セッションも同じチャット内で継続利用し、初回参照元検証時に保存した検証用Codex側の会話継続IDを使って2回目以降の参照元検証を `codex exec resume` で起動する。生成用作業領域と検証用作業領域は同じ `<user-id>/<session-id>` で一対一に対応するが、会話継続IDは生成用と検証用で別々に保持する。

`readonly/` は共有データソースなので、セッションごとに複製しない。PDF検索アプリを構成する場合のLinux向け設定例では、セッションディレクトリ作成時に `../../../readonly` へのシンボリックリンクとして配置する。Windowsでは、同等の参照関係をOS制約に合わせて実現する。

## Codex成果物の保存と表示

履歴表示は、DBに保存した回答本文、生成用codex execが作成したCodex成果物のメタ情報、保存済みCodex成果物領域の本体ファイルを使って行う。

`artifacts/` 内のファイルは、セッション継続時にcodex execが後から書き換える可能性がある。そのため、画面表示や履歴表示では `artifacts/` 内のファイルを直接参照しない。

バックエンドは回答受領時に、回答Markdownや回答JSONから参照される `artifacts/` 内のファイルを検証し、`codex.saved_artifacts_dir` 配下へコピーする。DBには、Codex成果物ID、チャット実行処理ID、MIMEタイプ、保存先参照、作成日時などのメタ情報だけを保存する。フロントエンドに表示する画像、HTML、CSVなどの回答内Codex成果物は、保存済みCodex成果物領域の本体ファイルから配信する。

回答Markdown内に含まれるセッション内 `artifacts/` への内部パスは、保存済みCodex成果物へコピーした後に `/api/artifacts/{artifact_id}` へ置換する。DBには置換後のMarkdownを回答本文として保存する。

この扱いにより、codex execがセッションディレクトリ内の生成物を更新しても、過去のチャット履歴表示はDBと保存済みCodex成果物領域に保存された時点の内容を維持できる。

## パス検証

セッションディレクトリには共有データソースへの参照が含まれるため、パス検証は実体パスの解決結果を基準に行う。

検証方針は次の通りである。

- `readonly/` の実体は許可済み共有データソース配下に限定する。
- `tmp/` と `artifacts/` は対象セッション配下から出ていないことを検証する。
- `..` や絶対パスによるディレクトリトラバーサルを拒否する。
- Windowsではドライブ文字、大文字小文字、区切り文字、UNCパスを正規化したうえで許可範囲を判定する。
- Linuxではシンボリックリンク解決後の実体パスを基準に許可範囲を判定する。
- `readonly/` 配下は生成物取り込み対象にしない。
- `artifacts/` から保存済みCodex成果物領域へコピーした後は、履歴表示時にセッションディレクトリ内の同名ファイルを参照しない。

## 後続設計で決めること

次の項目は、内部設計または実装設計で具体化する。

- `<user-id>/<session-id>/` 全体のサイズ上限
- セッションディレクトリの保存期間
- 古いセッションディレクトリのクリーンアップ方針
- 保存済みCodex成果物のファイル命名規則
- Codex成果物のMIMEタイプと拡張子の許可リスト
- 保存済みCodex成果物領域の容量上限とクリーンアップ方針

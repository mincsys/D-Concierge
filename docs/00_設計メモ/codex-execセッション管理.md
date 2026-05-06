# Codex セッション管理

## 目的

D-Conciergeでは、利用者ごと、かつチャットセッションごとにCodex execの作業ディレクトリを分離する。

利用者が新しいチャットを開始した場合は新しい作業ディレクトリを作成し、過去チャットを継続する場合は既存の作業ディレクトリをそのまま利用する。これにより、Codex execがセッション内で作成した中間ファイル、調査メモ、生成物を同じ文脈として扱えるようにする。

MVPではログインを必須にしないが、DB上のローカル利用者IDを使って利用者別ディレクトリを分ける。将来ログインユーザへ移行する場合も、同じディレクトリ階層を維持する。

## 設定項目

Codex execのホームディレクトリ、セッションベースディレクトリ、共有データソース配置は、アプリケーション設定で指定する。

設定項目と役割は次の通りである。

- `codex.home`: 生成用Codex execが読み込む `AGENTS.md`、Skills、Codex設定の配置先。
- `codex.workdir`: 生成用セッションベースディレクトリ。
- `codex.output_schema`: 生成用Codex execの出力スキーマ。
- `validator.max_retries`: 検証失敗後に生成側Codex execへ修正を依頼する最大回数。
- `validator.codex.home`: 検証用Codex execが読み込む `AGENTS.md`、Skills、Codex設定の配置先。
- `validator.codex.workdir`: 検証用セッションベースディレクトリ。

生成用・検証用Codex execの用途別の振る舞いは、それぞれの `home` 配下にある `AGENTS.md` とSkillsに従って制御する。

設定値が相対パスの場合は、アプリケーション実行基準ディレクトリからの相対パスとして扱う。

## ディレクトリ構成

共有データソース、生成用Codex exec、検証用Codex execのディレクトリは、設定値により決まる。PDF検索アプリを構成する場合の設定例では、共有データソースを `codex/readonly` に配置し、生成用Codex execと検証用Codex execのセッションディレクトリを分離する。

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

生成用は `codex.workdir/<user-id>/<session-id>/` 全体を永続化対象とする。セッションを再開する場合は、同じ `<user-id>/<session-id>/` をワーキングディレクトリとしてCodex execを起動する。PDF検索アプリを構成する場合の設定例では、生成用セッションディレクトリは `codex/sessions/<user-id>/<session-id>/` になる。

検証用は `validator.codex.workdir/<user-id>/<session-id>/` を作業ディレクトリとする。検証用セッションは最小構成とし、生成物保存用の `artifacts/` は作成しない。PDF検索アプリを構成する場合の設定例では、検証用セッションディレクトリは `codex/sessions_validator/<user-id>/<session-id>/` になる。

## Codex exec の起動

Codex execは、設定されたホームディレクトリを `CODEX_HOME` に指定し、対象セッションのディレクトリを `-C` に指定して起動する。

生成用Codex execでは、`CODEX_HOME` に `codex.home`、`-C` に `codex.workdir/<user-id>/<session-id>` を指定する。

PDF検索アプリを構成する場合の設定例:

```bash
CODEX_HOME=codex/.codex \
codex exec --json \
  --output-schema codex/output_json_schema/pdf-reference-schema.json \
  -C codex/sessions/<user-id>/<session-id> \
  "<利用者の質問>"
```

検証用Codex execでは、`CODEX_HOME` に `validator.codex.home`、`-C` に `validator.codex.workdir/<user-id>/<session-id>` を指定する。

PDF検索アプリを構成する場合の設定例:

```bash
CODEX_HOME=codex/.codex_validator \
codex exec --json \
  -C codex/sessions_validator/<user-id>/<session-id> \
  "<参照元検証依頼>"
```

`CODEX_HOME` は、Codex execが読み込む `AGENTS.md`、Skills、Codex設定を含む `.codex` ディレクトリを指す。PDF検索アプリを構成する場合の設定例では、生成用に `CODEX_HOME=codex/.codex`、検証用に `CODEX_HOME=codex/.codex_validator` を使う。

`-C` は、Codex execの作業ディレクトリを指す。D-Conciergeでは、DB上の利用者IDとセッションIDを組み合わせたディレクトリを指定する。

生成用Codex execからは、セッションディレクトリ直下に次のパスが見える。

```text
./readonly/
./tmp/
./artifacts/
```

検証用Codex execからは、セッションディレクトリ直下に次のパスが見える。

```text
./readonly/
./tmp/
```

`readonly/` は共有データソースへのシンボリックリンクである。PDF、HTML化済み文書、メタデータなど、セッション間で共有する読み取り用データを配置する。

`tmp/` はCodexの中間作業、調査メモ、生成途中ファイルなどを保持する領域である。セッション再開時にもCodexが前回の作業状態を参照できるよう、`<user-id>/<session-id>/` と一緒に永続化する。

`artifacts/` は生成用Codex execが生成した画像、HTML、CSV、その他の出力ファイルを置く領域である。回答Markdownから参照される生成物は、まずこの領域に出力される。

## セッションの扱い

新規チャットでは、DB上の利用者ID配下に新しい `<session-id>/` を作成する。他利用者、他セッションの `tmp/` や `artifacts/` は参照しない。

過去チャットを継続する場合は、既存の `codex.workdir/<user-id>/<session-id>/` をそのまま利用する。同じ作業ディレクトリを使うことで、Codex execは前回までの `tmp/` や `artifacts/` を参照できる。

検証用セッションは、生成用セッションと同じ `<user-id>` と `<session-id>` を使って `validator.codex.workdir/<user-id>/<session-id>/` に作成する。

`readonly/` は共有データソースなので、セッションごとに複製しない。PDF検索アプリを構成する場合の設定例では、セッションディレクトリ作成時に `../../../readonly` へのシンボリックリンクとして配置する。

## artifact の保存と表示

履歴表示は、DBに保存したメッセージとDBに保存したartifactを使って行う。

`artifacts/` 内のファイルは、セッション継続時にCodex execが後から書き換える可能性がある。そのため、画面表示や履歴表示では `artifacts/` 内のファイルを直接参照しない。

バックエンドは回答受領時に、回答Markdownや回答JSONから参照される `artifacts/` 内のファイルを検証し、DBへ取り込む。フロントエンドに表示する画像、HTML、CSVなどのartifactは、DB保存済みartifactから配信する。

この扱いにより、Codex execがセッションディレクトリ内の生成物を更新しても、過去のチャット履歴表示はDBに保存された時点の内容を維持できる。

## パス検証

セッションディレクトリには `readonly/` のシンボリックリンクが含まれるため、パス検証は `realpath` ベースで行う。

検証方針は次の通りである。

- `readonly/` の実体は許可済み共有データソース配下に限定する。
- `tmp/` と `artifacts/` は対象セッション配下から出ていないことを検証する。
- `..` や絶対パスによるディレクトリトラバーサルを拒否する。
- `readonly/` 配下は生成物取り込み対象にしない。
- `artifacts/` のDB取り込み後は、履歴表示時にセッションディレクトリ内の同名ファイルを参照しない。

## 後続設計で決めること

次の項目は、内部設計または実装設計で具体化する。

- `<user-id>/<session-id>/` 全体のサイズ上限
- セッションディレクトリの保存期間
- 古いセッションディレクトリのクリーンアップ方針
- artifact本体のDB保存形式
- artifactのMIME typeと拡張子の許可リスト
- DB保存済みartifactの配信用API

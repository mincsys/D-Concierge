# Windows/Linux両対応の実装と検証が不足している

## 概要

設計ではWindows/Linux両対応を仕様としているが、現状の実装とCIではLinux環境での確認が中心であり、Windows環境で同等に動くことを保証できていない。

ただし、Windows/Linux両対応は「Linux上のサーバがWindowsローカルパスを参照できるようにする」ことではない。アプリ内部で実ファイル参照として扱う値をOS非依存のPOSIX相対形式へ標準化し、各OS上では `pathlib.Path` で実ファイルへ解決できるようにする方針とする。

## 設計上の期待

- 要件定義では、WindowsとLinuxの両方で利用できることを要求している。
- 外部設計では、利用者操作、画面表示、API契約、SSE契約はOS差異を持たず、codex execの起動、キャンセル、パス正規化はバックエンド内部で吸収するとしている。
- 設定ファイルIFと共通設計には、Windows/Linuxのパス区切り、ドライブ文字、UNC、大文字小文字差異を正規化して扱う旨の記述がある。
- 実ファイル参照として使うCodex出力パス、DB保存パス、API/SSEで公開する参照先は、OS依存の絶対パスではなく、アプリ内部標準のPOSIX相対形式へ統一する必要がある。

## 現状の実装

- `pathlib.Path`、`subprocess.Popen`、`Path.symlink_to` など、クロスプラットフォームAPIは使っている。
- `FileArtifactStore` は `\` を `/` に正規化し、Windowsドライブ形式を拒否している。
- `session_readonly.py` は共有データソース提示時にsymlink失敗時のコピーfallbackを持つ。
- 検証用成果物提示では、設計どおりsymlink失敗をシステムエラーにしている。Windowsで権限や開発者モード設定が不足している場合は環境構築・動作確認時に検出するため、アプリ側でコピーfallbackを追加する対象ではない。
- `PathSecurityService` は `Path(relative_path)` に依存している。Windows絶対パスをLinux上で解釈する必要はないが、アプリが実ファイル参照として使うパス値をPOSIX相対形式へ標準化する責務は設計上明確にする必要がある。
- Codex出力の参照元パスや成果物リンクは、`readonly/...`、`artifacts/...`、`./artifacts/...` のような相対パスだけを許可対象にしている。区切り文字差分として `readonly\...` や `artifacts\...` が出た場合に、安全な範囲で `/` へ正規化できる余地がある。
- codex execのキャンセルは `subprocess.Popen.terminate()` / `kill()` を呼ぶだけで、OSごとのプロセスグループや子プロセス終了差異を明示的に吸収していない。
- CIはUbuntuのみで、Windowsジョブがない。

## 判断

設計の「Windows/Linux両対応」は維持する。ただし、Windows絶対パスやUNCをアプリが解釈して利用する設計にはしない方がよい。

採用すべき方針は、実ファイル参照として使う値をOS非依存のPOSIX相対形式へ標準化し、許可形式から外れる値は拒否する方式である。ユーザの自然文入力は自由入力のままでよく、固定検証の対象はCodex出力JSON、Markdownリンク、DB保存値、API/SSE公開値など、アプリが実際にファイル参照として使う値に限定する。

## 修正案

- 設計書の「Windows形式パスを正規化する」趣旨を、アプリ内部の参照パスはPOSIX相対形式へ標準化し、許可形式外の絶対パス、UNC、親ディレクトリ参照、URLは拒否する記述へ整理する。
- Codex出力の参照元パスと成果物リンクについて、検証前に安全な範囲で区切り文字を正規化する。
  - `readonly\raw\pdf\manual.pdf` は `readonly/raw/pdf/manual.pdf` へ正規化してよい。
  - `artifacts\chart.png` は `artifacts/chart.png` へ正規化してよい。
  - `./artifacts/chart.png` は `artifacts/chart.png` へ正規化してよい。
  - `C:\...`、`\\server\share\...`、`/home/...`、`../...`、`readonly/../...`、`file://...`、`http://...` は正規化せず拒否する。
- `PathSecurityService` は、アプリ内部標準パスまたはDB保存済み相対パスを実OS上の `Path` へ解決する責務に絞る。
- codex execのキャンセル処理について、Windows/Linuxそれぞれで親子プロセスを含めた終了方針を設計・実装する。
- GitHub ActionsにWindowsジョブを追加し、少なくともバックエンド単体テストとパス安全性テストを実行する。

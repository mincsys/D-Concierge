# codex/readonly と仕様書記述の乖離

## 内容

実装・モックではPDF参照を `codex/readonly` に一本化しているが、`docs/01_要件定義/MVP要件定義.md` には `codex/work` を前提にした記述が残っている。

## 対応方針

要件定義ドキュメントを修正する際に、Codex execが参照するデータソース配置を `codex/readonly` 前提へ整合させる。

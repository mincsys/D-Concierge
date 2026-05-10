# Codex成果物配信でjpg/jpegが許可されていない

## 内容

`docs/03_内部設計/03_内部IF設計/成果物ファイルIF.md` では、Codex成果物として `.jpg` と `.jpeg` を許可拡張子に含めている。

一方、`src/backend/app/factory.py` の成果物配信処理では、保存済み成果物のパス解決時に許可拡張子が `.svg`、`.png`、`.html`、`.csv` に限定されている。

## 影響

採用済み成果物として `.jpg` または `.jpeg` が保存できても、`/api/artifacts/{artifact_id}` で配信するときに拒否され、画面から表示できない可能性がある。

## 対応方針

成果物配信処理の許可拡張子を成果物ファイルIFと `FileArtifactStore` のMIME判定に合わせ、`.jpg` と `.jpeg` を含める。

## 設計と実装の評価

設計の方がよい。画像成果物として `.jpg` / `.jpeg` を許可することは画面設計、成果物ファイルIF、固定検証、`FileArtifactStore` の保存処理と整合している。

実装側の配信処理だけが古い許可拡張子に残っているため、`src/backend/app/factory.py` の `/api/artifacts/{artifact_id}` 配信時のMIMEタイプ・拡張子許可を設計へ合わせる。

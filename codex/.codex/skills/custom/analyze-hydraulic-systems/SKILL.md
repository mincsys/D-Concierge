---
name: analyze-hydraulic-systems
description: readonly/hydraulic_systems_dataset の油圧システム状態監視データを分析する。センサー時系列、profile条件値、サイクル抽出、特徴量作成、条件別集計、必要に応じた一時的なML分析を扱う。
---

# Analyze Hydraulic Systems

## 概要

`readonly/hydraulic_systems_dataset` の油圧試験装置データを、サイクル単位の多変量時系列として分析する。標準ではデータ理解、サイクル抽出、特徴量作成、条件別集計を行う。ユーザ要求に答えるためにML分析が必要または有効な場合は、一時スクリプトを作成して分析してよい。

## 最初に読むファイル

分析を始める前に、必ず以下を全文読む。

- `readonly/hydraulic_systems_dataset/説明.md`
- `readonly/hydraulic_systems_dataset/dataset/documentation.txt`
- `readonly/hydraulic_systems_dataset/dataset/description.txt`

## 前提

- 作業ディレクトリ直下に `readonly/`、`tmp/`、`artifacts/` がある。
- 入力データは主に `readonly/hydraulic_systems_dataset/dataset` から読む。
- `dataset/` 内のセンサー時系列ファイルと `profile.tsv` はタブ区切りTSVとして読み込める。
- `description.txt` と `documentation.txt` は説明文ファイルであり、TSVデータとして扱わない。
- 中間生成物、一時スクリプト、特徴量CSV、モデルファイルは原則 `tmp/` に保存する。
- 最終回答Markdownからリンクする必要がある成果物だけ `artifacts/` に保存する。
- `artifacts/` に保存したファイルは、回答本文から `artifacts/<ファイル名>` 形式でリンクする。

## 利用できる主なライブラリ

- `numpy`
- `pandas`
- `scipy`
- `scikit-learn`
- `matplotlib`

`matplotlib` を使う場合は、設定キャッシュを書き込めるように `MPLCONFIGDIR=tmp/matplotlib-cache` を指定する。

## 基本ワークフロー

1. 最初に読むファイル3件を確認し、センサー、サンプリング周波数、ターゲット条件値を把握する。
2. `inspect_dataset.py` で行数、列数、センサー一覧、`profile.tsv` の値分布を確認する。
3. 必要に応じて `extract_cycles.py` で特定サイクル・特定センサーの元波形を確認する。
4. 統計分析やML分析が必要な場合は、`extract_cycle_features.py` でサイクル単位特徴量CSVを作成する。
5. 条件別の傾向を見る場合は、`summarize_by_condition.py` でターゲット条件ごとの特徴量統計を確認する。
6. ユーザ要求に答えるために必要または有効なら、`tmp/` に一時的なML分析スクリプトを作成して実行する。同梱スクリプトには学習処理を含めない。

## スクリプト

Python は必ず `uv run python` で実行する。

### データセットを確認する

```bash
uv run python "$CODEX_HOME/skills/custom/analyze-hydraulic-systems/scripts/inspect_dataset.py" readonly/hydraulic_systems_dataset/dataset
```

センサーごとの行数、列数、ファイルサイズ、推定サンプリング周波数、`profile.tsv` の値分布をMarkdownで出力する。

### サイクルを抽出する

```bash
uv run python "$CODEX_HOME/skills/custom/analyze-hydraulic-systems/scripts/extract_cycles.py" readonly/hydraulic_systems_dataset/dataset --cycles 1,100,200 --sensors PS1 FS1 TS1
```

指定したサイクル番号とセンサーの先頭・末尾・基本統計をMarkdownで出力する。全量CSVが必要な場合は `--output tmp/cycles.csv` を指定する。

### サイクル特徴量を作る

```bash
uv run python "$CODEX_HOME/skills/custom/analyze-hydraulic-systems/scripts/extract_cycle_features.py" readonly/hydraulic_systems_dataset/dataset --sensors PS1 FS1 TS1 --output tmp/hydraulic_cycle_features.csv
```

センサー時系列を1サイクル1行の特徴量CSVに変換し、`profile.tsv` の5列を結合する。標準特徴量は `mean`、`std`、`min`、`max`、`median`、`q25`、`q75`、`first`、`last`、`range`、`slope`。

### 条件別に集計する

```bash
uv run python "$CODEX_HOME/skills/custom/analyze-hydraulic-systems/scripts/summarize_by_condition.py" tmp/hydraulic_cycle_features.csv --target valve_condition
```

指定ターゲット条件ごとに、特徴量の件数、平均、標準偏差、最小、最大をMarkdownで出力する。CSV保存が必要な場合は `--output tmp/condition_summary.csv` を指定する。

## 回答時の注意

- サイクル番号は1始まりとして説明する。
- `profile.tsv` の5列は、順に `cooler_condition`、`valve_condition`、`pump_leakage`、`accumulator_pressure`、`stable_flag` として扱う。
- ML分析を行った場合は、目的変数、特徴量、分割方法、評価指標、解釈上の注意点を明示する。
- 大容量センサーファイルを全文貼り付けない。必要な集計、抜粋、成果物リンクで説明する。

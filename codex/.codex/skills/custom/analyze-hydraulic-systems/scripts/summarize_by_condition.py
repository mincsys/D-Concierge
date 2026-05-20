"""特徴量CSVをターゲット条件別に集計する。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from common import PROFILE_COLUMNS, configure_standard_streams


def feature_columns(frame: pd.DataFrame, target: str, limit: int) -> list[str]:
    excluded = set(PROFILE_COLUMNS)
    candidates = [column for column in frame.columns if column not in excluded]
    if limit <= 0:
        return candidates
    return candidates[:limit]


def main() -> int:
    configure_standard_streams()
    parser = argparse.ArgumentParser(description="特徴量CSVを条件別にMarkdown集計します。")
    parser.add_argument("features_csv", help="extract_cycle_features.py が出力したCSV")
    parser.add_argument("--target", required=True, choices=PROFILE_COLUMNS, help="集計するターゲット条件列")
    parser.add_argument("--feature-limit", type=int, default=30, help="Markdownに出力する特徴量列数。0で全列")
    parser.add_argument("--output", help="集計CSVの保存先。例: tmp/condition_summary.csv")
    args = parser.parse_args()

    try:
        frame = pd.read_csv(args.features_csv)
        columns = feature_columns(frame, args.target, max(0, args.feature_limit))
        grouped = frame.groupby(args.target)[columns].agg(["count", "mean", "std", "min", "max"])
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            grouped.to_csv(output)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    sys.stdout.write(f"# 条件別特徴量集計: {args.target}\n\n")
    sys.stdout.write(f"- rows: {len(frame)}\n")
    sys.stdout.write(f"- features_shown: {len(columns)}\n")
    if args.output:
        sys.stdout.write(f"- csv_saved: {output}\n")
    sys.stdout.write("\n")

    for value, rows in frame.groupby(args.target):
        sys.stdout.write(f"## {args.target}={value}\n\n")
        sys.stdout.write("| feature | count | mean | std | min | max |\n")
        sys.stdout.write("|---|---:|---:|---:|---:|---:|\n")
        summary = rows[columns].agg(["count", "mean", "std", "min", "max"]).T
        for feature, row in summary.iterrows():
            sys.stdout.write(
                f"| {feature} | {int(row['count'])} | {row['mean']:.6g} | {row['std']:.6g} | "
                f"{row['min']:.6g} | {row['max']:.6g} |\n"
            )
        sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

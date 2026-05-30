"""油圧システムデータセットの構造をMarkdownで確認する。"""

from __future__ import annotations

import argparse
import sys

from common import (
    PROFILE_COLUMNS,
    SENSOR_COLUMNS,
    SENSOR_SAMPLING_RATE_HZ,
    configure_standard_streams,
    read_profile,
    resolve_dataset_dir,
)


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ["B", "KB", "MB", "GB"]:
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def main() -> int:
    configure_standard_streams()
    parser = argparse.ArgumentParser(description="油圧システムデータセットの概要をMarkdownで出力します。")
    parser.add_argument("dataset_dir", help="data_source/hydraulic_systems_dataset/dataset")
    args = parser.parse_args()

    try:
        dataset_dir = resolve_dataset_dir(args.dataset_dir)
        profile = read_profile(dataset_dir)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    sys.stdout.write("# Hydraulic Systems Dataset 概要\n\n")
    sys.stdout.write(f"- サイクル数: {len(profile)}\n")
    sys.stdout.write(f"- センサー数: {len(SENSOR_COLUMNS)}\n")
    sys.stdout.write("- 欠損値: documentation上はなし\n\n")

    sys.stdout.write("## センサーファイル\n\n")
    sys.stdout.write("| sensor | rows | columns | sampling_rate_hz | size |\n")
    sys.stdout.write("|---|---:|---:|---:|---:|\n")
    for sensor, columns in SENSOR_COLUMNS.items():
        path = dataset_dir / f"{sensor}.tsv"
        rows = sum(1 for _ in path.open(encoding="utf-8"))
        size = format_bytes(path.stat().st_size)
        rate = SENSOR_SAMPLING_RATE_HZ[sensor]
        sys.stdout.write(f"| {sensor} | {rows} | {columns} | {rate} | {size} |\n")

    sys.stdout.write("\n## profile.tsv 値分布\n\n")
    for column in PROFILE_COLUMNS:
        sys.stdout.write(f"### {column}\n\n")
        counts = profile[column].value_counts().sort_index()
        sys.stdout.write("| value | count |\n")
        sys.stdout.write("|---:|---:|\n")
        for value, count in counts.items():
            sys.stdout.write(f"| {value} | {count} |\n")
        sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

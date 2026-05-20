"""指定サイクルとセンサーの時系列を抽出する。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from common import (
    configure_standard_streams,
    parse_cycle_numbers,
    read_sensor,
    resolve_dataset_dir,
    validate_sensors,
)


def selected_rows(frame: pd.DataFrame, cycles: list[int]) -> pd.DataFrame:
    indexes = [cycle - 1 for cycle in cycles if 0 < cycle <= len(frame)]
    if not indexes:
        raise ValueError("指定サイクルがデータ範囲内にありません。")
    result = frame.iloc[indexes].copy()
    result.insert(0, "cycle", [index + 1 for index in indexes])
    return result


def write_markdown_summary(dataset_dir: Path, cycles: list[int], sensors: list[str]) -> None:
    sys.stdout.write("# 抽出サイクル要約\n\n")
    sys.stdout.write(f"- cycles: {', '.join(map(str, cycles))}\n")
    sys.stdout.write(f"- sensors: {', '.join(sensors)}\n\n")
    for sensor in sensors:
        frame = read_sensor(dataset_dir, sensor)
        rows = selected_rows(frame, cycles)
        sys.stdout.write(f"## {sensor}\n\n")
        sys.stdout.write("| cycle | samples | mean | std | min | max | first | last |\n")
        sys.stdout.write("|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for _, row in rows.iterrows():
            cycle = int(row["cycle"])
            values = row.drop(labels=["cycle"]).astype(float)
            sys.stdout.write(
                f"| {cycle} | {len(values)} | {values.mean():.6g} | {values.std(ddof=0):.6g} | "
                f"{values.min():.6g} | {values.max():.6g} | {values.iloc[0]:.6g} | {values.iloc[-1]:.6g} |\n"
            )
        sys.stdout.write("\n")


def write_csv(dataset_dir: Path, cycles: list[int], sensors: list[str], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    parts: list[pd.DataFrame] = []
    for sensor in sensors:
        rows = selected_rows(read_sensor(dataset_dir, sensor), cycles)
        renamed = rows.rename(columns={column: f"{sensor}_{column}" for column in rows.columns if column != "cycle"})
        parts.append(renamed)
    merged = parts[0]
    for part in parts[1:]:
        merged = merged.merge(part, on="cycle", how="inner")
    merged.to_csv(output, index=False)


def main() -> int:
    configure_standard_streams()
    parser = argparse.ArgumentParser(description="指定サイクルとセンサーの時系列を抽出します。")
    parser.add_argument("dataset_dir", help="readonly/hydraulic_systems_dataset/dataset")
    parser.add_argument("--cycles", required=True, help="1始まりのサイクル番号。例: 1,100,200 または 1-10")
    parser.add_argument("--sensors", nargs="+", required=True, help="抽出するセンサー名。例: PS1 FS1 TS1")
    parser.add_argument("--output", help="全量CSVの保存先。例: tmp/cycles.csv")
    args = parser.parse_args()

    try:
        dataset_dir = resolve_dataset_dir(args.dataset_dir)
        cycles = parse_cycle_numbers(args.cycles)
        sensors = validate_sensors(args.sensors)
        write_markdown_summary(dataset_dir, cycles, sensors)
        if args.output:
            output = Path(args.output)
            write_csv(dataset_dir, cycles, sensors, output)
            sys.stdout.write(f"CSV saved: {output}\n")
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

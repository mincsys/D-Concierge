"""センサー時系列をサイクル単位特徴量CSVへ変換する。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from common import (
    SENSOR_COLUMNS,
    configure_standard_streams,
    read_profile,
    read_sensor,
    resolve_dataset_dir,
    validate_sensors,
)


def compute_features(sensor: str, frame: pd.DataFrame) -> pd.DataFrame:
    values = frame.to_numpy(dtype=float)
    first = values[:, 0]
    last = values[:, -1]
    q25 = np.quantile(values, 0.25, axis=1)
    q75 = np.quantile(values, 0.75, axis=1)
    return pd.DataFrame(
        {
            f"{sensor}_mean": values.mean(axis=1),
            f"{sensor}_std": values.std(axis=1),
            f"{sensor}_min": values.min(axis=1),
            f"{sensor}_max": values.max(axis=1),
            f"{sensor}_median": np.median(values, axis=1),
            f"{sensor}_q25": q25,
            f"{sensor}_q75": q75,
            f"{sensor}_first": first,
            f"{sensor}_last": last,
            f"{sensor}_range": values.max(axis=1) - values.min(axis=1),
            f"{sensor}_slope": (last - first) / max(values.shape[1] - 1, 1),
        }
    )


def main() -> int:
    configure_standard_streams()
    parser = argparse.ArgumentParser(description="油圧システムデータをサイクル単位特徴量CSVへ変換します。")
    parser.add_argument("dataset_dir", help="readonly/hydraulic_systems_dataset/dataset")
    parser.add_argument("--sensors", nargs="+", default=list(SENSOR_COLUMNS), help="対象センサー名。省略時は全センサー")
    parser.add_argument("--output", default="tmp/hydraulic_cycle_features.csv", help="特徴量CSVの保存先")
    args = parser.parse_args()

    try:
        dataset_dir = resolve_dataset_dir(args.dataset_dir)
        sensors = validate_sensors(args.sensors)
        features: list[pd.DataFrame] = []
        for sensor in sensors:
            features.append(compute_features(sensor, read_sensor(dataset_dir, sensor)))
        result = pd.concat([read_profile(dataset_dir), *features], axis=1)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(output, index=False)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    sys.stdout.write("# 特徴量CSV作成結果\n\n")
    sys.stdout.write(f"- output: {output}\n")
    sys.stdout.write(f"- rows: {len(result)}\n")
    sys.stdout.write(f"- columns: {len(result.columns)}\n")
    sys.stdout.write(f"- sensors: {', '.join(sensors)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""油圧システムデータセット分析スクリプトの共通処理。"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


SENSOR_COLUMNS: dict[str, int] = {
    "PS1": 6000,
    "PS2": 6000,
    "PS3": 6000,
    "PS4": 6000,
    "PS5": 6000,
    "PS6": 6000,
    "EPS1": 6000,
    "FS1": 600,
    "FS2": 600,
    "TS1": 60,
    "TS2": 60,
    "TS3": 60,
    "TS4": 60,
    "VS1": 60,
    "CE": 60,
    "CP": 60,
    "SE": 60,
}

SENSOR_SAMPLING_RATE_HZ: dict[str, int] = {
    "PS1": 100,
    "PS2": 100,
    "PS3": 100,
    "PS4": 100,
    "PS5": 100,
    "PS6": 100,
    "EPS1": 100,
    "FS1": 10,
    "FS2": 10,
    "TS1": 1,
    "TS2": 1,
    "TS3": 1,
    "TS4": 1,
    "VS1": 1,
    "CE": 1,
    "CP": 1,
    "SE": 1,
}

PROFILE_COLUMNS = [
    "cooler_condition",
    "valve_condition",
    "pump_leakage",
    "accumulator_pressure",
    "stable_flag",
]


def configure_standard_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def resolve_dataset_dir(path_text: str) -> Path:
    path = Path(path_text)
    if not path.exists():
        raise FileNotFoundError(f"データセットディレクトリが見つかりません: {path}")
    if not path.is_dir():
        raise ValueError(f"データセットディレクトリを指定してください: {path}")
    missing = [name for name in [*SENSOR_COLUMNS, "profile"] if not (path / f"{name}.tsv").exists()]
    if missing:
        raise FileNotFoundError(f"必要なtxtファイルが見つかりません: {', '.join(missing)}")
    return path


def parse_csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_cycle_numbers(value: str) -> list[int]:
    cycles: set[int] = set()
    for part in parse_csv_list(value):
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if start > end:
                start, end = end, start
            cycles.update(range(start, end + 1))
        else:
            cycles.add(int(part))
    return sorted(cycle for cycle in cycles if cycle > 0)


def validate_sensors(sensors: list[str]) -> list[str]:
    unknown = [sensor for sensor in sensors if sensor not in SENSOR_COLUMNS]
    if unknown:
        raise ValueError(f"未知のセンサー名です: {', '.join(unknown)}")
    return sensors


def read_sensor(dataset_dir: Path, sensor: str) -> pd.DataFrame:
    return pd.read_csv(dataset_dir / f"{sensor}.tsv", sep="\t", header=None)


def read_profile(dataset_dir: Path) -> pd.DataFrame:
    return pd.read_csv(dataset_dir / "profile.tsv", sep="\t", header=None, names=PROFILE_COLUMNS)

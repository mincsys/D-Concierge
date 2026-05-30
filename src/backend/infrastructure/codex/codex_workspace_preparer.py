from pathlib import Path


def prepare_generation_workspace(workdir: Path) -> None:
    """生成用Codex作業領域を準備する。"""
    _ensure_dir(workdir)
    _ensure_dir(workdir / "tmp")
    _ensure_dir(workdir / "artifacts")


def prepare_validation_workspace(workdir: Path) -> None:
    """検証用Codex作業領域を準備する。"""
    _ensure_dir(workdir)
    _ensure_dir(workdir / "tmp")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

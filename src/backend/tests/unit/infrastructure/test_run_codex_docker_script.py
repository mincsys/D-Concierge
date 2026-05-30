import os
import subprocess
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).parents[3] / "infrastructure" / "codex" / "run_codex_docker.sh"
)


def test_run_codex_docker_script_builds_docker_command(tmp_path: Path) -> None:
    """観点：Docker起動スクリプト。確認：名前付き引数からdocker run引数を組み立てる。"""
    docker_capture = tmp_path / "docker-args.txt"
    docker_bin = tmp_path / "bin" / "docker"
    docker_bin.parent.mkdir()
    docker_bin.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$@" > "$DOCKER_CAPTURE"
printf 'CODEX_API_KEY=%s\n' "${CODEX_API_KEY-}" >> "$DOCKER_CAPTURE"
""",
        encoding="utf-8",
    )
    docker_bin.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{docker_bin.parent}:{env['PATH']}"
    env["DOCKER_CAPTURE"] = str(docker_capture)
    env["CODEX_API_KEY"] = "sk-test"

    completed = subprocess.run(
        [
            str(SCRIPT_PATH),
            "--container-name",
            "d-concierge-generator-run-001",
            "--image",
            "codex-python-runner:latest",
            "--workspace-dir",
            "/workspace",
            "--codex-home-dir",
            "/home/codex/.codex",
            "--host-codex-home",
            str(tmp_path / "codex-home"),
            "--host-workdir",
            str(tmp_path / "session"),
            "--host-datasource",
            str(tmp_path / "readonly"),
            "--host-schema-dir",
            str(tmp_path / "schemas"),
            "--schema-file",
            "schema.json",
            "--host-artifacts",
            str(tmp_path / "artifacts"),
            "--prompt",
            "資料を要約してください",
            "--conversation-id",
            "thread-001",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode == 0
    assert completed.stdout == ""
    captured = docker_capture.read_text(encoding="utf-8").splitlines()
    assert captured[:3] == ["run", "--rm", "--name"]
    assert "d-concierge-generator-run-001" in captured
    assert "codex-python-runner:latest" in captured
    assert "CODEX_API_KEY=sk-test" in captured
    assert "--read-only" in captured
    assert "--cap-drop" in captured
    assert "ALL" in captured
    assert "codex" in captured
    assert "exec" in captured
    assert "--json" in captured
    assert "--skip-git-repo-check" in captured
    assert "--sandbox" in captured
    assert "workspace-write" in captured
    assert "--output-schema" in captured
    assert "/tmp/output_json_schema/schema.json" in captured
    assert "resume" in captured
    assert "thread-001" in captured
    assert "資料を要約してください" in captured


def test_run_codex_docker_script_rejects_unsafe_schema_file(
    tmp_path: Path,
) -> None:
    """観点：Docker起動スクリプト。確認：schema-fileにパス区切りを含めない。"""
    completed = subprocess.run(
        [
            str(SCRIPT_PATH),
            "--container-name",
            "d-concierge-generator-run-001",
            "--image",
            "codex-python-runner:latest",
            "--workspace-dir",
            "/workspace",
            "--codex-home-dir",
            "/home/codex/.codex",
            "--host-codex-home",
            str(tmp_path / "codex-home"),
            "--host-workdir",
            str(tmp_path / "session"),
            "--host-datasource",
            str(tmp_path / "readonly"),
            "--host-schema-dir",
            str(tmp_path / "schemas"),
            "--schema-file",
            "../schema.json",
            "--prompt",
            "資料を要約してください",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "schema-file" in completed.stderr

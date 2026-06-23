from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

import pytest

from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.tests.support.chat import (
    CHAT_ID_VALUE,
    F003_USER_ID,
    RUN_ID_VALUE,
    SESSION_ID_VALUE,
)
from backend.tests.support.codex import (
    valid_candidate_json,
    validation_result,
)

if TYPE_CHECKING:
    from backend.infrastructure.codex.codex_runner import CodexRunnerSettings


@dataclass(frozen=True, slots=True)
class ProcessExecutionRecord:
    command: tuple[str, ...]
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class ProcessResultRecord:
    return_code: int
    stdout_lines: tuple[str, ...]
    stderr: str = ""


@dataclass(slots=True)
class RecordingCodexProcessRunner:
    result: ProcessResultRecord
    executions: list[ProcessExecutionRecord] = field(default_factory=list)
    raise_timeout: bool = False

    def run(
        self,
        command: tuple[str, ...],
        timeout_seconds: int,
    ) -> ProcessResultRecord:
        self.executions.append(
            ProcessExecutionRecord(
                command=command,
                timeout_seconds=timeout_seconds,
            ),
        )
        if self.raise_timeout:
            raise TimeoutError("Codex実行がタイムアウトしました。")
        return self.result


@dataclass(frozen=True, slots=True)
class StopRequestRecord:
    container_name: str
    grace_seconds: int


@dataclass(slots=True)
class RecordingDockerStopper:
    return_code: int = 0
    requests: list[StopRequestRecord] = field(default_factory=list)

    def stop(self, container_name: str, grace_seconds: int) -> int:
        self.requests.append(
            StopRequestRecord(
                container_name=container_name,
                grace_seconds=grace_seconds,
            ),
        )
        return self.return_code


@dataclass(frozen=True, slots=True)
class RegisteredProcessRecord:
    container_name: str
    completed: bool = False


@dataclass(slots=True)
class FakeRunningProcessRegistry:
    processes: dict[UUID, RegisteredProcessRecord] = field(default_factory=dict)

    def get(self, run_id: UUID) -> RegisteredProcessRecord | None:
        return self.processes.get(run_id)

    def register(self, run_id: UUID, container_name: str) -> None:
        self.processes[run_id] = RegisteredProcessRecord(container_name)

    def remove(self, run_id: UUID) -> None:
        self.processes.pop(run_id, None)


class CodexRunnerLike(Protocol):
    """CodexRunnerのcancel契約を観測するためのProtocol。"""

    def cancel(self, run_id: UUID, trace_id: str) -> str: ...


def _successful_generation_stdout() -> tuple[str, ...]:
    return (
        json.dumps({"type": "thread.started", "thread_id": "gen-thread-001"}),
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": json.dumps(
                        {"payload": {"kind": "progress", "text": "調査中です。"}},
                        ensure_ascii=False,
                    ),
                },
            },
            ensure_ascii=False,
        ),
        json.dumps(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": valid_candidate_json()},
            },
            ensure_ascii=False,
        ),
        json.dumps({"type": "turn.completed"}),
    )


def _successful_validation_stdout() -> tuple[str, ...]:
    return (
        json.dumps({"type": "thread.started", "thread_id": "val-thread-001"}),
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": validation_result(valid=True).final_result_json,
                },
            },
            ensure_ascii=False,
        ),
        json.dumps({"type": "turn.completed"}),
    )


def test_workspace_preparer_creates_generation_and_validation_dirs(
    tmp_path: Path,
) -> None:
    """
    観点：CodexWorkspacePreparerが生成用と検証用の作業領域を分離すること
    確認：生成用はtmp/artifacts、検証用はtmpだけを作成し、両者のパスを
    混在させないこと
    """
    from backend.infrastructure.codex.codex_workspace_preparer import (
        prepare_generation_workspace,
        prepare_validation_workspace,
    )

    generation_dir = tmp_path / "sessions" / F003_USER_ID / str(SESSION_ID_VALUE)
    validation_dir = (
        tmp_path / "sessions_validator" / F003_USER_ID / str(SESSION_ID_VALUE)
    )

    generation_workspace = prepare_generation_workspace(generation_dir)
    validation_workspace = prepare_validation_workspace(validation_dir)

    assert generation_workspace.workdir == generation_dir
    assert generation_workspace.tmp_dir == generation_dir / "tmp"
    assert generation_workspace.artifacts_dir == generation_dir / "artifacts"
    assert generation_workspace.tmp_dir.is_dir()
    assert generation_workspace.artifacts_dir.is_dir()
    assert validation_workspace.workdir == validation_dir
    assert validation_workspace.tmp_dir == validation_dir / "tmp"
    assert validation_workspace.tmp_dir.is_dir()
    assert not (validation_dir / "artifacts").exists()
    assert generation_workspace.workdir != validation_workspace.workdir


def test_workspace_preparer_raises_and_does_not_create_children_on_failure(
    tmp_path: Path,
) -> None:
    """
    観点：CodexWorkspacePreparerが作業領域準備失敗をCodex実行前に通知すること
    確認：セッション作業領域パスにファイルがある場合はtrace対象のSYSTEM AppErrorとなり、
    tmp/artifactsを作らないこと
    """
    from backend.infrastructure.codex.codex_workspace_preparer import (
        prepare_generation_workspace,
    )

    session_path = tmp_path / "sessions" / F003_USER_ID / str(SESSION_ID_VALUE)
    session_path.parent.mkdir(parents=True)
    session_path.write_text("not directory", encoding="utf-8")

    with pytest.raises(AppError) as raised:
        prepare_generation_workspace(session_path)

    assert raised.value.error_type is ErrorType.SYSTEM
    assert raised.value.trace is True
    assert not (session_path / "tmp").exists()
    assert not (session_path / "artifacts").exists()


def test_codex_runner_generation_uses_named_args_resume_and_timeout(
    tmp_path: Path,
) -> None:
    """
    観点：CodexRunnerが生成用Docker実行を名前付き引数でsubprocess境界へ渡すこと
    確認：生成用home/workdir/schema/data_source、resume ID、timeoutを分離して渡し、
    turn.completed後のfinal候補とprogressだけを結果へ返すこと
    """
    from backend.application.ports.codex.dto import CodexGenerationRequest
    from backend.infrastructure.codex.codex_runner import CodexRunner

    process_runner = RecordingCodexProcessRunner(
        result=ProcessResultRecord(
            return_code=0,
            stdout_lines=_successful_generation_stdout(),
        ),
    )
    stopper = RecordingDockerStopper()
    runner = CodexRunner(
        settings=_runner_settings(tmp_path),
        process_runner=process_runner,
        docker_stopper=stopper,
    )

    result = runner.run_generation(
        CodexGenerationRequest(
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            user_id=F003_USER_ID,
            session_id=SESSION_ID_VALUE,
            user_instruction="ポンプの点検方法を教えてください。",
            resume_conversation_id="gen-thread-previous",
            regeneration_instruction=None,
            remaining_seconds=300,
        ),
    )

    command = process_runner.executions[0].command
    assert process_runner.executions[0].timeout_seconds == 300
    assert "--container-name" in command
    assert f"d-concierge-generator-{RUN_ID_VALUE}" in command
    assert "--host-codex-home" in command
    assert str(tmp_path / "codex" / ".codex") in command
    assert "--host-workdir" in command
    generation_workdir = (
        tmp_path / "codex" / "sessions" / F003_USER_ID / str(SESSION_ID_VALUE)
    )
    assert str(generation_workdir) in command
    assert "--host-data-source" in command
    assert str(tmp_path / "codex" / "data_source") in command
    assert "--output-schema-file" in command
    assert "answer.json" in command
    assert "--conversation-id" in command
    assert "gen-thread-previous" in command
    assert "--host-artifacts" not in command
    assert result.conversation_id == "gen-thread-001"
    assert result.progress_messages == ("調査中です。",)
    assert result.final_answer_json == valid_candidate_json()


def test_codex_runner_validation_uses_validator_home_and_optional_artifacts(
    tmp_path: Path,
) -> None:
    """
    観点：CodexRunnerが検証用Docker実行を生成用設定から分離すること
    確認：検証用home/workdir/schemaを使い、resume ID未指定時はconversation-idを渡さず、
    artifactsディレクトリがある場合だけhost-artifactsを渡すこと
    """
    from backend.application.ports.codex.dto import ValidatorCodexRequest
    from backend.infrastructure.codex.codex_runner import CodexRunner

    artifacts_dir = (
        tmp_path
        / "codex"
        / "sessions"
        / F003_USER_ID
        / str(SESSION_ID_VALUE)
        / "artifacts"
    )
    artifacts_dir.mkdir(parents=True)
    (artifacts_dir / "diagram.svg").write_text("<svg />", encoding="utf-8")
    process_runner = RecordingCodexProcessRunner(
        result=ProcessResultRecord(
            return_code=0,
            stdout_lines=_successful_validation_stdout(),
        ),
    )
    runner = CodexRunner(
        settings=_runner_settings(tmp_path),
        process_runner=process_runner,
        docker_stopper=RecordingDockerStopper(),
    )

    result = runner.run_validation(
        ValidatorCodexRequest(
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            user_id=F003_USER_ID,
            session_id=SESSION_ID_VALUE,
            candidate_json=valid_candidate_json(),
            resume_conversation_id=None,
            artifacts_readonly_dir=artifacts_dir,
            remaining_seconds=240,
        ),
    )

    command = process_runner.executions[0].command
    assert "--container-name" in command
    assert f"d-concierge-validator-{RUN_ID_VALUE}" in command
    assert str(tmp_path / "codex" / ".codex_validator") in command
    validation_workdir = (
        tmp_path / "codex" / "sessions_validator" / F003_USER_ID / str(SESSION_ID_VALUE)
    )
    assert str(validation_workdir) in command
    assert "validator.json" in command
    assert "--conversation-id" not in command
    assert "--host-artifacts" in command
    assert str(artifacts_dir) in command
    assert result.conversation_id == "val-thread-001"
    assert result.final_result_json == validation_result(valid=True).final_result_json


def test_codex_runner_timeout_stops_container_and_raises_trace_error(
    tmp_path: Path,
) -> None:
    """
    観点：CodexRunnerが1回実行timeout時に実行中コンテナへ停止要求を送ること
    確認：timeoutではdocker stop -t 10を呼び、利用者向け出力ではなくtrace対象の
    SYSTEM AppErrorとして上位へ返すこと
    """
    from backend.application.ports.codex.dto import CodexGenerationRequest
    from backend.infrastructure.codex.codex_runner import CodexRunner

    process_runner = RecordingCodexProcessRunner(
        result=ProcessResultRecord(return_code=0, stdout_lines=()),
        raise_timeout=True,
    )
    stopper = RecordingDockerStopper(return_code=1)
    runner = CodexRunner(
        settings=_runner_settings(tmp_path),
        process_runner=process_runner,
        docker_stopper=stopper,
    )

    with pytest.raises(AppError) as raised:
        runner.run_generation(
            CodexGenerationRequest(
                chat_id=CHAT_ID_VALUE,
                run_id=RUN_ID_VALUE,
                user_id=F003_USER_ID,
                session_id=SESSION_ID_VALUE,
                user_instruction="ポンプの点検方法を教えてください。",
                resume_conversation_id=None,
                regeneration_instruction=None,
                remaining_seconds=1,
            ),
        )

    assert raised.value.error_type is ErrorType.SYSTEM
    assert raised.value.trace is True
    assert stopper.requests == [
        StopRequestRecord(
            container_name=f"d-concierge-generator-{RUN_ID_VALUE}",
            grace_seconds=10,
        ),
    ]


def test_codex_runner_raises_trace_error_on_non_zero_exit(
    tmp_path: Path,
) -> None:
    """
    観点：CodexRunnerがDocker実行の非0終了をtrace対象障害として扱うこと
    確認：stderrの診断をAppErrorへ含め、回答候補として採用しないこと
    """
    from backend.application.ports.codex.dto import CodexGenerationRequest
    from backend.infrastructure.codex.codex_runner import CodexRunner

    runner = CodexRunner(
        settings=_runner_settings(tmp_path),
        process_runner=RecordingCodexProcessRunner(
            result=ProcessResultRecord(
                return_code=2,
                stdout_lines=(),
                stderr="docker failed",
            ),
        ),
        docker_stopper=RecordingDockerStopper(),
    )

    with pytest.raises(AppError) as raised:
        runner.run_generation(
            CodexGenerationRequest(
                chat_id=CHAT_ID_VALUE,
                run_id=RUN_ID_VALUE,
                user_id=F003_USER_ID,
                session_id=SESSION_ID_VALUE,
                user_instruction="ポンプの点検方法を教えてください。",
                resume_conversation_id=None,
                regeneration_instruction=None,
                remaining_seconds=300,
            ),
        )

    assert raised.value.error_type is ErrorType.SYSTEM
    assert raised.value.trace is True
    assert "docker failed" in raised.value.diagnostic_message


@pytest.mark.parametrize(
    "stdout_lines",
    (
        (
            json.dumps({"type": "thread.started", "thread_id": "gen-thread-001"}),
            json.dumps(
                {
                    "type": "turn.failed",
                    "error": {"message": "生成に失敗しました。"},
                },
                ensure_ascii=False,
            ),
        ),
        (
            json.dumps({"type": "thread.started", "thread_id": "gen-thread-001"}),
            json.dumps({"type": "turn.completed"}),
        ),
    ),
)
def test_codex_runner_raises_trace_error_for_failed_or_missing_final_stdout(
    tmp_path: Path,
    stdout_lines: tuple[str, ...],
) -> None:
    """
    観点：CodexRunnerがJSONL上の失敗とfinal欠落を上位障害へ変換すること
    確認：turn.failedまたはfinal payload欠落ではSYSTEMかつtrace対象のAppErrorとなること
    """
    from backend.application.ports.codex.dto import CodexGenerationRequest
    from backend.infrastructure.codex.codex_runner import CodexRunner

    runner = CodexRunner(
        settings=_runner_settings(tmp_path),
        process_runner=RecordingCodexProcessRunner(
            result=ProcessResultRecord(
                return_code=0,
                stdout_lines=stdout_lines,
            ),
        ),
        docker_stopper=RecordingDockerStopper(),
    )

    with pytest.raises(AppError) as raised:
        runner.run_generation(
            CodexGenerationRequest(
                chat_id=CHAT_ID_VALUE,
                run_id=RUN_ID_VALUE,
                user_id=F003_USER_ID,
                session_id=SESSION_ID_VALUE,
                user_instruction="ポンプの点検方法を教えてください。",
                resume_conversation_id=None,
                regeneration_instruction=None,
                remaining_seconds=300,
            ),
        )

    assert raised.value.error_type is ErrorType.SYSTEM
    assert raised.value.trace is True


@pytest.mark.parametrize(
    ("registry", "stop_return_code", "expected_status"),
    (
        (FakeRunningProcessRegistry(), 0, "not_registered"),
        (
            FakeRunningProcessRegistry(
                processes={
                    RUN_ID_VALUE: RegisteredProcessRecord(
                        container_name=f"d-concierge-generator-{RUN_ID_VALUE}",
                        completed=True,
                    ),
                },
            ),
            0,
            "already_exited",
        ),
        (
            FakeRunningProcessRegistry(
                processes={
                    RUN_ID_VALUE: RegisteredProcessRecord(
                        container_name=f"d-concierge-generator-{RUN_ID_VALUE}",
                    ),
                },
            ),
            0,
            "sent",
        ),
        (
            FakeRunningProcessRegistry(
                processes={
                    RUN_ID_VALUE: RegisteredProcessRecord(
                        container_name=f"d-concierge-generator-{RUN_ID_VALUE}",
                    ),
                },
            ),
            1,
            "not_registered",
        ),
    ),
    ids=("not_registered", "already_exited", "sent", "stop_failed"),
)
def test_codex_runner_cancel_classifies_docker_stop_result(
    tmp_path: Path,
    registry: FakeRunningProcessRegistry,
    stop_return_code: int,
    expected_status: str,
) -> None:
    """
    観点：CodexRunner.cancelが実行中プロセス登録とdocker stop結果を分類すること
    確認：未登録、終了済み、停止要求送信済み、stop失敗をsent/already_exited/
    not_registeredへ変換し、docker rm -fを要求しないこと
    """
    from backend.infrastructure.codex.codex_runner import CodexRunner

    stopper = RecordingDockerStopper(return_code=stop_return_code)
    runner = CodexRunner(
        settings=_runner_settings(tmp_path),
        process_runner=RecordingCodexProcessRunner(
            result=ProcessResultRecord(return_code=0, stdout_lines=()),
        ),
        docker_stopper=stopper,
        process_registry=registry,
    )

    result = runner.cancel(RUN_ID_VALUE, trace_id="trace-f005")

    assert result.status == expected_status
    if expected_status in {"sent", "not_registered"} and registry.processes:
        assert stopper.requests[0].grace_seconds == 10


def _runner_settings(tmp_path: Path) -> CodexRunnerSettings:
    from backend.infrastructure.codex.codex_runner import CodexRunnerSettings

    return CodexRunnerSettings(
        script_path=tmp_path / "run_codex_docker.sh",
        generator_home=tmp_path / "codex" / ".codex",
        validator_home=tmp_path / "codex" / ".codex_validator",
        generator_workdir_root=tmp_path / "codex" / "sessions",
        validator_workdir_root=tmp_path / "codex" / "sessions_validator",
        data_source_dir=tmp_path / "codex" / "data_source",
        output_schema_dir=tmp_path / "codex" / "output_json_schema",
        generator_schema_file="answer.json",
        validator_schema_file="validator.json",
    )

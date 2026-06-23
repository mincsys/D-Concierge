from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from backend.application.execution.dto import CodexCancelResult
from backend.application.ports.codex.dto import (
    CodexGenerationRequest,
    CodexGenerationResult,
    ValidatorCodexRequest,
    ValidatorCodexResult,
)
from backend.infrastructure.codex.codex_workspace_preparer import (
    prepare_generation_workspace,
    prepare_validation_workspace,
)
from backend.infrastructure.codex.jsonl_event_parser import (
    JsonlEvent,
    JsonlEventParser,
    JsonlEventType,
)
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError


@dataclass(frozen=True, slots=True)
class CodexRunnerSettings:
    """Codex実行に必要なホスト側設定。"""

    script_path: Path
    generator_home: Path
    validator_home: Path
    generator_workdir_root: Path
    validator_workdir_root: Path
    data_source_dir: Path
    output_schema_dir: Path
    generator_schema_file: str
    validator_schema_file: str


class ProcessRunResultLike(Protocol):
    """Codex実行プロセスの終了結果。"""

    @property
    def return_code(self) -> int: ...

    @property
    def stdout_lines(self) -> tuple[str, ...]: ...

    @property
    def stderr(self) -> str: ...


class CodexProcessRunnerLike(Protocol):
    """Codex実行プロセス起動境界。"""

    def run(
        self,
        command: tuple[str, ...],
        timeout_seconds: int,
    ) -> ProcessRunResultLike: ...


class DockerStopperLike(Protocol):
    """Docker停止要求境界。"""

    def stop(self, container_name: str, grace_seconds: int) -> int: ...


class RunningProcessRecordLike(Protocol):
    """実行中プロセス登録の読取結果。"""

    @property
    def container_name(self) -> str: ...

    @property
    def completed(self) -> bool: ...


class RunningProcessRegistryLike(Protocol):
    """実行中Codexプロセス登録境界。"""

    def get(self, run_id: UUID) -> RunningProcessRecordLike | None: ...

    def register(self, run_id: UUID, container_name: str) -> None: ...

    def remove(self, run_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class ProcessRunResult:
    """標準subprocess実行の戻り値。"""

    return_code: int
    stdout_lines: tuple[str, ...]
    stderr: str


@dataclass(frozen=True, slots=True)
class SubprocessCodexProcessRunner:
    """run_codex_docker.shをsubprocessで実行する境界。"""

    def run(
        self,
        command: tuple[str, ...],
        timeout_seconds: int,
    ) -> ProcessRunResult:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_seconds,
        )
        return ProcessRunResult(
            return_code=completed.returncode,
            stdout_lines=tuple(
                line for line in completed.stdout.splitlines() if line.strip()
            ),
            stderr=completed.stderr,
        )


@dataclass(frozen=True, slots=True)
class DockerStopper:
    """docker stopを実行する境界。"""

    def stop(self, container_name: str, grace_seconds: int) -> int:
        completed = subprocess.run(
            ("docker", "stop", "-t", str(grace_seconds), container_name),
            capture_output=True,
            check=False,
            text=True,
        )
        return completed.returncode


@dataclass(slots=True)
class InMemoryRunningProcessRegistry:
    """同一プロセス内で実行中Codexコンテナを保持する簡易登録。"""

    _processes: dict[UUID, RunningProcessRecordLike]

    def __init__(self) -> None:
        self._processes = {}

    def get(self, run_id: UUID) -> RunningProcessRecordLike | None:
        return self._processes.get(run_id)

    def register(self, run_id: UUID, container_name: str) -> None:
        self._processes[run_id] = _RunningProcessRecord(container_name=container_name)

    def remove(self, run_id: UUID) -> None:
        self._processes.pop(run_id, None)


@dataclass(frozen=True, slots=True)
class _RunningProcessRecord:
    container_name: str
    completed: bool = False


@dataclass(slots=True)
class CodexRunner:
    """生成用・検証用Codex実行コンテナを制御する。"""

    settings: CodexRunnerSettings
    process_runner: CodexProcessRunnerLike
    docker_stopper: DockerStopperLike
    process_registry: RunningProcessRegistryLike

    def __init__(
        self,
        settings: CodexRunnerSettings,
        process_runner: CodexProcessRunnerLike | None = None,
        docker_stopper: DockerStopperLike | None = None,
        process_registry: RunningProcessRegistryLike | None = None,
    ) -> None:
        self.settings = settings
        self.process_runner = process_runner or SubprocessCodexProcessRunner()
        self.docker_stopper = docker_stopper or DockerStopper()
        self.process_registry = process_registry or InMemoryRunningProcessRegistry()

    def run_generation(
        self,
        request: CodexGenerationRequest,
    ) -> CodexGenerationResult:
        workspace = prepare_generation_workspace(
            self.settings.generator_workdir_root
            / request.user_id
            / str(request.session_id),
        )
        container_name = f"d-concierge-generator-{request.run_id}"
        result = self._run_codex(
            run_id=request.run_id,
            command=self._base_command(
                container_name=container_name,
                codex_home=self.settings.generator_home,
                workdir=workspace.workdir,
                schema_file=self.settings.generator_schema_file,
                resume_conversation_id=request.resume_conversation_id,
                artifacts_dir=None,
            ),
            timeout_seconds=request.remaining_seconds,
            container_name=container_name,
        )
        return CodexGenerationResult(
            conversation_id=result.conversation_id,
            progress_messages=result.progress_messages,
            final_answer_json=result.final_payload_json,
            artifacts_dir=workspace.artifacts_dir,
        )

    def run_validation(
        self,
        request: ValidatorCodexRequest,
    ) -> ValidatorCodexResult:
        workspace = prepare_validation_workspace(
            self.settings.validator_workdir_root
            / request.user_id
            / str(request.session_id),
        )
        container_name = f"d-concierge-validator-{request.run_id}"
        result = self._run_codex(
            run_id=request.run_id,
            command=self._base_command(
                container_name=container_name,
                codex_home=self.settings.validator_home,
                workdir=workspace.workdir,
                schema_file=self.settings.validator_schema_file,
                resume_conversation_id=request.resume_conversation_id,
                artifacts_dir=request.artifacts_readonly_dir,
            ),
            timeout_seconds=request.remaining_seconds,
            container_name=container_name,
        )
        return ValidatorCodexResult(
            conversation_id=result.conversation_id,
            progress_messages=result.progress_messages,
            final_result_json=result.final_payload_json,
        )

    def cancel(self, run_id: UUID, trace_id: str) -> CodexCancelResult:
        record = self.process_registry.get(run_id)
        if record is None:
            return CodexCancelResult(status="not_registered")
        if record.completed:
            self.process_registry.remove(run_id)
            return CodexCancelResult(status="already_exited")
        return_code = self.docker_stopper.stop(record.container_name, 10)
        self.process_registry.remove(run_id)
        if return_code == 0:
            return CodexCancelResult(status="sent")
        return CodexCancelResult(status="not_registered")

    def _base_command(
        self,
        *,
        container_name: str,
        codex_home: Path,
        workdir: Path,
        schema_file: str,
        resume_conversation_id: str | None,
        artifacts_dir: Path | None,
    ) -> tuple[str, ...]:
        command = [
            str(self.settings.script_path),
            "--container-name",
            container_name,
            "--host-codex-home",
            str(codex_home),
            "--host-workdir",
            str(workdir),
            "--host-data-source",
            str(self.settings.data_source_dir),
            "--output-schema-file",
            schema_file,
        ]
        if resume_conversation_id is not None:
            command.extend(("--conversation-id", resume_conversation_id))
        if artifacts_dir is not None:
            command.extend(("--host-artifacts", str(artifacts_dir)))
        return tuple(command)

    def _run_codex(
        self,
        *,
        run_id: UUID,
        command: tuple[str, ...],
        timeout_seconds: int,
        container_name: str,
    ) -> _ParsedCodexRun:
        self.process_registry.register(run_id, container_name)
        try:
            result = self.process_runner.run(command, timeout_seconds)
        except TimeoutError as error:
            self.docker_stopper.stop(container_name, 10)
            raise AppError(
                error_type=ErrorType.SYSTEM,
                trace=True,
                diagnostic_message="Codex実行がタイムアウトしました。",
                cause=error,
            ) from error
        finally:
            self.process_registry.remove(run_id)
        if result.return_code != 0:
            raise AppError(
                error_type=ErrorType.SYSTEM,
                trace=True,
                diagnostic_message=f"Codex実行が失敗しました: {result.stderr}",
            )
        return _parse_stdout(result.stdout_lines)


@dataclass(frozen=True, slots=True)
class _ParsedCodexRun:
    conversation_id: str
    progress_messages: tuple[str, ...]
    final_payload_json: str


def _parse_stdout(stdout_lines: tuple[str, ...]) -> _ParsedCodexRun:
    parser = JsonlEventParser()
    thread_id = ""
    progress_messages: list[str] = []
    final_payload_json = ""
    for line in stdout_lines:
        event = parser.parse_line(line)
        if event.event_type is JsonlEventType.THREAD_STARTED:
            thread_id = event.thread_id or ""
        elif event.event_type is JsonlEventType.AGENT_MESSAGE:
            _append_agent_message(event, progress_messages)
            if event.final_payload_json is not None:
                final_payload_json = event.final_payload_json
        elif event.event_type in {JsonlEventType.TURN_FAILED, JsonlEventType.ERROR}:
            raise AppError(
                error_type=ErrorType.SYSTEM,
                trace=True,
                diagnostic_message=event.error_message or "Codex実行が失敗しました。",
            )
    if not final_payload_json:
        raise AppError(
            error_type=ErrorType.SYSTEM,
            trace=True,
            diagnostic_message="Codex実行の最終出力がありません。",
        )
    return _ParsedCodexRun(
        conversation_id=thread_id,
        progress_messages=tuple(progress_messages),
        final_payload_json=final_payload_json,
    )


def _append_agent_message(
    event: JsonlEvent,
    progress_messages: list[str],
) -> None:
    if event.progress_text is not None:
        progress_messages.append(event.progress_text)

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
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
from backend.tests.support.codex import valid_candidate_json, validation_result

if TYPE_CHECKING:
    from backend.application.ports.codex.dto import CodexGenerationRequest
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
            ProcessExecutionRecord(command=command, timeout_seconds=timeout_seconds),
        )
        if self.raise_timeout:
            raise TimeoutError("timeout")
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
        self.requests.append(StopRequestRecord(container_name, grace_seconds))
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


def test_codex_runner_generation_and_validation_parse_jsonl_contract(
    tmp_path: Path,
) -> None:
    """
    観点：CodexRunnerがJSONL parserと連携して生成用・検証用結果を返すこと
    確認：progress/final/thread IDを抽出し、用途別home/workdir/schema/artifactsを
    名前付き引数でプロセス境界へ渡すこと
    """
    from backend.application.ports.codex.dto import (
        CodexGenerationRequest,
        ValidatorCodexRequest,
    )
    from backend.infrastructure.codex.codex_runner import CodexRunner

    generation_process = RecordingCodexProcessRunner(
        result=ProcessResultRecord(0, _generation_stdout()),
    )
    generation_runner = CodexRunner(
        settings=_runner_settings(tmp_path),
        process_runner=generation_process,
        docker_stopper=RecordingDockerStopper(),
    )

    generation_result = generation_runner.run_generation(
        CodexGenerationRequest(
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            user_id=F003_USER_ID,
            session_id=SESSION_ID_VALUE,
            user_instruction="ポンプ点検",
            resume_conversation_id="gen-thread-before",
            regeneration_instruction=None,
            remaining_seconds=300,
        ),
    )

    generation_command = generation_process.executions[0].command
    assert generation_result.conversation_id == "gen-thread-001"
    assert generation_result.progress_messages == ("調査中です。",)
    assert generation_result.final_answer_json == valid_candidate_json()
    assert "--conversation-id" in generation_command
    assert "gen-thread-before" in generation_command
    assert "--host-artifacts" not in generation_command
    assert generation_process.executions[0].timeout_seconds == 300

    artifacts_dir = generation_result.artifacts_dir
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "diagram.svg").write_text("<svg />", encoding="utf-8")
    validation_process = RecordingCodexProcessRunner(
        result=ProcessResultRecord(0, _validation_stdout()),
    )
    validation_runner = CodexRunner(
        settings=_runner_settings(tmp_path),
        process_runner=validation_process,
        docker_stopper=RecordingDockerStopper(),
    )

    validation_result_record = validation_runner.run_validation(
        ValidatorCodexRequest(
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            user_id=F003_USER_ID,
            session_id=SESSION_ID_VALUE,
            candidate_json=valid_candidate_json(),
            resume_conversation_id=None,
            artifacts_readonly_dir=artifacts_dir,
            remaining_seconds=240,
        )
    )

    validation_command = validation_process.executions[0].command
    assert validation_result_record.conversation_id == "val-thread-001"
    assert (
        validation_result_record.final_result_json
        == validation_result(
            valid=True,
        ).final_result_json
    )
    assert "--conversation-id" not in validation_command
    assert "--host-artifacts" in validation_command
    assert str(artifacts_dir) in validation_command


@pytest.mark.parametrize(
    "line",
    (
        json.dumps({"type": "turn.completed"}),
        json.dumps({"type": "turn.started"}),
        json.dumps({"type": "item.started", "item": {"type": "agent_message"}}),
        json.dumps({"type": "item.completed"}),
        json.dumps({"type": "item.completed", "item": {"type": "tool_call"}}),
        json.dumps({"type": "item.completed", "item": {"type": "agent_message"}}),
        json.dumps(
            {"type": "item.completed", "item": {"type": "agent_message", "text": "[]"}},
        ),
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": json.dumps({"message": "payloadなし"}, ensure_ascii=False),
                },
            },
            ensure_ascii=False,
        ),
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": json.dumps({"payload": {"kind": "debug"}}),
                },
            },
        ),
        json.dumps({"type": "turn.failed", "message": "実行が中断されました。"}),
        json.dumps({"type": "turn.failed", "error": {}}),
        json.dumps({"type": "error"}),
        json.dumps({"type": "experimental.event"}),
    ),
)
def test_jsonl_parser_classifies_non_final_events(line: str) -> None:
    """
    観点：JSONL parserが完了、内部、失敗、errorイベントを分類すること
    確認：回答候補でないitem.completedをfinalへ誤変換しないこと
    """
    from backend.infrastructure.codex.jsonl_event_parser import JsonlEventParser

    event = JsonlEventParser().parse_line(line)

    if event.final_payload_json is not None:
        raise AssertionError("非finalイベントをfinalとして扱っています。")


@pytest.mark.parametrize(
    "line",
    ("{not-json", "[]", json.dumps({"thread_id": "thread-001"})),
)
def test_jsonl_parser_rejects_invalid_event_lines(line: str) -> None:
    """
    観点：JSONL parserがイベント形式違反をtrace対象障害として扱うこと
    確認：壊れたJSON、トップレベル配列、type欠落をAppErrorへ変換すること
    """
    from backend.infrastructure.codex.jsonl_event_parser import JsonlEventParser

    with pytest.raises(AppError) as raised:
        JsonlEventParser().parse_line(line)

    assert raised.value.error_type is ErrorType.SYSTEM
    assert raised.value.trace is True


@pytest.mark.parametrize(
    "stdout_lines",
    (
        (
            json.dumps({"type": "thread.started", "thread_id": "gen-thread-001"}),
            json.dumps({"type": "turn.failed", "error": {"message": "生成失敗"}}),
        ),
        (
            json.dumps({"type": "thread.started", "thread_id": "gen-thread-001"}),
            json.dumps({"type": "error", "message": "stream error"}),
        ),
        (
            json.dumps({"type": "thread.started", "thread_id": "gen-thread-001"}),
            json.dumps({"type": "turn.completed"}),
        ),
    ),
)
def test_codex_runner_converts_jsonl_failure_or_missing_final_to_app_error(
    tmp_path: Path,
    stdout_lines: tuple[str, ...],
) -> None:
    """
    観点：CodexRunnerがJSONL失敗とfinal欠落を回答候補へ進めないこと
    確認：turn.failed、error、final欠落はSYSTEMかつtrace対象のAppErrorになること
    """
    from backend.infrastructure.codex.codex_runner import CodexRunner

    runner = CodexRunner(
        settings=_runner_settings(tmp_path),
        process_runner=RecordingCodexProcessRunner(
            ProcessResultRecord(0, stdout_lines),
        ),
        docker_stopper=RecordingDockerStopper(),
    )

    with pytest.raises(AppError) as raised:
        runner.run_generation(_generation_request())

    assert raised.value.error_type is ErrorType.SYSTEM
    assert raised.value.trace is True


def test_codex_runner_converts_process_failure_and_timeout_to_app_error(
    tmp_path: Path,
) -> None:
    """
    観点：CodexRunnerがプロセス境界の失敗をtrace対象障害へ変換すること
    確認：非0終了はstderrを含むAppError、timeoutはdocker stop後のAppErrorになること
    """
    from backend.infrastructure.codex.codex_runner import CodexRunner

    failed_runner = CodexRunner(
        settings=_runner_settings(tmp_path),
        process_runner=RecordingCodexProcessRunner(
            ProcessResultRecord(2, (), "docker failed"),
        ),
        docker_stopper=RecordingDockerStopper(),
    )
    with pytest.raises(AppError) as failed:
        failed_runner.run_generation(_generation_request())
    assert "docker failed" in failed.value.diagnostic_message

    stopper = RecordingDockerStopper(return_code=1)
    timeout_runner = CodexRunner(
        settings=_runner_settings(tmp_path),
        process_runner=RecordingCodexProcessRunner(
            ProcessResultRecord(0, ()),
            raise_timeout=True,
        ),
        docker_stopper=stopper,
    )
    with pytest.raises(AppError) as timed_out:
        timeout_runner.run_generation(_generation_request())
    assert timed_out.value.error_type is ErrorType.SYSTEM
    assert stopper.requests == [
        StopRequestRecord(
            container_name=f"d-concierge-generator-{RUN_ID_VALUE}",
            grace_seconds=10,
        )
    ]


@pytest.mark.parametrize(
    ("registry", "stop_return_code", "expected_status"),
    (
        (FakeRunningProcessRegistry(), 0, "not_registered"),
        (
            FakeRunningProcessRegistry(
                {RUN_ID_VALUE: RegisteredProcessRecord("container", completed=True)},
            ),
            0,
            "already_exited",
        ),
        (
            FakeRunningProcessRegistry(
                {RUN_ID_VALUE: RegisteredProcessRecord("container")},
            ),
            0,
            "sent",
        ),
        (
            FakeRunningProcessRegistry(
                {RUN_ID_VALUE: RegisteredProcessRecord("container")},
            ),
            1,
            "not_registered",
        ),
    ),
)
def test_codex_runner_cancel_classifies_process_registry(
    tmp_path: Path,
    registry: FakeRunningProcessRegistry,
    stop_return_code: int,
    expected_status: str,
) -> None:
    """
    観点：CodexRunner.cancelが登録状態とdocker stop結果を分類すること
    確認：未登録、終了済み、停止成功、停止失敗を契約どおりのstatusへ変換すること
    """
    from backend.infrastructure.codex.codex_runner import CodexRunner

    runner = CodexRunner(
        settings=_runner_settings(tmp_path),
        process_runner=RecordingCodexProcessRunner(ProcessResultRecord(0, ())),
        docker_stopper=RecordingDockerStopper(return_code=stop_return_code),
        process_registry=registry,
    )

    result = runner.cancel(RUN_ID_VALUE, trace_id="trace-f005")

    assert result.status == expected_status


def _generation_stdout() -> tuple[str, ...]:
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


def _validation_stdout() -> tuple[str, ...]:
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
        ),
        json.dumps({"type": "turn.completed"}),
    )


def _generation_request() -> CodexGenerationRequest:
    from backend.application.ports.codex.dto import CodexGenerationRequest

    return CodexGenerationRequest(
        chat_id=CHAT_ID_VALUE,
        run_id=RUN_ID_VALUE,
        user_id=F003_USER_ID,
        session_id=SESSION_ID_VALUE,
        user_instruction="ポンプ点検",
        resume_conversation_id=None,
        regeneration_instruction=None,
        remaining_seconds=300,
    )


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

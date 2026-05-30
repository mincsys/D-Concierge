import signal
import sys
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from threading import Event
from typing import IO
from uuid import UUID

import pytest

from backend.application.ports.codex.cancel_request_result import CancelRequestResult
from backend.infrastructure.codex.codex_event_kind import CodexEventKind
from backend.infrastructure.codex.codex_runner import (
    CodexProcess,
    CodexProcessOutput,
    CodexProcessTimeout,
    CodexRunner,
    CodexRunRequest,
    SubprocessCodexProcessFactory,
    _OsProcessGroupTerminator,
    _SubprocessCodexProcess,
)
from backend.infrastructure.codex.jsonl_event_parser import (
    ParsedCodexEvent,
)
from backend.infrastructure.config.models import CodexDockerConfig
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import (
    AppError,
    CodexProcessFailureError,
    CodexProviderError,
    RunTimeoutError,
)


def test_codex_runner_starts_generation_and_parses_final_message(
    tmp_path: Path,
) -> None:
    """観点：CodexRunner。確認：生成用Docker起動スクリプトを起動し、JSONLから最終候補を返す。"""
    process = CompletedProcess(
        stdout=(
            '{"type":"thread.started","thread_id":"thread-001"}\n'
            '{"type":"item.completed","item":{"type":"agent_message",'
            '"text":"{\\"markdown\\":\\"回答\\",\\"references\\":[]}"}}\n'
            '{"type":"turn.completed"}\n'
        )
    )
    factory = RecordingProcessFactory(process)
    script_path = tmp_path / "run_codex_docker.sh"
    runner = CodexRunner(process_factory=factory, script_path=script_path)

    result = runner.run_generation(
        CodexRunRequest(
            run_id=UUID("00000000-0000-0000-0000-000000000701"),
            prompt="資料を要約してください",
            codex_home=tmp_path / "codex-home",
            workdir=tmp_path / "session",
            data_source_dir=tmp_path / "data_source",
            output_schema=tmp_path / "schema.json",
            docker_config=_docker_config(codex_api_key="sk-test"),
            artifact_mount_dir=None,
            codex_conversation_id=None,
            timeout_seconds=30,
            trace_id="trace-401",
        )
    )

    assert result.codex_conversation_id == "thread-001"
    assert result.final_message == '{"markdown":"回答","references":[]}'
    assert [event.kind for event in result.events] == [
        CodexEventKind.THREAD_STARTED,
        CodexEventKind.AGENT_MESSAGE,
        CodexEventKind.TURN_COMPLETED,
    ]
    assert factory.command == (
        str(script_path),
        "--container-name",
        "d-concierge-generator-00000000-0000-0000-0000-000000000701",
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
        "--host-data-source",
        str(tmp_path / "data_source"),
        "--host-schema-dir",
        str(tmp_path),
        "--schema-file",
        "schema.json",
        "--prompt",
        "資料を要約してください",
    )
    assert factory.cwd == tmp_path / "session"
    assert factory.env["CODEX_API_KEY"] == "sk-test"


def test_codex_runner_places_resume_after_exec_options(tmp_path: Path) -> None:
    """観点：CodexRunner。確認：resume利用時は会話継続IDをスクリプト引数として渡す。"""
    process = CompletedProcess(
        stdout=(
            '{"type":"thread.started","thread_id":"thread-002"}\n'
            '{"type":"item.completed","item":{"type":"agent_message","text":"検証結果"}}\n'
            '{"type":"turn.completed"}\n'
        )
    )
    factory = RecordingProcessFactory(process)
    script_path = tmp_path / "run_codex_docker.sh"
    runner = CodexRunner(process_factory=factory, script_path=script_path)

    result = runner.run_validation(
        CodexRunRequest(
            run_id=UUID("00000000-0000-0000-0000-000000000702"),
            prompt="参照元を検証してください",
            codex_home=tmp_path / "validator-home",
            workdir=tmp_path / "validator-session",
            data_source_dir=tmp_path / "data_source",
            output_schema=tmp_path / "validator-schema.json",
            docker_config=_docker_config(),
            artifact_mount_dir=tmp_path / "artifacts",
            codex_conversation_id="thread-previous",
            timeout_seconds=30,
            trace_id="trace-402",
        )
    )

    assert result.final_message == "検証結果"
    assert factory.command is not None
    assert factory.command[:5] == (
        str(script_path),
        "--container-name",
        "d-concierge-validator-00000000-0000-0000-0000-000000000702",
        "--image",
        "codex-python-runner:latest",
    )
    assert "--host-artifacts" in factory.command
    assert str(tmp_path / "artifacts") in factory.command
    assert factory.command[-2:] == (
        "--conversation-id",
        "thread-previous",
    )


def test_codex_runner_rejects_invalid_timeout_before_starting_process(
    tmp_path: Path,
) -> None:
    """観点：CodexRunner異常系。確認：不正timeoutはプロセス起動前に拒否する。"""
    factory = RecordingProcessFactory(CompletedProcess(stdout=""))
    runner = CodexRunner(process_factory=factory)

    with pytest.raises(AppError) as error_info:
        runner.run_generation(_make_request(tmp_path, timeout_seconds=0))

    assert error_info.value.error_type is ErrorType.SYSTEM
    assert factory.command is None


def test_codex_runner_converts_process_start_and_exit_failures(
    tmp_path: Path,
) -> None:
    """観点：CodexRunner異常系。確認：起動失敗と異常終了をシステムエラーにする。"""
    with pytest.raises(AppError) as start_error:
        CodexRunner(process_factory=OSErrorProcessFactory()).run_generation(
            _make_request(tmp_path)
        )
    with pytest.raises(AppError) as exit_error:
        CodexRunner(
            process_factory=RecordingProcessFactory(
                CompletedProcess(stdout="", return_code=1)
            )
        ).run_generation(_make_request(tmp_path))

    assert start_error.value.error_type is ErrorType.SYSTEM
    assert exit_error.value.error_type is ErrorType.SYSTEM


def test_codex_runner_stops_container_when_timeout_occurs(tmp_path: Path) -> None:
    """観点：CodexRunner異常系。確認：Docker実行タイムアウト時は対象コンテナへstopを送る。"""
    process = TimeoutProcess()
    stopper = RecordingContainerStopper()
    runner = CodexRunner(
        process_factory=RecordingProcessFactory(process),
        container_stopper=stopper,
    )

    with pytest.raises(RunTimeoutError):
        runner.run_generation(_make_request(tmp_path))

    assert process.killed
    assert stopper.calls == [
        ("d-concierge-generator-00000000-0000-0000-0000-000000000799", 10)
    ]


def test_codex_runner_rejects_failed_or_incomplete_jsonl(
    tmp_path: Path,
) -> None:
    """観点：CodexRunner異常系。確認：失敗イベントと不完全JSONLを正常終了にしない。"""
    with pytest.raises(AppError) as failed_event_error:
        CodexRunner(
            process_factory=RecordingProcessFactory(
                CompletedProcess(
                    stdout=(
                        '{"type":"thread.started","thread_id":"thread-005"}\n'
                        '{"type":"error","message":"failed"}\n'
                    )
                )
            )
        ).run_generation(_make_request(tmp_path))
    with pytest.raises(AppError) as incomplete_error:
        CodexRunner(
            process_factory=RecordingProcessFactory(
                CompletedProcess(
                    stdout='{"type":"thread.started","thread_id":"thread-006"}\n'
                )
            )
        ).run_generation(_make_request(tmp_path))

    assert failed_event_error.value.error_type is ErrorType.SYSTEM
    assert incomplete_error.value.error_type is ErrorType.SYSTEM


def test_codex_runner_raises_provider_error_for_usage_limit_jsonl(
    tmp_path: Path,
) -> None:
    """観点：CodexRunner異常系。

    確認：Codex JSONLのerrorイベントをCodex側エラーとして扱い、元メッセージを保持する。
    """
    process = CompletedProcess(
        stdout=(
            '{"type":"thread.started","thread_id":"thread-limit"}\n'
            '{"type":"error","message":"You\\u0027ve hit your usage limit."}\n'
        )
    )
    stopper = RecordingContainerStopper()

    with pytest.raises(CodexProviderError) as error_info:
        CodexRunner(
            process_factory=RecordingProcessFactory(process),
            container_stopper=stopper,
        ).run_generation(
            _make_request(
                tmp_path,
                run_id=UUID("00000000-0000-0000-0000-000000000703"),
            )
        )

    assert process.terminated
    assert stopper.calls == [
        ("d-concierge-generator-00000000-0000-0000-0000-000000000703", 10)
    ]
    assert error_info.value.error_type is ErrorType.SYSTEM
    assert error_info.value.codex_event_type == "error"
    assert error_info.value.codex_message == "You've hit your usage limit."
    assert "You've hit your usage limit." in error_info.value.diagnostic_message


def test_codex_runner_raises_provider_error_for_turn_failed_jsonl(
    tmp_path: Path,
) -> None:
    """観点：CodexRunner異常系。

    確認：turn.failedのerror.messageをCodex側エラー詳細として保持する。
    """
    process = CompletedProcess(
        stdout=(
            '{"type":"thread.started","thread_id":"thread-network"}\n'
            '{"type":"turn.failed","error":{"message":"stream disconnected"}}\n'
        )
    )

    with pytest.raises(CodexProviderError) as error_info:
        CodexRunner(process_factory=RecordingProcessFactory(process)).run_generation(
            _make_request(tmp_path)
        )

    assert process.terminated
    assert error_info.value.codex_event_type == "turn.failed"
    assert error_info.value.codex_message == "stream disconnected"


def test_codex_runner_raises_process_failure_without_jsonl_error(
    tmp_path: Path,
) -> None:
    """観点：CodexRunner異常系。

    確認：JSONLエラーなしの非ゼロ終了をプロセス異常終了として扱う。
    """
    process = CompletedProcess(stdout="", stderr="fatal", return_code=1)

    with pytest.raises(CodexProcessFailureError) as error_info:
        CodexRunner(process_factory=RecordingProcessFactory(process)).run_generation(
            _make_request(tmp_path)
        )

    assert error_info.value.error_type is ErrorType.SYSTEM
    assert error_info.value.return_code == 1
    assert error_info.value.stderr == "fatal"
    assert "fatal" in error_info.value.diagnostic_message


def test_codex_runner_handles_blank_and_unknown_events(tmp_path: Path) -> None:
    """観点：CodexRunner。確認：空行と利用しないイベントを読み飛ばして最終結果を返す。"""
    runner = CodexRunner(
        process_factory=RecordingProcessFactory(
            CompletedProcess(
                stdout=(
                    "\n"
                    '{"type":"thread.started","thread_id":"thread-007"}\n'
                    '{"type":"turn.started"}\n'
                    '{"type":"item.completed","item":{"type":"agent_message","text":"結果"}}\n'
                    '{"type":"turn.completed"}\n'
                )
            )
        )
    )

    result = runner.run_generation(_make_request(tmp_path))

    assert result.codex_conversation_id == "thread-007"
    assert result.final_message == "結果"


def test_codex_runner_notifies_jsonl_events_before_process_completion(
    tmp_path: Path,
) -> None:
    """観点：CodexRunner逐次JSONL通知。

    確認：Codex Docker実行が完了する前に読み取ったJSONLイベントを呼出元へ通知する。
    """
    process = StreamingProcess(
        first_stdout_line='{"type":"thread.started","thread_id":"thread-stream"}\n',
        remaining_stdout=(
            '{"type":"item.completed","item":{"type":"agent_message","text":"結果"}}\n'
            '{"type":"turn.completed"}\n'
        ),
    )
    runner = CodexRunner(process_factory=RecordingProcessFactory(process))
    notified_events: list[CodexEventKind] = []

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            runner.run_generation,
            _make_request(
                tmp_path,
                on_event=lambda event: notified_events.append(event.kind),
            ),
        )
        process.first_line_notified.wait(timeout=1)
        assert notified_events == [CodexEventKind.THREAD_STARTED]
        process.release()

    assert future.result().final_message == "結果"
    assert notified_events == [
        CodexEventKind.THREAD_STARTED,
        CodexEventKind.AGENT_MESSAGE,
        CodexEventKind.TURN_COMPLETED,
    ]


def test_codex_runner_cancels_registered_process(tmp_path: Path) -> None:
    """観点：CodexRunner。確認：登録済み生存コンテナへ終了要求を送る。"""
    process = BlockingProcess(
        stdout=(
            '{"type":"thread.started","thread_id":"thread-004"}\n'
            '{"type":"item.completed","item":{"type":"agent_message","text":"結果"}}\n'
            '{"type":"turn.completed"}\n'
        )
    )
    stopper = RecordingContainerStopper()
    runner = CodexRunner(
        process_factory=RecordingProcessFactory(process),
        container_stopper=stopper,
    )
    run_id = UUID("00000000-0000-0000-0000-000000000704")
    request = CodexRunRequest(
        run_id=run_id,
        prompt="資料を要約してください",
        codex_home=tmp_path / "codex-home",
        workdir=tmp_path / "session",
        data_source_dir=tmp_path / "data_source",
        output_schema=tmp_path / "schema.json",
        docker_config=_docker_config(),
        artifact_mount_dir=None,
        codex_conversation_id=None,
        timeout_seconds=30,
        trace_id="trace-404",
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(runner.run_generation, request)
        process.started.wait(timeout=1)
        cancel_result = runner.cancel(run_id=run_id, trace_id="trace-405")
        process.release()

    assert cancel_result is CancelRequestResult.SENT
    assert not process.terminated
    assert stopper.calls == [
        ("d-concierge-generator-00000000-0000-0000-0000-000000000704", 10)
    ]
    assert future.result().final_message == "結果"
    assert (
        runner.cancel(run_id=run_id, trace_id="trace-406")
        is CancelRequestResult.NOT_REGISTERED
    )


def test_codex_runner_returns_not_registered_when_container_stop_fails(
    tmp_path: Path,
) -> None:
    """観点：CodexRunnerキャンセル。確認：Docker stop失敗は未登録相当として扱う。"""
    process = BlockingProcess(stdout='{"type":"thread.started","thread_id":"thread"}\n')
    stopper = RecordingContainerStopper(result=False)
    runner = CodexRunner(
        process_factory=RecordingProcessFactory(process),
        container_stopper=stopper,
    )
    request = _make_request(tmp_path)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(runner.run_generation, request)
        process.started.wait(timeout=1)
        cancel_result = runner.cancel(run_id=request.run_id, trace_id="trace-408")
        process.release()

    assert cancel_result is CancelRequestResult.NOT_REGISTERED
    assert not process.terminated
    assert stopper.calls == [
        ("d-concierge-generator-00000000-0000-0000-0000-000000000799", 10)
    ]
    with pytest.raises(AppError):
        future.result()


def test_subprocess_codex_process_streams_stdout_and_collects_stderr(
    tmp_path: Path,
) -> None:
    """観点：SubprocessCodexProcess。

    確認：標準出力行を逐次通知し、標準エラーと終了コードを完了結果へ格納する。
    """
    process = SubprocessCodexProcessFactory().start(
        (
            sys.executable,
            "-c",
            "import sys; print('line-1'); sys.stderr.write('warn')",
        ),
        tmp_path,
        {},
    )
    lines: list[str] = []

    output = process.communicate(5, on_stdout_line=lines.append)

    assert lines == ["line-1\n"]
    assert output.stdout == "line-1\n"
    assert output.stderr == "warn"
    assert output.return_code == 0


def test_subprocess_codex_process_supports_no_stdout_callback(tmp_path: Path) -> None:
    """観点：SubprocessCodexProcess。

    確認：標準出力通知先が未指定でも完了出力を取得できる。
    """
    process = SubprocessCodexProcessFactory().start(
        (sys.executable, "-c", "print('line-1')"),
        tmp_path,
        {},
    )

    output = process.communicate(5)

    assert output.stdout == "line-1\n"


def test_subprocess_codex_process_converts_wait_timeout(tmp_path: Path) -> None:
    """観点：SubprocessCodexProcess異常系。

    確認：プロセス完了待ちtimeoutをCodexProcessTimeoutへ変換する。
    """
    process = SubprocessCodexProcessFactory().start(
        (sys.executable, "-c", "import time; time.sleep(3)"),
        tmp_path,
        {},
    )

    with pytest.raises(CodexProcessTimeout):
        process.communicate(1)
    process.kill()


def test_subprocess_codex_process_converts_stdout_callback_failure(
    tmp_path: Path,
) -> None:
    """観点：SubprocessCodexProcess異常系。

    確認：標準出力通知中の失敗を呼出元へ伝える。
    """
    process = SubprocessCodexProcessFactory().start(
        (sys.executable, "-c", "print('line-1')"),
        tmp_path,
        {},
    )

    def fail_on_stdout(_line: str) -> None:
        raise ValueError("callback failed")

    with pytest.raises(RuntimeError):
        process.communicate(5, on_stdout_line=fail_on_stdout)


def test_os_process_group_terminator_uses_posix_process_group() -> None:
    """観点：CodexRunnerプロセス制御。

    確認：POSIXではプロセスグループへ終了要求と強制終了要求を送る。
    """
    killpg_calls: list[tuple[int, int]] = []
    terminator = _OsProcessGroupTerminator(
        os_name="posix",
        killpg=lambda pid, sig: killpg_calls.append((pid, sig)),
        taskkill_runner=lambda _command: 0,
    )

    terminator.terminate(1234)
    terminator.kill(1234)

    assert killpg_calls == [(1234, signal.SIGTERM), (1234, 9)]


def test_os_process_group_terminator_uses_windows_taskkill() -> None:
    """観点：CodexRunnerプロセス制御。

    確認：Windowsではtaskkillで子プロセスを含めて終了要求と強制終了要求を送る。
    """
    taskkill_calls: list[tuple[str, ...]] = []

    def record_taskkill(command: tuple[str, ...]) -> int:
        taskkill_calls.append(command)
        return 0

    terminator = _OsProcessGroupTerminator(
        os_name="nt",
        killpg=lambda _pid, _sig: None,
        taskkill_runner=record_taskkill,
    )

    terminator.terminate(1234)
    terminator.kill(1234)

    assert taskkill_calls == [
        ("taskkill", "/T", "/PID", "1234"),
        ("taskkill", "/F", "/T", "/PID", "1234"),
    ]


def test_subprocess_codex_process_falls_back_when_group_termination_fails() -> None:
    """観点：CodexRunnerプロセス制御。

    確認：OS別の子プロセス込み終了要求に失敗した場合は対象プロセス単体へfallbackする。
    """
    handle = RecordingSubprocessHandle(pid=1234)
    process = _SubprocessCodexProcess(
        handle,
        process_group_terminator=FailingProcessGroupTerminator(),
    )

    process.terminate()
    process.kill()

    assert handle.terminated is True
    assert handle.killed is True


def test_codex_runner_returns_already_exited_for_registered_exited_process(
    tmp_path: Path,
) -> None:
    """観点：CodexRunnerキャンセル。確認：登録済み終了プロセスをalready_exitedにする。"""
    runner = CodexRunner()
    run_id = UUID("00000000-0000-0000-0000-000000000705")
    runner._register_process(
        run_id,
        CompletedProcess(stdout="", return_code=0),
        "d-concierge-generator-00000000-0000-0000-0000-000000000705",
    )

    result = runner.cancel(run_id=run_id, trace_id="trace-407")

    assert result is CancelRequestResult.ALREADY_EXITED


@dataclass(slots=True)
class RecordingSubprocessHandle:
    pid: int
    stdout: IO[str] = field(default_factory=StringIO)
    stderr: IO[str] = field(default_factory=StringIO)
    returncode: int | None = None
    terminated: bool = False
    killed: bool = False

    def wait(self, timeout: int) -> int:
        _ = timeout
        self.returncode = 0
        return 0

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True


class FailingProcessGroupTerminator:
    def terminate(self, pid: int) -> None:
        _ = pid
        raise OSError("group termination failed")

    def kill(self, pid: int) -> None:
        _ = pid
        raise OSError("group kill failed")


@dataclass(slots=True)
class RecordingProcessFactory:
    process: CodexProcess
    command: tuple[str, ...] | None = None
    cwd: Path | None = None
    env: Mapping[str, str] = field(default_factory=dict)

    def start(
        self,
        command: tuple[str, ...],
        cwd: Path,
        env: Mapping[str, str],
    ) -> CodexProcess:
        self.command = command
        self.cwd = cwd
        self.env = env
        return self.process


@dataclass(slots=True)
class RecordingContainerStopper:
    calls: list[tuple[str, int]] = field(default_factory=list)
    result: bool = True

    def stop(self, container_name: str, timeout_seconds: int) -> bool:
        self.calls.append((container_name, timeout_seconds))
        return self.result


@dataclass(slots=True)
class CompletedProcess:
    stdout: str
    stderr: str = ""
    return_code: int = 0
    terminated: bool = False

    def communicate(
        self,
        timeout_seconds: int,
        on_stdout_line: Callable[[str], None] | None = None,
    ) -> CodexProcessOutput:
        _ = timeout_seconds
        if on_stdout_line is not None:
            for line in self.stdout.splitlines(keepends=True):
                on_stdout_line(line)
        return CodexProcessOutput(
            stdout=self.stdout,
            stderr=self.stderr,
            return_code=self.return_code,
        )

    def poll(self) -> int | None:
        return self.return_code

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.terminated = True


class OSErrorProcessFactory:
    def start(
        self,
        command: tuple[str, ...],
        cwd: Path,
        env: Mapping[str, str],
    ) -> CodexProcess:
        _ = (command, cwd, env)
        raise OSError("codex not found")


@dataclass(slots=True)
class TimeoutProcess:
    killed: bool = False

    def communicate(
        self,
        timeout_seconds: int,
        on_stdout_line: Callable[[str], None] | None = None,
    ) -> CodexProcessOutput:
        _ = (timeout_seconds, on_stdout_line)
        raise CodexProcessTimeout

    def poll(self) -> int | None:
        return None

    def terminate(self) -> None:
        return

    def kill(self) -> None:
        self.killed = True


@dataclass(slots=True)
class BlockingProcess:
    stdout: str
    started: Event = field(default_factory=Event)
    released: Event = field(default_factory=Event)
    terminated: bool = False

    def communicate(
        self,
        timeout_seconds: int,
        on_stdout_line: Callable[[str], None] | None = None,
    ) -> CodexProcessOutput:
        _ = timeout_seconds
        self.started.set()
        self.released.wait(timeout=1)
        if on_stdout_line is not None:
            for line in self.stdout.splitlines(keepends=True):
                on_stdout_line(line)
        return CodexProcessOutput(stdout=self.stdout, stderr="", return_code=0)

    def poll(self) -> int | None:
        return None if not self.terminated else 0

    def terminate(self) -> None:
        self.terminated = True
        self.released.set()

    def kill(self) -> None:
        self.terminated = True
        self.released.set()

    def release(self) -> None:
        self.released.set()


@dataclass(slots=True)
class StreamingProcess:
    first_stdout_line: str
    remaining_stdout: str
    first_line_notified: Event = field(default_factory=Event)
    released: Event = field(default_factory=Event)
    terminated: bool = False

    def communicate(
        self,
        timeout_seconds: int,
        on_stdout_line: Callable[[str], None] | None = None,
    ) -> CodexProcessOutput:
        _ = timeout_seconds
        if on_stdout_line is not None:
            on_stdout_line(self.first_stdout_line)
        self.first_line_notified.set()
        self.released.wait(timeout=1)
        for line in self.remaining_stdout.splitlines(keepends=True):
            if on_stdout_line is not None:
                on_stdout_line(line)
        return CodexProcessOutput(
            stdout=self.first_stdout_line + self.remaining_stdout,
            stderr="",
            return_code=0,
        )

    def poll(self) -> int | None:
        return None if not self.terminated else 0

    def terminate(self) -> None:
        self.terminated = True
        self.release()

    def kill(self) -> None:
        self.terminated = True
        self.release()

    def release(self) -> None:
        self.released.set()


def _make_request(
    tmp_path: Path,
    run_id: UUID | None = None,
    timeout_seconds: int = 30,
    on_event: Callable[[ParsedCodexEvent], None] | None = None,
) -> CodexRunRequest:
    return CodexRunRequest(
        run_id=run_id or UUID("00000000-0000-0000-0000-000000000799"),
        prompt="資料を要約してください",
        codex_home=tmp_path / "codex-home",
        workdir=tmp_path / "session",
        data_source_dir=tmp_path / "data_source",
        output_schema=tmp_path / "schema.json",
        docker_config=_docker_config(),
        artifact_mount_dir=None,
        codex_conversation_id=None,
        timeout_seconds=timeout_seconds,
        trace_id="trace-499",
        on_event=on_event,
    )


def _docker_config(codex_api_key: str = "") -> CodexDockerConfig:
    return CodexDockerConfig(
        image="codex-python-runner:latest",
        workspace_dir="/workspace",
        codex_home_dir="/home/codex/.codex",
        codex_api_key=codex_api_key,
    )

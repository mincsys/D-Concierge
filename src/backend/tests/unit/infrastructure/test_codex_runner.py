import sys
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from uuid import UUID

import pytest

from backend.infrastructure.codex.codex_runner import (
    CodexProcess,
    CodexProcessOutput,
    CodexProcessTimeout,
    CodexRunner,
    CodexRunRequest,
    SubprocessCodexProcessFactory,
)
from backend.infrastructure.codex.jsonl_event_parser import ParsedCodexEvent
from backend.shared.errors import AppError, ErrorClass, RunTimeoutError


def test_codex_runner_starts_generation_and_parses_final_message(
    tmp_path: Path,
) -> None:
    """観点：CodexRunner。確認：生成用codex execを起動し、JSONLから最終候補を返す。"""
    process = CompletedProcess(
        stdout=(
            '{"type":"thread.started","thread_id":"thread-001"}\n'
            '{"type":"item.completed","item":{"type":"agent_message",'
            '"text":"{\\"markdown\\":\\"回答\\",\\"references\\":[]}"}}\n'
            '{"type":"turn.completed"}\n'
        )
    )
    factory = RecordingProcessFactory(process)
    runner = CodexRunner(process_factory=factory)

    result = runner.run_generation(
        CodexRunRequest(
            run_id=UUID("00000000-0000-0000-0000-000000000701"),
            prompt="資料を要約してください",
            codex_home=tmp_path / "codex-home",
            workdir=tmp_path / "session",
            output_schema=tmp_path / "schema.json",
            codex_conversation_id=None,
            timeout_seconds=30,
            trace_id="trace-401",
        )
    )

    assert result.codex_conversation_id == "thread-001"
    assert result.final_message == '{"markdown":"回答","references":[]}'
    assert [event.kind for event in result.events] == [
        "thread_started",
        "agent_message",
        "turn_completed",
    ]
    assert factory.command == (
        "codex",
        "exec",
        "--json",
        "--output-schema",
        str(tmp_path / "schema.json"),
        "-C",
        str(tmp_path / "session"),
        "資料を要約してください",
    )
    assert factory.cwd == tmp_path / "session"
    assert factory.env["CODEX_HOME"] == str(tmp_path / "codex-home")


def test_codex_runner_places_resume_after_exec_options(tmp_path: Path) -> None:
    """観点：CodexRunner。確認：resume利用時もexecオプションをresumeより前に指定する。"""
    process = CompletedProcess(
        stdout=(
            '{"type":"thread.started","thread_id":"thread-002"}\n'
            '{"type":"item.completed","item":{"type":"agent_message","text":"検証結果"}}\n'
            '{"type":"turn.completed"}\n'
        )
    )
    factory = RecordingProcessFactory(process)
    runner = CodexRunner(process_factory=factory)

    result = runner.run_validation(
        CodexRunRequest(
            run_id=UUID("00000000-0000-0000-0000-000000000702"),
            prompt="参照元を検証してください",
            codex_home=tmp_path / "validator-home",
            workdir=tmp_path / "validator-session",
            output_schema=tmp_path / "validator-schema.json",
            codex_conversation_id="thread-previous",
            timeout_seconds=30,
            trace_id="trace-402",
        )
    )

    assert result.final_message == "検証結果"
    assert factory.command is not None
    assert factory.command.index("resume") > factory.command.index("-C")
    assert factory.command[-3:] == (
        "resume",
        "thread-previous",
        "参照元を検証してください",
    )


def test_codex_runner_rejects_invalid_timeout_before_starting_process(
    tmp_path: Path,
) -> None:
    """観点：CodexRunner異常系。確認：不正timeoutはプロセス起動前に拒否する。"""
    factory = RecordingProcessFactory(CompletedProcess(stdout=""))
    runner = CodexRunner(process_factory=factory)

    with pytest.raises(AppError) as error_info:
        runner.run_generation(_make_request(tmp_path, timeout_seconds=0))

    assert error_info.value.error_class is ErrorClass.SYSTEM
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

    assert start_error.value.error_class is ErrorClass.SYSTEM
    assert exit_error.value.error_class is ErrorClass.SYSTEM


def test_codex_runner_kills_process_when_timeout_occurs(tmp_path: Path) -> None:
    """観点：CodexRunner異常系。確認：codex execタイムアウト時はプロセスをkillする。"""
    process = TimeoutProcess()
    runner = CodexRunner(process_factory=RecordingProcessFactory(process))

    with pytest.raises(RunTimeoutError):
        runner.run_generation(_make_request(tmp_path))

    assert process.killed


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

    assert failed_event_error.value.error_class is ErrorClass.SYSTEM
    assert incomplete_error.value.error_class is ErrorClass.SYSTEM


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

    確認：codex execが完了する前に読み取ったJSONLイベントを呼出元へ通知する。
    """
    process = StreamingProcess(
        first_stdout_line='{"type":"thread.started","thread_id":"thread-stream"}\n',
        remaining_stdout=(
            '{"type":"item.completed","item":{"type":"agent_message","text":"結果"}}\n'
            '{"type":"turn.completed"}\n'
        ),
    )
    runner = CodexRunner(process_factory=RecordingProcessFactory(process))
    notified_events: list[str] = []

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            runner.run_generation,
            _make_request(
                tmp_path,
                on_event=lambda event: notified_events.append(event.kind),
            ),
        )
        process.first_line_notified.wait(timeout=1)
        assert notified_events == ["thread_started"]
        process.release()

    assert future.result().final_message == "結果"
    assert notified_events == ["thread_started", "agent_message", "turn_completed"]


def test_codex_runner_cancels_registered_process(tmp_path: Path) -> None:
    """観点：CodexRunner。確認：登録済み生存プロセスへ終了要求を送る。"""
    process = BlockingProcess(
        stdout=(
            '{"type":"thread.started","thread_id":"thread-004"}\n'
            '{"type":"item.completed","item":{"type":"agent_message","text":"結果"}}\n'
            '{"type":"turn.completed"}\n'
        )
    )
    runner = CodexRunner(process_factory=RecordingProcessFactory(process))
    run_id = UUID("00000000-0000-0000-0000-000000000704")
    request = CodexRunRequest(
        run_id=run_id,
        prompt="資料を要約してください",
        codex_home=tmp_path / "codex-home",
        workdir=tmp_path / "session",
        output_schema=tmp_path / "schema.json",
        codex_conversation_id=None,
        timeout_seconds=30,
        trace_id="trace-404",
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(runner.run_generation, request)
        process.started.wait(timeout=1)
        cancel_result = runner.cancel(run_id=run_id, trace_id="trace-405")

    assert cancel_result == "sent"
    assert process.terminated
    assert future.result().final_message == "結果"
    assert runner.cancel(run_id=run_id, trace_id="trace-406") == "not_registered"


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


def test_codex_runner_returns_already_exited_for_registered_exited_process(
    tmp_path: Path,
) -> None:
    """観点：CodexRunnerキャンセル。確認：登録済み終了プロセスをalready_exitedにする。"""
    runner = CodexRunner()
    run_id = UUID("00000000-0000-0000-0000-000000000705")
    runner._register_process(run_id, CompletedProcess(stdout="", return_code=0))

    result = runner.cancel(run_id=run_id, trace_id="trace-407")

    assert result == "already_exited"


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
class CompletedProcess:
    stdout: str
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
            stderr="",
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
    timeout_seconds: int = 30,
    on_event: Callable[[ParsedCodexEvent], None] | None = None,
) -> CodexRunRequest:
    return CodexRunRequest(
        run_id=UUID("00000000-0000-0000-0000-000000000799"),
        prompt="資料を要約してください",
        codex_home=tmp_path / "codex-home",
        workdir=tmp_path / "session",
        output_schema=tmp_path / "schema.json",
        codex_conversation_id=None,
        timeout_seconds=timeout_seconds,
        trace_id="trace-499",
        on_event=on_event,
    )

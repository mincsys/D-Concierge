import os
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import RLock, Thread
from typing import Literal, Protocol
from uuid import UUID

from backend.infrastructure.codex.jsonl_event_parser import (
    JsonlEventParser,
    JsonlParseError,
    ParsedCodexEvent,
)
from backend.shared.errors import AppError, ErrorClass, RunTimeoutError

CancelResult = Literal["sent", "already_exited", "not_registered"]


class CodexProcessTimeout(Exception):
    """codex execプロセスが指定時間内に終了しなかったことを示す。"""


@dataclass(frozen=True, slots=True)
class CodexProcessOutput:
    """codex execプロセスの完了出力。"""

    stdout: str
    stderr: str
    return_code: int


class CodexProcess(Protocol):
    """CodexRunnerが制御するOSプロセス境界。"""

    def communicate(
        self,
        timeout_seconds: int,
        on_stdout_line: Callable[[str], None] | None = None,
    ) -> CodexProcessOutput:
        """プロセス完了まで待ち、標準出力行を必要に応じて通知する。"""
        ...

    def poll(self) -> int | None:
        """終了済みなら終了コード、生存中ならNoneを返す。"""

    def terminate(self) -> None:
        """プロセスへ通常終了要求を送る。"""

    def kill(self) -> None:
        """プロセスへ強制終了要求を送る。"""


class CodexProcessFactory(Protocol):
    """codex execプロセス生成境界。"""

    def start(
        self,
        command: tuple[str, ...],
        cwd: Path,
        env: Mapping[str, str],
    ) -> CodexProcess:
        """指定コマンドでcodex execプロセスを起動する。"""


@dataclass(frozen=True, slots=True)
class CodexRunRequest:
    """codex exec起動要求。"""

    run_id: UUID
    prompt: str
    codex_home: Path
    workdir: Path
    output_schema: Path
    codex_conversation_id: str | None
    timeout_seconds: int
    trace_id: str
    on_event: Callable[[ParsedCodexEvent], None] | None = None


@dataclass(frozen=True, slots=True)
class CodexRunResult:
    """codex exec正常完了結果。"""

    events: tuple[ParsedCodexEvent, ...]
    final_message: str
    codex_conversation_id: str


class CodexRunner:
    """codex execを起動し、JSONLと最終出力を検証して返す。"""

    def __init__(
        self,
        process_factory: CodexProcessFactory | None = None,
    ) -> None:
        self._process_factory = (
            process_factory
            if process_factory is not None
            else SubprocessCodexProcessFactory()
        )
        self._running_processes: dict[UUID, CodexProcess] = {}
        self._lock = RLock()

    def run_generation(self, request: CodexRunRequest) -> CodexRunResult:
        """生成用codex execを起動する。"""
        return self._run(request)

    def run_validation(self, request: CodexRunRequest) -> CodexRunResult:
        """検証用codex execを起動する。"""
        return self._run(request)

    def cancel(self, run_id: UUID, trace_id: str) -> CancelResult:
        """実行中codex execへ終了要求を送る。"""
        _ = trace_id
        with self._lock:
            process = self._running_processes.get(run_id)
            if process is None:
                return "not_registered"
            if process.poll() is not None:
                self._running_processes.pop(run_id, None)
                return "already_exited"
            process.terminate()
            return "sent"

    def _run(self, request: CodexRunRequest) -> CodexRunResult:
        if request.timeout_seconds <= 0:
            raise AppError(ErrorClass.SYSTEM, "Codex実行時間が不正です。")

        _ = request.trace_id
        request.workdir.mkdir(parents=True, exist_ok=True)
        command = _build_command(request)
        env = {"CODEX_HOME": str(request.codex_home)}
        try:
            process = self._process_factory.start(command, request.workdir, env)
        except OSError as exc:
            raise AppError(
                ErrorClass.SYSTEM, "Codex実行を開始できませんでした。"
            ) from exc

        self._register_process(request.run_id, process)
        try:
            events: list[ParsedCodexEvent] = []

            def handle_stdout_line(line: str) -> None:
                event = _parse_stdout_line(line)
                if event is None:
                    return
                events.append(event)
                if request.on_event is not None:
                    request.on_event(event)

            try:
                output = process.communicate(
                    request.timeout_seconds,
                    on_stdout_line=handle_stdout_line,
                )
            except JsonlParseError as exc:
                raise AppError(
                    ErrorClass.SYSTEM, "Codex出力を解析できませんでした。"
                ) from exc
            if output.return_code != 0:
                raise AppError(ErrorClass.SYSTEM, "Codex実行が失敗しました。")
            return _to_run_result(events)
        except CodexProcessTimeout as exc:
            process.kill()
            raise RunTimeoutError from exc
        finally:
            self._release_process(request.run_id, process)

    def _register_process(self, run_id: UUID, process: CodexProcess) -> None:
        with self._lock:
            self._running_processes[run_id] = process

    def _release_process(self, run_id: UUID, process: CodexProcess) -> None:
        with self._lock:
            if self._running_processes.get(run_id) is process:
                self._running_processes.pop(run_id, None)


class SubprocessCodexProcessFactory:
    """標準subprocessでcodex execを起動するプロセスファクトリ。"""

    def start(
        self,
        command: tuple[str, ...],
        cwd: Path,
        env: Mapping[str, str],
    ) -> CodexProcess:
        process_env = os.environ.copy()
        process_env.update(env)
        process = subprocess.Popen(
            list(command),
            cwd=cwd,
            env=process_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return _SubprocessCodexProcess(process)


class _SubprocessCodexProcess:
    def __init__(self, process: subprocess.Popen[str]) -> None:
        self._process = process

    def communicate(
        self,
        timeout_seconds: int,
        on_stdout_line: Callable[[str], None] | None = None,
    ) -> CodexProcessOutput:
        callback = on_stdout_line if on_stdout_line is not None else lambda _line: None
        return self._communicate_streaming(timeout_seconds, callback)

    def _communicate_streaming(
        self,
        timeout_seconds: int,
        on_stdout_line: Callable[[str], None],
    ) -> CodexProcessOutput:
        stdout_lines: list[str] = []
        stderr_chunks: list[str] = []
        reader_errors: list[BaseException] = []
        stdout_pipe = self._process.stdout
        stderr_pipe = self._process.stderr
        assert stdout_pipe is not None
        assert stderr_pipe is not None

        def read_stdout() -> None:
            try:
                for line in stdout_pipe:
                    stdout_lines.append(line)
                    on_stdout_line(line)
            except BaseException as exc:  # noqa: BLE001
                reader_errors.append(exc)
                self._process.terminate()

        def read_stderr() -> None:
            try:
                stderr_chunks.append(stderr_pipe.read())
            except BaseException as exc:  # noqa: BLE001
                reader_errors.append(exc)
                self._process.terminate()

        stdout_thread = Thread(target=read_stdout, daemon=True)
        stderr_thread = Thread(target=read_stderr, daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        try:
            self._process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            raise CodexProcessTimeout from exc

        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
        if reader_errors:
            raise RuntimeError(
                "Codex出力読込中にエラーが発生しました。"
            ) from reader_errors[0]

        return CodexProcessOutput(
            stdout="".join(stdout_lines),
            stderr="".join(stderr_chunks),
            return_code=self._process.returncode,
        )

    def poll(self) -> int | None:
        return self._process.poll()

    def terminate(self) -> None:
        self._process.terminate()

    def kill(self) -> None:
        self._process.kill()


def _build_command(request: CodexRunRequest) -> tuple[str, ...]:
    command = (
        "codex",
        "exec",
        "--json",
        "--output-schema",
        str(request.output_schema),
        "-C",
        str(request.workdir),
    )
    if request.codex_conversation_id is None:
        return (*command, request.prompt)
    return (*command, "resume", request.codex_conversation_id, request.prompt)


def _parse_stdout_line(line: str) -> ParsedCodexEvent | None:
    if line.strip() == "":
        return None
    return JsonlEventParser.parse_line(line)


def _to_run_result(events: list[ParsedCodexEvent]) -> CodexRunResult:
    codex_conversation_id: str | None = None
    latest_agent_message: str | None = None
    final_message: str | None = None
    for event in events:
        match event.kind:
            case "thread_started":
                codex_conversation_id = event.thread_id
            case "agent_message":
                latest_agent_message = event.text
            case "turn_completed":
                final_message = latest_agent_message
            case "turn_failed" | "error":
                raise AppError(ErrorClass.SYSTEM, "Codex実行が失敗しました。")
            case _:
                continue

    if codex_conversation_id is None or final_message is None:
        raise AppError(ErrorClass.SYSTEM, "Codex最終出力が不正です。")

    return CodexRunResult(
        events=tuple(events),
        final_message=final_message,
        codex_conversation_id=codex_conversation_id,
    )

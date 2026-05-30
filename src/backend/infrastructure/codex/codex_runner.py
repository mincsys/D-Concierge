import os
import signal
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import RLock, Thread
from typing import IO, Protocol
from uuid import UUID

from backend.application.ports.codex.cancel_request_result import CancelRequestResult
from backend.infrastructure.codex.codex_event_kind import CodexEventKind
from backend.infrastructure.codex.jsonl_event_parser import (
    JsonlEventParser,
    JsonlParseError,
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

CancelResult = CancelRequestResult
_WINDOWS_CREATE_NEW_PROCESS_GROUP = 0x00000200
_POSIX_SIGKILL = 9
_DOCKER_STOP_TIMEOUT_SECONDS = 10


class CodexProcessTimeout(Exception):
    """Codex Docker起動プロセスが指定時間内に終了しなかったことを示す。"""


@dataclass(frozen=True, slots=True)
class CodexProcessOutput:
    """Codex Docker起動プロセスの完了出力。"""

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
    """Codex Docker起動プロセス生成境界。"""

    def start(
        self,
        command: tuple[str, ...],
        cwd: Path,
        env: Mapping[str, str],
    ) -> CodexProcess:
        """指定コマンドでCodex Docker起動プロセスを開始する。"""


class SubprocessHandle(Protocol):
    """標準subprocessハンドルのうちCodexProcessが利用する操作。"""

    @property
    def pid(self) -> int:
        """プロセスID。"""

    @property
    def stdout(self) -> IO[str] | None:
        """標準出力pipe。"""

    @property
    def stderr(self) -> IO[str] | None:
        """標準エラーpipe。"""

    @property
    def returncode(self) -> int | None:
        """終了コード。"""

    def wait(self, timeout: int) -> int:
        """プロセス終了まで待つ。"""

    def poll(self) -> int | None:
        """終了済みなら終了コード、生存中ならNoneを返す。"""

    def terminate(self) -> None:
        """対象プロセス単体へ通常終了要求を送る。"""

    def kill(self) -> None:
        """対象プロセス単体へ強制終了要求を送る。"""


class ProcessGroupTerminator(Protocol):
    """OS別のプロセスツリー終了境界。"""

    def terminate(self, pid: int) -> None:
        """子プロセスを含む通常終了要求を送る。"""

    def kill(self, pid: int) -> None:
        """子プロセスを含む強制終了要求を送る。"""


class ContainerStopper(Protocol):
    """Dockerコンテナ終了要求境界。"""

    def stop(self, container_name: str, timeout_seconds: int) -> bool:
        """対象コンテナへ終了要求を送り、終了要求が成功した場合はTrueを返す。"""
        ...


@dataclass(frozen=True, slots=True)
class CodexRunRequest:
    """Codex Docker実行要求。"""

    run_id: UUID
    prompt: str
    codex_home: Path
    workdir: Path
    data_source_dir: Path
    output_schema: Path
    docker_config: CodexDockerConfig
    artifact_mount_dir: Path | None
    codex_conversation_id: str | None
    timeout_seconds: int
    trace_id: str
    on_event: Callable[[ParsedCodexEvent], None] | None = None


@dataclass(frozen=True, slots=True)
class CodexRunResult:
    """Codex Docker実行の正常完了結果。"""

    events: tuple[ParsedCodexEvent, ...]
    final_message: str
    codex_conversation_id: str


@dataclass(frozen=True, slots=True)
class _RunningProcess:
    process: CodexProcess
    container_name: str


class CodexRunner:
    """Codex実行コンテナを起動し、JSONLと最終出力を検証して返す。"""

    def __init__(
        self,
        process_factory: CodexProcessFactory | None = None,
        script_path: Path | None = None,
        container_stopper: ContainerStopper | None = None,
    ) -> None:
        self._process_factory = (
            process_factory
            if process_factory is not None
            else SubprocessCodexProcessFactory()
        )
        self._script_path = (
            script_path
            if script_path is not None
            else Path(__file__).with_name("run_codex_docker.sh")
        )
        self._container_stopper = (
            container_stopper
            if container_stopper is not None
            else DockerContainerStopper()
        )
        self._running_processes: dict[UUID, _RunningProcess] = {}
        self._lock = RLock()

    def run_generation(self, request: CodexRunRequest) -> CodexRunResult:
        """生成用Codex Docker実行を開始する。"""
        return self._run(request, stage="generation")

    def run_validation(self, request: CodexRunRequest) -> CodexRunResult:
        """検証用Codex Docker実行を開始する。"""
        return self._run(request, stage="validation")

    def cancel(self, run_id: UUID, trace_id: str) -> CancelResult:
        """実行中Codexコンテナへ終了要求を送る。"""
        _ = trace_id
        with self._lock:
            running_process = self._running_processes.get(run_id)
            if running_process is None:
                return CancelRequestResult.NOT_REGISTERED
            if running_process.process.poll() is not None:
                self._running_processes.pop(run_id, None)
                return CancelRequestResult.ALREADY_EXITED
            stopped = self._container_stopper.stop(
                running_process.container_name,
                _DOCKER_STOP_TIMEOUT_SECONDS,
            )
            if not stopped:
                return CancelRequestResult.NOT_REGISTERED
            return CancelRequestResult.SENT

    def _run(self, request: CodexRunRequest, stage: str) -> CodexRunResult:
        if request.timeout_seconds <= 0:
            raise _codex_system_error("Codex実行時間が不正です。")

        _ = request.trace_id
        request.workdir.mkdir(parents=True, exist_ok=True)
        container_name = _container_name(stage, request.run_id)
        command = _build_command(
            request=request,
            script_path=self._script_path,
            container_name=container_name,
        )
        env = {"CODEX_API_KEY": request.docker_config.codex_api_key}
        try:
            process = self._process_factory.start(command, request.workdir, env)
        except OSError as exc:
            raise _codex_system_error("Codex実行を開始できませんでした。", exc) from exc

        self._register_process(request.run_id, process, container_name)
        try:
            events: list[ParsedCodexEvent] = []

            def handle_stdout_line(line: str) -> None:
                event = _parse_stdout_line(line)
                if event is None:
                    return
                events.append(event)
                if event.kind in {CodexEventKind.ERROR, CodexEventKind.TURN_FAILED}:
                    self._container_stopper.stop(
                        container_name,
                        _DOCKER_STOP_TIMEOUT_SECONDS,
                    )
                    process.terminate()
                    raise _codex_provider_error(event, stage)
                if request.on_event is not None:
                    request.on_event(event)

            try:
                output = process.communicate(
                    request.timeout_seconds,
                    on_stdout_line=handle_stdout_line,
                )
            except JsonlParseError as exc:
                raise _codex_system_error(
                    "Codex出力を解析できませんでした。", exc
                ) from exc
            if output.return_code != 0:
                raise CodexProcessFailureError(
                    return_code=output.return_code,
                    stderr=output.stderr,
                    stage=stage,
                )
            return _to_run_result(events, stage)
        except CodexProcessTimeout as exc:
            self._container_stopper.stop(
                container_name,
                _DOCKER_STOP_TIMEOUT_SECONDS,
            )
            process.kill()
            raise RunTimeoutError from exc
        finally:
            self._release_process(request.run_id, process)

    def _register_process(
        self,
        run_id: UUID,
        process: CodexProcess,
        container_name: str,
    ) -> None:
        with self._lock:
            self._running_processes[run_id] = _RunningProcess(
                process=process,
                container_name=container_name,
            )

    def _release_process(self, run_id: UUID, process: CodexProcess) -> None:
        with self._lock:
            running_process = self._running_processes.get(run_id)
            if running_process is not None and running_process.process is process:
                self._running_processes.pop(run_id, None)


class SubprocessCodexProcessFactory:
    """標準subprocessでCodex Docker起動スクリプトを起動するプロセスファクトリ。"""

    def start(
        self,
        command: tuple[str, ...],
        cwd: Path,
        env: Mapping[str, str],
    ) -> CodexProcess:
        process_env = os.environ.copy()
        process_env.update(env)
        if os.name == "nt":
            process = subprocess.Popen(
                list(command),
                cwd=cwd,
                env=process_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=_WINDOWS_CREATE_NEW_PROCESS_GROUP,
            )
        else:
            process = subprocess.Popen(
                list(command),
                cwd=cwd,
                env=process_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
        return _SubprocessCodexProcess(process)


class DockerContainerStopper:
    """Docker CLIで実行中コンテナへ終了要求を送る。"""

    def stop(self, container_name: str, timeout_seconds: int) -> bool:
        try:
            completed = subprocess.run(
                (
                    "docker",
                    "stop",
                    "-t",
                    str(timeout_seconds),
                    container_name,
                ),
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            return False
        return completed.returncode == 0


def _kill_process_group(pid: int, sig: int) -> None:
    if not hasattr(os, "killpg"):
        raise OSError("process group termination is not supported")
    os.killpg(pid, sig)


@dataclass(frozen=True, slots=True)
class _OsProcessGroupTerminator:
    """OS別に子プロセスを含む終了要求を送る。"""

    os_name: str = os.name
    killpg: Callable[[int, int], None] = _kill_process_group
    taskkill_runner: Callable[[tuple[str, ...]], int] | None = None

    def terminate(self, pid: int) -> None:
        if self.os_name == "nt":
            self._run_taskkill(("taskkill", "/T", "/PID", str(pid)))
            return
        self.killpg(pid, signal.SIGTERM)

    def kill(self, pid: int) -> None:
        if self.os_name == "nt":
            self._run_taskkill(("taskkill", "/F", "/T", "/PID", str(pid)))
            return
        self.killpg(pid, _POSIX_SIGKILL)

    def _run_taskkill(self, command: tuple[str, ...]) -> None:
        runner = self.taskkill_runner or _run_taskkill_command
        exit_code = runner(command)
        if exit_code != 0:
            raise OSError(f"taskkill failed: {exit_code}")


def _run_taskkill_command(command: tuple[str, ...]) -> int:
    completed = subprocess.run(
        list(command),
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return completed.returncode


class _SubprocessCodexProcess:
    def __init__(
        self,
        process: SubprocessHandle,
        process_group_terminator: ProcessGroupTerminator | None = None,
    ) -> None:
        self._process = process
        self._process_group_terminator = (
            process_group_terminator
            if process_group_terminator is not None
            else _OsProcessGroupTerminator()
        )

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
            first_error = reader_errors[0]
            if isinstance(first_error, JsonlParseError | CodexProviderError):
                raise first_error
            raise RuntimeError(
                "Codex出力読込中にエラーが発生しました。"
            ) from first_error

        return CodexProcessOutput(
            stdout="".join(stdout_lines),
            stderr="".join(stderr_chunks),
            return_code=_completed_return_code(self._process),
        )

    def poll(self) -> int | None:
        return self._process.poll()

    def terminate(self) -> None:
        try:
            self._process_group_terminator.terminate(self._process.pid)
        except OSError:
            self._process.terminate()

    def kill(self) -> None:
        try:
            self._process_group_terminator.kill(self._process.pid)
        except OSError:
            self._process.kill()


def _build_command(
    *,
    request: CodexRunRequest,
    script_path: Path,
    container_name: str,
) -> tuple[str, ...]:
    command: tuple[str, ...] = (
        str(script_path),
        "--container-name",
        container_name,
        "--image",
        request.docker_config.image,
        "--workspace-dir",
        request.docker_config.workspace_dir,
        "--codex-home-dir",
        request.docker_config.codex_home_dir,
        "--host-codex-home",
        str(request.codex_home),
        "--host-workdir",
        str(request.workdir),
        "--host-data-source",
        str(request.data_source_dir),
        "--host-schema-dir",
        str(request.output_schema.parent),
        "--schema-file",
        request.output_schema.name,
    )
    if request.artifact_mount_dir is not None:
        command = (
            *command,
            "--host-artifacts",
            str(request.artifact_mount_dir),
        )
    command = (*command, "--prompt", request.prompt)
    if request.codex_conversation_id is None:
        return command
    return (*command, "--conversation-id", request.codex_conversation_id)


def _container_name(stage: str, run_id: UUID) -> str:
    if stage == "validation":
        return f"d-concierge-validator-{run_id}"
    return f"d-concierge-generator-{run_id}"


def _completed_return_code(process: SubprocessHandle) -> int:
    if process.returncode is None:
        raise RuntimeError("Codexプロセスの終了コードを取得できません。")
    return process.returncode


def _parse_stdout_line(line: str) -> ParsedCodexEvent | None:
    if line.strip() == "":
        return None
    return JsonlEventParser.parse_line(line)


def _to_run_result(events: list[ParsedCodexEvent], stage: str) -> CodexRunResult:
    codex_conversation_id: str | None = None
    latest_agent_message: str | None = None
    final_message: str | None = None
    for event in events:
        match event.kind:
            case CodexEventKind.THREAD_STARTED:
                codex_conversation_id = event.thread_id
            case CodexEventKind.AGENT_MESSAGE:
                latest_agent_message = event.text
            case CodexEventKind.TURN_COMPLETED:
                final_message = latest_agent_message
            case CodexEventKind.TURN_FAILED | CodexEventKind.ERROR:
                raise _codex_provider_error(event, stage)
            case _:
                continue

    if codex_conversation_id is None or final_message is None:
        raise _codex_system_error("Codex最終出力が不正です。")

    return CodexRunResult(
        events=tuple(events),
        final_message=final_message,
        codex_conversation_id=codex_conversation_id,
    )


def _codex_provider_error(event: ParsedCodexEvent, stage: str) -> CodexProviderError:
    return CodexProviderError(
        event_type=event.event_type,
        message=event.message,
        stage=stage,
    )


def _codex_system_error(
    diagnostic_message: str, cause: Exception | None = None
) -> AppError:
    return AppError(
        ErrorType.SYSTEM,
        trace=True,
        diagnostic_message=diagnostic_message,
        cause=cause,
    )

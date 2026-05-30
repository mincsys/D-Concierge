from dataclasses import dataclass, field
from pathlib import Path

from backend.application.ports.codex.dto import CodexRunResult
from backend.infrastructure.codex.codex_event_kind import CodexEventKind
from backend.infrastructure.codex.codex_runner import (
    CodexRunRequest,
)
from backend.infrastructure.codex.codex_runner import (
    CodexRunResult as InfrastructureCodexRunResult,
)
from backend.infrastructure.codex.generation_runner import (
    CodexGenerationRunnerAdapter,
)
from backend.infrastructure.codex.intermediate_messages import (
    CodexIntermediateMessageStreamer,
)
from backend.infrastructure.codex.jsonl_event_parser import (
    ParsedCodexEvent,
)
from backend.infrastructure.config.models import CodexDockerConfig, GeneratorConfig
from backend.tests.support.memory_repository import InMemoryChatRepository
from backend.tests.support.transaction_manager import NoopTransactionManager


def test_codex_generation_runner_builds_request_and_saves_resume_id(
    tmp_path: Path,
) -> None:
    """観点：Codex生成実行アダプタ。

    確認：チャットの作業領域IDと生成用resume IDを使い、CodexRunner結果へ変換する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("初回")
    repository.save_generation_conversation_id(accepted.chat_id, "previous-thread")
    codex_runner = RecordingCodexRunner(
        result=InfrastructureCodexRunResult(
            events=(
                ParsedCodexEvent(
                    kind=CodexEventKind.THREAD_STARTED,
                    event_type="thread.started",
                    thread_id="next-thread",
                ),
                ParsedCodexEvent(
                    kind=CodexEventKind.AGENT_MESSAGE,
                    event_type="item.completed",
                    text='{"payload":{"kind":"progress","text":"資料を検索しています。"}}',
                ),
                ParsedCodexEvent(
                    kind=CodexEventKind.AGENT_MESSAGE,
                    event_type="item.completed",
                    text='{"payload":{"kind":"final","answers":[{"text":"回答","references":[]}]}}',
                ),
                ParsedCodexEvent(
                    kind=CodexEventKind.TURN_COMPLETED, event_type="turn.completed"
                ),
            ),
            final_message='{"payload":{"kind":"final","answers":[{"text":"回答","references":[]}]}}',
            codex_conversation_id="next-thread",
        )
    )
    data_source_dir = tmp_path / "data_source"
    data_source_dir.mkdir()
    adapter = CodexGenerationRunnerAdapter(
        repository=repository,
        codex_runner=codex_runner,
        generator_config=GeneratorConfig(
            max_retries=2,
            home=tmp_path / "codex/.codex",
            workdir=tmp_path / "codex/sessions",
            output_schema=tmp_path / "schema.json",
            saved_artifacts_dir=tmp_path / "codex/saved_artifacts",
        ),
        codex_docker_config=_docker_config(),
        data_source_dir=data_source_dir,
        timeout_seconds=300,
        transaction_manager=NoopTransactionManager(),
    )

    result = adapter.run_generation(
        accepted.chat_id,
        accepted.run_id,
        "<ユーザ指示>\n資料を要約してください\n</ユーザ指示>",
        timeout_seconds=45,
        trace_id="trace-701",
    )
    saved_context = repository.get_chat_runtime_context(accepted.chat_id)

    assert result == CodexRunResult(
        conversation_id="next-thread",
        intermediate_messages=("資料を検索しています。",),
        final_answer_json='{"payload":{"kind":"final","answers":[{"text":"回答","references":[]}]}}',
    )
    assert saved_context.generation_conversation_id == "next-thread"
    assert codex_runner.requests[0].run_id == accepted.run_id
    assert codex_runner.requests[0].prompt == (
        "<ユーザ指示>\n資料を要約してください\n</ユーザ指示>"
    )
    assert codex_runner.requests[0].codex_conversation_id == "previous-thread"
    assert codex_runner.requests[0].codex_home == tmp_path / "codex/.codex"
    assert codex_runner.requests[0].output_schema == tmp_path / "schema.json"
    assert codex_runner.requests[0].data_source_dir == data_source_dir
    assert codex_runner.requests[0].docker_config == _docker_config()
    assert codex_runner.requests[0].artifact_mount_dir is None
    assert codex_runner.requests[0].workdir == (
        tmp_path
        / "codex/sessions"
        / saved_context.user_id
        / str(saved_context.session_id)
    )
    assert codex_runner.requests[0].timeout_seconds == 45
    assert codex_runner.requests[0].trace_id == "trace-701"


def test_codex_generation_runner_prepares_data_source_mount(
    tmp_path: Path,
) -> None:
    """観点：Codex生成実行アダプタ。

    確認：生成用セッションdata_sourceへ共有データソースを提示してから起動する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("初回")
    data_source_dir = tmp_path / "data_source"
    data_source_dir.mkdir()
    (data_source_dir / "manual.pdf").write_bytes(b"%PDF-1.4\n")
    (data_source_dir / "nested").mkdir()
    (data_source_dir / "nested" / "appendix.pdf").write_bytes(b"%PDF-1.4\n")
    codex_runner = RecordingCodexRunner(
        result=InfrastructureCodexRunResult(
            events=(),
            final_message='{"payload":{"kind":"final","answers":[{"text":"回答","references":[]}]}}',
            codex_conversation_id="thread",
        )
    )
    adapter = CodexGenerationRunnerAdapter(
        repository=repository,
        codex_runner=codex_runner,
        generator_config=GeneratorConfig(
            max_retries=2,
            home=tmp_path / "codex/.codex",
            workdir=tmp_path / "codex/sessions",
            output_schema=tmp_path / "schema.json",
            saved_artifacts_dir=tmp_path / "codex/saved_artifacts",
        ),
        codex_docker_config=_docker_config(),
        data_source_dir=data_source_dir,
        timeout_seconds=300,
        transaction_manager=NoopTransactionManager(),
    )

    adapter.run_generation(
        accepted.chat_id,
        accepted.run_id,
        "資料を要約してください",
    )

    assert codex_runner.requests[0].data_source_dir == data_source_dir
    assert not (codex_runner.requests[0].workdir / "data_source").exists()
    assert (codex_runner.requests[0].workdir / "tmp").is_dir()
    assert (codex_runner.requests[0].workdir / "artifacts").is_dir()


def test_codex_generation_runner_streams_intermediate_messages(
    tmp_path: Path,
) -> None:
    """観点：Codex生成実行アダプタの中間メッセージ逐次通知。

    確認：agent_message.textを即時通知し、最終回答の生成結果JSONは通知しない。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("初回")
    codex_runner = StreamingRecordingCodexRunner(
        result=InfrastructureCodexRunResult(
            events=(
                ParsedCodexEvent(
                    kind=CodexEventKind.THREAD_STARTED,
                    event_type="thread.started",
                    thread_id="thread",
                ),
                ParsedCodexEvent(
                    kind=CodexEventKind.AGENT_MESSAGE,
                    event_type="item.completed",
                    text='{"payload":{"kind":"progress","text":"資料を確認しています。"}}',
                ),
                ParsedCodexEvent(
                    kind=CodexEventKind.UNKNOWN, event_type="item.completed"
                ),
                ParsedCodexEvent(
                    kind=CodexEventKind.AGENT_MESSAGE,
                    event_type="item.completed",
                    text='{"payload":{"kind":"final","answers":[{"text":"回答","references":[]}]}}',
                ),
                ParsedCodexEvent(
                    kind=CodexEventKind.TURN_COMPLETED, event_type="turn.completed"
                ),
            ),
            final_message='{"payload":{"kind":"final","answers":[{"text":"回答","references":[]}]}}',
            codex_conversation_id="thread",
        )
    )
    data_source_dir = tmp_path / "data_source"
    data_source_dir.mkdir()
    adapter = CodexGenerationRunnerAdapter(
        repository=repository,
        codex_runner=codex_runner,
        generator_config=GeneratorConfig(
            max_retries=2,
            home=tmp_path / "codex/.codex",
            workdir=tmp_path / "codex/sessions",
            output_schema=tmp_path / "schema.json",
            saved_artifacts_dir=tmp_path / "codex/saved_artifacts",
        ),
        codex_docker_config=_docker_config(),
        data_source_dir=data_source_dir,
        timeout_seconds=300,
        transaction_manager=NoopTransactionManager(),
    )
    streamed_messages: list[str] = []

    result = adapter.run_generation(
        accepted.chat_id,
        accepted.run_id,
        "資料を要約してください",
        on_intermediate_message=streamed_messages.append,
    )

    assert streamed_messages == ["資料を確認しています。"]
    assert result.intermediate_messages == ()
    assert result.final_answer_json == (
        '{"payload":{"kind":"final","answers":[{"text":"回答","references":[]}]}}'
    )


def test_intermediate_message_streamer_emits_agent_message_text_immediately() -> None:
    """観点：JSONL中間メッセージ分類。

    確認：payload.kind=progressのagent_message.textを受信時点で通知する。
    """
    messages: list[str] = []
    streamer = CodexIntermediateMessageStreamer(messages.append)

    streamer.accept(
        ParsedCodexEvent(
            kind=CodexEventKind.AGENT_MESSAGE,
            event_type="item.completed",
            text='{"payload":{"kind":"progress","text":"参照元を確認しています。"}}',
        )
    )

    assert messages == ["参照元を確認しています。"]


def test_generation_streamer_handles_payload_progress_and_final_json() -> None:
    """観点：JSONL中間メッセージ分類。

    確認：payload.kind=progressだけを中間メッセージへ通知し、payload.kind=finalは最終回答として通知しない。
    """
    messages: list[str] = []
    streamer = CodexIntermediateMessageStreamer(messages.append)

    streamer.accept(
        ParsedCodexEvent(
            kind=CodexEventKind.AGENT_MESSAGE,
            event_type="item.completed",
            text=(
                '{"payload":{"kind":"progress","text":"関連文書を確認しています。"}}'
            ),
        )
    )
    streamer.accept(
        ParsedCodexEvent(
            kind=CodexEventKind.AGENT_MESSAGE,
            event_type="item.completed",
            text=(
                '{"payload":{"kind":"final","answers":'
                '[{"text":"最終回答です。","references":[]}]}}'
            ),
        )
    )
    streamer.accept(
        ParsedCodexEvent(
            kind=CodexEventKind.TURN_COMPLETED, event_type="turn.completed"
        )
    )

    assert messages == ["関連文書を確認しています。"]


def test_intermediate_message_streamer_ignores_non_progress_events() -> None:
    """観点：JSONL中間メッセージ分類。

    確認：plain text、payload.kind=final、その他イベントは通知しない。
    """
    messages: list[str] = []
    streamer = CodexIntermediateMessageStreamer(messages.append)

    streamer.accept(
        ParsedCodexEvent(
            kind=CodexEventKind.AGENT_MESSAGE,
            event_type="item.completed",
            text="参照元を確認しています。",
        )
    )
    streamer.accept(
        ParsedCodexEvent(
            kind=CodexEventKind.AGENT_MESSAGE,
            event_type="item.completed",
            text='{"payload":{"kind":"final","answers":[{"text":"回答","references":[]}]}}',
        )
    )
    streamer.accept(
        ParsedCodexEvent(kind=CodexEventKind.UNKNOWN, event_type="item.completed")
    )

    assert messages == []


def test_intermediate_message_streamer_allows_no_emit_callback() -> None:
    """観点：中間メッセージ分類。

    確認：通知先なしでもagent_message.textの分類処理を実行できる。
    """
    streamer = CodexIntermediateMessageStreamer(None)

    streamer.accept(
        ParsedCodexEvent(
            kind=CodexEventKind.AGENT_MESSAGE,
            event_type="item.completed",
            text="通知されないメッセージ",
        )
    )
    streamer.accept(
        ParsedCodexEvent(kind=CodexEventKind.UNKNOWN, event_type="item.completed")
    )


@dataclass(slots=True)
class RecordingCodexRunner:
    result: InfrastructureCodexRunResult
    requests: list[CodexRunRequest] = field(default_factory=list)

    def run_generation(self, request: CodexRunRequest) -> InfrastructureCodexRunResult:
        self.requests.append(request)
        return self.result


@dataclass(slots=True)
class StreamingRecordingCodexRunner(RecordingCodexRunner):
    def run_generation(self, request: CodexRunRequest) -> InfrastructureCodexRunResult:
        self.requests.append(request)
        for event in self.result.events:
            if request.on_event is not None:
                request.on_event(event)
        return self.result


def _docker_config() -> CodexDockerConfig:
    return CodexDockerConfig(
        image="codex-python-runner:latest",
        workspace_dir="/workspace",
        codex_home_dir="/home/codex/.codex",
        codex_api_key="",
    )

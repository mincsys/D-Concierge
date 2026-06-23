from __future__ import annotations

import pytest

from backend.domain.chat.chat_state import ChatState
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.shared.tracing.trace_id import TraceId
from backend.tests.support.chat import (
    CHAT_ID_VALUE,
    F003_USER_ID,
    OTHER_USER_ID,
    TRACE_ID_VALUE,
    FakeChatRepository,
    fixed_chat_detail_record,
    fixed_history_records,
)


def test_list_chat_histories_returns_owner_items_in_repository_order() -> None:
    """
    観点：履歴一覧取得ユースケースがログインユーザの通常操作対象履歴だけを返すこと
    確認：Repositoryが返した更新日時降順の履歴を維持し、別ユーザ履歴を混在させず、
    latest_run_id、latest_state、updated_atを画面契約名で返すこと
    """
    from backend.application.history.list_chat_histories import (
        ListChatHistoriesCommand,
        ListChatHistoriesUseCase,
    )

    repository = FakeChatRepository(
        histories={
            F003_USER_ID: fixed_history_records(),
            OTHER_USER_ID: (),
        },
    )
    use_case = ListChatHistoriesUseCase(repository=repository)

    result = use_case.execute(
        ListChatHistoriesCommand(
            authenticated_user_id=F003_USER_ID,
            trace_id=TraceId(TRACE_ID_VALUE),
        )
    )

    assert [item.chat_id for item in result.items] == [
        fixed_history_records()[0].chat_id,
        fixed_history_records()[1].chat_id,
    ]
    assert result.items[0].title == "新しい履歴"
    assert result.items[0].latest_run_id == fixed_history_records()[0].latest_run_id
    assert result.items[0].latest_state == "completed"
    assert result.items[0].updated_at == fixed_history_records()[0].updated_at


def test_get_chat_detail_formats_runs_messages_answers_and_references() -> None:
    """
    観点：履歴詳細取得ユースケースが保存済みrun、指示、中間メッセージ、回答、参照元を整形すること
    確認：runは保存済み順で返り、完了runには回答ブロックと表示用参照元URL、
    未生成項目は余分な内部情報なしで返ること
    """
    from backend.application.chat.get_chat_detail import (
        GetChatDetailCommand,
        GetChatDetailUseCase,
    )

    repository = FakeChatRepository(
        details={(F003_USER_ID, CHAT_ID_VALUE): fixed_chat_detail_record()},
    )
    use_case = GetChatDetailUseCase(repository=repository)

    result = use_case.execute(
        GetChatDetailCommand(
            authenticated_user_id=F003_USER_ID,
            chat_id=CHAT_ID_VALUE,
            trace_id=TraceId(TRACE_ID_VALUE),
        )
    )

    assert result.chat_id == CHAT_ID_VALUE
    assert result.title == "履歴タイトル"
    assert len(result.runs) == 1
    run = result.runs[0]
    assert run.run_id == fixed_chat_detail_record().runs[0].run_id
    assert run.user_instruction == "最初の指示"
    assert run.intermediate_messages[0].text == "作業を開始します。"
    assert run.answer is not None
    assert run.answer.blocks[0].markdown == "回答本文"
    reference = run.answer.blocks[0].references[0]
    assert reference.source_type == "pdf"
    assert reference.url.startswith("/api/references/")
    assert reference.locator.page_start == 2
    assert reference.locator.page_end == 3


def test_get_chat_detail_rejects_missing_or_deleting_chat() -> None:
    """
    観点：履歴詳細取得ユースケースが対象なし、別ユーザ、削除中チャットを通常表示へ混ぜないこと
    確認：対象なしはNOT_FOUND、deletingはCONFLICTとなり、詳細payloadを返さないこと
    """
    from backend.application.chat.get_chat_detail import (
        GetChatDetailCommand,
        GetChatDetailUseCase,
    )

    deleting_detail = fixed_chat_detail_record()
    repository = FakeChatRepository(
        details={
            (OTHER_USER_ID, CHAT_ID_VALUE): fixed_chat_detail_record(),
            (
                F003_USER_ID,
                CHAT_ID_VALUE,
            ): type(deleting_detail)(
                chat_id=deleting_detail.chat_id,
                title=deleting_detail.title,
                chat_state=ChatState.DELETING.value,
                runs=deleting_detail.runs,
            ),
        },
    )
    use_case = GetChatDetailUseCase(repository=repository)

    with pytest.raises(AppError) as missing:
        use_case.execute(
            GetChatDetailCommand(
                authenticated_user_id=F003_USER_ID,
                chat_id=type(CHAT_ID_VALUE)("99999999-9999-7999-8999-999999999999"),
                trace_id=TraceId(TRACE_ID_VALUE),
            )
        )

    with pytest.raises(AppError) as deleting:
        use_case.execute(
            GetChatDetailCommand(
                authenticated_user_id=F003_USER_ID,
                chat_id=CHAT_ID_VALUE,
                trace_id=TraceId(TRACE_ID_VALUE),
            )
        )

    assert missing.value.error_type is ErrorType.NOT_FOUND
    assert deleting.value.error_type is ErrorType.CONFLICT

from uuid import UUID

from backend.application.execution.execute_chat_run import RunEvent
from backend.application.execution.run_event_type import RunEventType
from backend.domain.execution.run_state import RunState
from backend.presentation.sse.run_event_broker import RunEventBroker


def test_run_event_broker_delivers_events_to_subscriber_in_order() -> None:
    """観点：SSEイベント配信IF。

    確認：購読中runへpublishされたイベントを発生順に取得できる。
    """
    broker = RunEventBroker()
    chat_id = UUID("00000000-0000-0000-0000-000000000501")
    run_id = UUID("00000000-0000-0000-0000-000000000502")
    subscription = broker.subscribe(run_id)

    broker.publish(
        RunEvent(
            event=RunEventType.STATE,
            chat_id=chat_id,
            run_id=run_id,
            state=RunState.RUNNING,
        )
    )
    broker.publish(
        RunEvent(
            event=RunEventType.MESSAGE,
            chat_id=chat_id,
            run_id=run_id,
            text="検索中です。",
        )
    )

    first = subscription.next_event(timeout_seconds=0)
    second = subscription.next_event(timeout_seconds=0)
    assert first is not None
    assert second is not None
    assert first.event is RunEventType.STATE
    assert second.event is RunEventType.MESSAGE


def test_run_event_broker_ignores_publish_without_subscriber() -> None:
    """観点：SSEイベント配信IF。

    確認：購読者がいないrunへのpublishはエラーにしない。
    """
    broker = RunEventBroker()

    broker.publish(
        RunEvent(
            event=RunEventType.STATE,
            chat_id=UUID("00000000-0000-0000-0000-000000000503"),
            run_id=UUID("00000000-0000-0000-0000-000000000504"),
            state=RunState.RUNNING,
        )
    )


def test_run_event_broker_closes_subscription_after_terminal_event() -> None:
    """観点：SSEイベント配信IF。

    確認：終端イベント配信後は購読を閉じ、後続イベントを送らない。
    """
    broker = RunEventBroker()
    chat_id = UUID("00000000-0000-0000-0000-000000000505")
    run_id = UUID("00000000-0000-0000-0000-000000000506")
    subscription = broker.subscribe(run_id)

    broker.publish(
        RunEvent(
            event=RunEventType.ANSWER,
            chat_id=chat_id,
            run_id=run_id,
            state=RunState.COMPLETED,
        )
    )
    broker.publish(
        RunEvent(
            event=RunEventType.STATE,
            chat_id=chat_id,
            run_id=run_id,
            state=RunState.RUNNING,
        )
    )

    terminal = subscription.next_event(timeout_seconds=0)
    closed = subscription.next_event(timeout_seconds=0)
    late = subscription.next_event(timeout_seconds=0)
    assert terminal is not None
    assert terminal.event is RunEventType.ANSWER
    assert closed is None
    assert late is None


def test_run_event_broker_unsubscribe_stops_delivery() -> None:
    """観点：SSEイベント配信IF。

    確認：購読解除後の接続へイベントを送信しない。
    """
    broker = RunEventBroker()
    chat_id = UUID("00000000-0000-0000-0000-000000000507")
    run_id = UUID("00000000-0000-0000-0000-000000000508")
    subscription = broker.subscribe(run_id)

    broker.unsubscribe(subscription)
    broker.publish(
        RunEvent(
            event=RunEventType.STATE,
            chat_id=chat_id,
            run_id=run_id,
            state=RunState.RUNNING,
        )
    )

    assert subscription.next_event(timeout_seconds=0) is None
    assert subscription.next_event(timeout_seconds=0) is None


def test_run_event_broker_unsubscribe_one_of_multiple_subscribers() -> None:
    """観点：SSEイベント配信IF。

    確認：同一runの一部購読だけを解除し、残りの購読には配信を継続する。
    """
    broker = RunEventBroker()
    chat_id = UUID("00000000-0000-0000-0000-000000000509")
    run_id = UUID("00000000-0000-0000-0000-000000000510")
    removed = broker.subscribe(run_id)
    remaining = broker.subscribe(run_id)

    broker.unsubscribe(removed)
    broker.publish(
        RunEvent(
            event=RunEventType.STATE,
            chat_id=chat_id,
            run_id=run_id,
            state=RunState.RUNNING,
        )
    )

    assert removed.next_event(timeout_seconds=0) is None
    delivered = remaining.next_event(timeout_seconds=0)
    assert delivered is not None
    assert delivered.event is RunEventType.STATE


def test_run_event_broker_unsubscribe_unknown_subscription_is_noop() -> None:
    """観点：SSEイベント配信IF。

    確認：登録済みでない購読の解除と、削除済みrunの再解除をエラーにしない。
    """
    broker = RunEventBroker()
    run_id = UUID("00000000-0000-0000-0000-000000000511")
    registered = broker.subscribe(run_id)
    unknown = broker.subscribe(UUID("00000000-0000-0000-0000-000000000512"))

    broker.unsubscribe(registered)
    broker.unsubscribe(registered)
    broker.unsubscribe(unknown)

    assert registered.next_event(timeout_seconds=0) is None
    assert unknown.next_event(timeout_seconds=0) is None

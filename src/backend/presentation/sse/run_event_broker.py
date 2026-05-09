from dataclasses import dataclass, field
from queue import Empty, Queue
from threading import RLock
from uuid import UUID

from backend.application.execution.execute_chat_run import RunEvent

TERMINAL_EVENTS = frozenset(("answer", "error", "canceled"))


@dataclass(slots=True)
class RunEventSubscription:
    """run ID単位のSSE購読。"""

    run_id: UUID
    _events: Queue[RunEvent | None] = field(default_factory=Queue)

    def next_event(self, timeout_seconds: float | None = None) -> RunEvent | None:
        """次のイベントを取得する。終端またはタイムアウト時はNoneを返す。"""
        try:
            return self._events.get(timeout=timeout_seconds)
        except Empty:
            return None

    def poll_event(self) -> tuple[bool, RunEvent | None]:
        """待機せずにイベントを取得し、未到着か終端かを区別して返す。"""
        try:
            return True, self._events.get_nowait()
        except Empty:
            return False, None

    def push(self, event: RunEvent) -> None:
        """購読キューへイベントを追加する。"""
        self._events.put(event)

    def close(self) -> None:
        """購読キューへ終端を通知する。"""
        self._events.put(None)


class RunEventBroker:
    """run ID単位で実行イベントをpublish/subscribeするメモリ内Broker。"""

    def __init__(self) -> None:
        self._subscriptions: dict[UUID, list[RunEventSubscription]] = {}
        self._lock = RLock()

    def subscribe(self, run_id: UUID) -> RunEventSubscription:
        """run IDのイベント購読を登録する。"""
        subscription = RunEventSubscription(run_id=run_id)
        with self._lock:
            subscriptions = self._subscriptions.setdefault(run_id, [])
            subscriptions.append(subscription)
        return subscription

    def unsubscribe(self, subscription: RunEventSubscription) -> None:
        """購読を解除する。"""
        with self._lock:
            subscriptions = self._subscriptions.get(subscription.run_id)
            if subscriptions is None:
                return
            if subscription in subscriptions:
                subscriptions.remove(subscription)
            if not subscriptions:
                del self._subscriptions[subscription.run_id]
        subscription.close()

    def publish(self, event: RunEvent) -> None:
        """購読者へイベントを配信する。購読者がいない場合は何もしない。"""
        with self._lock:
            subscriptions = tuple(self._subscriptions.get(event.run_id, ()))
            if event.event in TERMINAL_EVENTS:
                self._subscriptions.pop(event.run_id, None)

        for subscription in subscriptions:
            subscription.push(event)
            if event.event in TERMINAL_EVENTS:
                subscription.close()

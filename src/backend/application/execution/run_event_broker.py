from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class RunEventType(Enum):
    """SSEで送信するrunイベント種別。"""

    STATE = "state"
    MESSAGE = "message"
    ANSWER = "answer"
    ERROR = "error"
    CANCELED = "canceled"


@dataclass(frozen=True, slots=True)
class RunEvent:
    """run ID単位で配信するSSEイベント。"""

    event_type: RunEventType
    run_id: UUID
    payload_state: str | None = None
    text: str | None = None
    user_message: str | None = None

    @classmethod
    def state(cls, run_id: UUID, state: str) -> RunEvent:
        """状態通知イベントを生成する。"""

        return cls(
            event_type=RunEventType.STATE,
            run_id=run_id,
            payload_state=state,
        )

    @classmethod
    def message(cls, run_id: UUID, text: str) -> RunEvent:
        """中間メッセージイベントを生成する。"""

        return cls(
            event_type=RunEventType.MESSAGE,
            run_id=run_id,
            text=text,
        )

    @classmethod
    def end(
        cls,
        *,
        event_type: RunEventType,
        run_id: UUID,
        state: str,
        user_message: str,
    ) -> RunEvent:
        """終端イベントを生成する。"""

        return cls(
            event_type=event_type,
            run_id=run_id,
            payload_state=state,
            user_message=user_message,
        )


@dataclass(slots=True)
class RunEventSubscription:
    """runイベント購読状態。"""

    run_id: UUID
    _queue: deque[RunEvent]
    _closed: bool = False

    def poll_event(self) -> RunEvent | None:
        """未読イベントを1件取り出す。"""

        if self._closed or not self._queue:
            return None
        return self._queue.popleft()

    def close(self) -> None:
        """購読を閉じ、未配送イベントを破棄する。"""

        self._closed = True
        self._queue.clear()


class RunEventBroker:
    """run ID単位でSSEイベントをpublish/subscribeする。"""

    def __init__(self) -> None:
        self._subscriptions: dict[UUID, list[deque[RunEvent]]] = {}
        self._terminal_run_ids: set[UUID] = set()

    def subscribe(self, run_id: UUID) -> RunEventSubscription:
        """指定runのイベント購読を開始する。"""

        queue: deque[RunEvent] = deque()
        self._subscriptions.setdefault(run_id, []).append(queue)
        return RunEventSubscription(run_id=run_id, _queue=queue)

    def publish(self, event: RunEvent) -> None:
        """購読者へイベントを配信する。"""

        if event.run_id in self._terminal_run_ids:
            return
        for queue in self._subscriptions.get(event.run_id, ()):
            queue.append(event)
        if event.event_type in _TERMINAL_EVENT_TYPES:
            self._terminal_run_ids.add(event.run_id)

    def unsubscribe(self, subscription: RunEventSubscription) -> None:
        """指定購読を解除する。"""

        queues = self._subscriptions.get(subscription.run_id)
        if queues is not None:
            remaining_queues = [
                queue for queue in queues if queue is not subscription._queue
            ]
            if len(remaining_queues) != len(queues):
                if remaining_queues:
                    self._subscriptions[subscription.run_id] = remaining_queues
                else:
                    del self._subscriptions[subscription.run_id]
        subscription.close()


_TERMINAL_EVENT_TYPES = frozenset(
    {
        RunEventType.ANSWER,
        RunEventType.ERROR,
        RunEventType.CANCELED,
    }
)

# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""进程内 SSE 事件总线；只承诺单进程生命周期。"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from dataclasses import dataclass
from typing import Any

_TERMINAL_EVENTS = {"completed", "failed", "closed"}


@dataclass(frozen=True, slots=True)
class ReviewEvent:
    """发送给 SSE consumer 的事件。"""

    event: str
    data: dict[str, Any]

    @property
    def terminal(self) -> bool:
        return self.event in _TERMINAL_EVENTS


class ReviewEventBus:
    """按 (tenant_id, run_id) 维护有界 consumer 队列。"""

    def __init__(self) -> None:
        self._queues: dict[tuple[str, str], list[asyncio.Queue[ReviewEvent]]] = {}
        self._lock = threading.RLock()

    def subscribe(self, tenant_id: str, run_id: str) -> asyncio.Queue[ReviewEvent]:
        """创建一个独立 consumer；断开时调用方直接放弃 queue 即可。"""
        queue: asyncio.Queue[ReviewEvent] = asyncio.Queue(maxsize=64)
        with self._lock:
            self._queues.setdefault((tenant_id, run_id), []).append(queue)
        return queue

    def unsubscribe(self, tenant_id: str, run_id: str, queue: asyncio.Queue[ReviewEvent]) -> None:
        """consumer 断开时只移除自己的队列，不影响 run。"""
        with self._lock:
            queues = self._queues.get((tenant_id, run_id), [])
            with contextlib.suppress(ValueError):
                queues.remove(queue)
            if not queues:
                self._queues.pop((tenant_id, run_id), None)

    def publish(self, tenant_id: str, run_id: str, event: str, data: dict[str, Any]) -> None:
        """发布事件；慢 consumer 只丢弃非 terminal 事件。"""
        item = ReviewEvent(event=event, data=data)
        with self._lock:
            for queue in self._queues.get((tenant_id, run_id), []):
                self._put(queue, item)

    def complete(self, tenant_id: str, run_id: str) -> None:
        """发送关闭事件并清理该 run 的全部 consumer。"""
        with self._lock:
            for queue in self._queues.get((tenant_id, run_id), []):
                self._put(queue, ReviewEvent(event="closed", data={}))
            self._queues.pop((tenant_id, run_id), None)

    @staticmethod
    def _put(queue: asyncio.Queue[ReviewEvent], item: ReviewEvent) -> None:
        if queue.full():
            pending = list(queue._queue)  # type: ignore[attr-defined]
            drop_index = next(
                (idx for idx, current in enumerate(pending) if not current.terminal),
                0,
            )
            queue._queue.remove(pending[drop_index])  # type: ignore[attr-defined]
        queue.put_nowait(item)

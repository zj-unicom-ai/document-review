# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""把异步审核引擎安全地提供给同步、多线程宿主。"""

import asyncio
import os
import threading
from collections.abc import Callable
from concurrent.futures import CancelledError, Future

from document_review.schemas.evaluation import EvaluationRequest, EvaluationResponse
from document_review.services.evaluation import EvaluationService


class EvaluationBusy(RuntimeError):
    """执行器容量已满，调用方应稍后重试。"""


class SyncEvaluationClient:
    """一个进程内共享一个循环与服务；支持有界并发、关闭及上下文管理。"""

    def __init__(self, service_factory: Callable[[], EvaluationService], *, max_inflight: int = 4):
        if max_inflight < 1:
            raise ValueError("max_inflight 必须大于 0")
        self._pid = os.getpid()
        self._slots = threading.BoundedSemaphore(max_inflight)
        self._lock = threading.Lock()
        self._closed = False
        self._ready = Future()
        self._thread = threading.Thread(
            target=self._run, args=(service_factory,), name="document-review-loop", daemon=True
        )
        self._thread.start()
        self._ready.result()

    def _run(self, factory):
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)

        async def initialize():
            self._service = factory()

        async def cleanup():
            tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await loop.shutdown_asyncgens()

        try:
            loop.run_until_complete(initialize())
            self._ready.set_result(None)
            loop.run_forever()
        except BaseException as exc:
            if not self._ready.done():
                self._ready.set_exception(exc)
            else:
                raise
        finally:
            loop.run_until_complete(cleanup())
            loop.close()

    def evaluate(self, pdf_bytes: bytes, request: EvaluationRequest) -> EvaluationResponse:
        """同步等待本次任务；容量不足抛 EvaluationBusy，关闭中任务返回需复核。"""
        if os.getpid() != self._pid:
            raise RuntimeError("执行器必须在 fork 后创建")
        if threading.current_thread() is self._thread:
            raise RuntimeError("不能在审核事件循环线程中同步等待")
        with self._lock:
            if self._closed:
                raise RuntimeError("审核执行器已关闭")
            if not self._slots.acquire(blocking=False):
                raise EvaluationBusy("通用审核容量已满，请稍后重试")
            future = asyncio.run_coroutine_threadsafe(
                self._service.evaluate(pdf_bytes, request), self._loop
            )
            future.add_done_callback(lambda _: self._slots.release())
        try:
            return future.result()
        except CancelledError:
            return EvaluationResponse(status="needs_review", error="审核执行器关闭，需复核")

    def close(self) -> None:
        """停止接收任务，取消现有任务并等待临时文件清理；可重复调用。"""
        if os.getpid() != self._pid:
            return
        if threading.current_thread() is self._thread:
            raise RuntimeError("不能在审核事件循环线程中同步关闭")
        with self._lock:
            if not self._closed:
                self._closed = True
                self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=10)
        if self._thread.is_alive():
            raise RuntimeError("审核执行器未在期限内关闭")

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

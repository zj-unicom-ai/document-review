# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""BL-019：公共同步调用接口的并发、取消与生命周期契约。"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import pymupdf
import pytest
from document_review import EvaluationRequest, EvaluationService
from document_review.engine.llm_rule import AgentStep
from document_review.integrations.llm import LlmService, StructuredResponse


def content():
    with pymupdf.open() as pdf:
        pdf.new_page()
        return pdf.tobytes()


def task():
    return EvaluationRequest(
        instruction="检查",
        output_schema={"type": "object"},
        require_evidence=False,
        require_visual_coverage=False,
    )


class Provider:
    def __init__(self):
        self.active = 0
        self.peak = 0
        self.loops = set()

    async def structured(self, schema, messages, **kwargs):
        self.loops.add(asyncio.get_running_loop())
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(0.01)
            return StructuredResponse(parsed=AgentStep(final={"ok": True}), raw={}, usage={})
        finally:
            self.active -= 1


def test_a3_threads_share_loop_and_model_limit():
    from document_review import SyncEvaluationClient

    provider = Provider()
    with SyncEvaluationClient(
        lambda: EvaluationService(LlmService(provider, max_concurrency=1)), max_inflight=4
    ) as client:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: client.evaluate(content(), task()), range(8)))
        assert all(r.status == "success" for r in results)
    assert provider.peak == 1
    assert len(provider.loops) == 1
    assert next(iter(provider.loops)).is_closed()


def test_e3_capacity_rejects_without_starting_another_task():
    from document_review import EvaluationBusy, SyncEvaluationClient

    started = threading.Event()
    release = threading.Event()

    class BlockingProvider(Provider):
        async def structured(self, *args, **kwargs):
            started.set()
            while not release.is_set():  # noqa: ASYNC110 — 同步调用线程控制测试释放点
                await asyncio.sleep(0.005)
            return await super().structured(*args, **kwargs)

    with SyncEvaluationClient(
        lambda: EvaluationService(LlmService(BlockingProvider())), max_inflight=1
    ) as client:
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(client.evaluate, content(), task())
            try:
                assert started.wait(2)
                with pytest.raises(EvaluationBusy):
                    client.evaluate(content(), task())
            finally:
                release.set()
            assert pending.result(timeout=2).status == "success"


def test_e4_timeout_cleans_file_and_releases_capacity():
    from document_review import SyncEvaluationClient
    from document_review.engine.state import RuleResult

    paths = []

    async def runner(plan, doc, llm):
        paths.append(doc.parsed.pdf_path)
        if len(paths) == 1:
            await asyncio.sleep(10)
        return RuleResult("test", 0, "test", "test", status="success", extracted={})

    with SyncEvaluationClient(
        lambda: EvaluationService(None, runner=runner, timeout_s=0.03), max_inflight=1
    ) as client:
        assert client.evaluate(content(), task()).status == "needs_review"
        assert client.evaluate(content(), task()).status == "success"
    assert all(not path.exists() for path in paths)
    with pytest.raises(RuntimeError, match="关闭"):
        client.evaluate(content(), task())


def test_e4_close_cancels_active_task_and_cleans_source():
    from document_review import SyncEvaluationClient

    paths = []
    entered = threading.Event()

    async def runner(plan, doc, llm):
        paths.append(doc.parsed.pdf_path)
        entered.set()
        await asyncio.sleep(10)

    client = SyncEvaluationClient(lambda: EvaluationService(None, runner=runner))
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.evaluate, content(), task())
        assert entered.wait(2)
        client.close()
        assert pending.result(timeout=2).status == "needs_review"
    assert all(not path.exists() for path in paths)
    client.close()

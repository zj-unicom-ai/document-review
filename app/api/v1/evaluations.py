# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""原 PDF 加调用方任务的受控无状态入口。"""

import secrets
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import ValidationError

from app.core.config import settings
from app.engine.tools import UnknownToolError, validate_tool_whitelist
from app.integrations.llm import build_llm_service
from app.schemas.evaluation import EvaluationRequest, EvaluationResponse
from app.services.evaluation import EvaluationService

router = APIRouter()


async def authorize(x_api_key: Annotated[str | None, Header()] = None) -> None:
    """仅允许已配置密钥的内部调用方使用模型执行入口。"""
    if not settings.agent_api_key:
        raise HTTPException(503, "AGENT_API_KEY 未配置")
    if not secrets.compare_digest(x_api_key or "", settings.agent_api_key):
        raise HTTPException(401, "调用方鉴权失败")


@lru_cache(maxsize=1)
def _build_evaluation_service() -> EvaluationService:
    """共享 LLM 并发限流器，文档上下文仍按请求隔离。"""
    return EvaluationService(
        build_llm_service(settings),
        timeout_s=settings.agent_timeout_s,
        max_pages=settings.agent_max_pages,
        max_upload_mb=settings.agent_max_upload_mb,
    )


async def get_evaluation_service() -> EvaluationService:
    """提供进程内共享限流器，避免同步依赖占用线程池。"""
    return _build_evaluation_service()


@router.post("/", response_model=EvaluationResponse, dependencies=[Depends(authorize)])
async def evaluate(
    file: Annotated[UploadFile, File()],
    request: Annotated[str, Form()],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> EvaluationResponse:
    """接收 PDF 与 JSON 任务；不接受服务器路径、不写入业务数据库。"""
    if len(request.encode("utf-8")) > 10 * 1024 * 1024:
        raise HTTPException(413, "任务上下文过大")
    try:
        task = EvaluationRequest.model_validate_json(request)
        validate_tool_whitelist(task.tools)
    except (ValidationError, UnknownToolError):
        raise HTTPException(422, "任务或工具配置不合法") from None
    content = await file.read(settings.agent_max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.agent_max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "PDF 超过大小限制")
    if not content:
        raise HTTPException(422, "PDF 为空")
    try:
        return await service.evaluate(content, task)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

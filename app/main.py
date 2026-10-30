# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""FastAPI app entrypoint."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1 import api_v1_router
from app.core.config import settings
from app.core.deps import DBSession
from app.core.exceptions import DomainError
from app.core.logging import configure_logging

configure_logging(settings.app_log_level)


def validate_runtime_security() -> None:
    """生产环境必须显式配置会话签名密钥。"""
    if settings.app_env == "production" and not settings.auth_secret_key:
        raise RuntimeError("AUTH_SECRET_KEY is required in production")


validate_runtime_security()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.app_debug,
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.exception_handler(DomainError)
async def _domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    """把 DomainError 映射到其声明的 HTTP 状态码。

    每个 DomainError 子类都自带 code + http_status；这里集中转换，让 API 层
    不会把所有领域错误都退化成 500。BL-002 偏差记录详见 lifecycle 文档。
    """
    return JSONResponse(
        status_code=exc.http_status,
        content={"code": exc.code, "message": str(exc)},
    )


app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


@app.get("/health/ready", tags=["meta"], include_in_schema=False)
async def readiness(session: DBSession) -> JSONResponse:
    """部署探针：数据库不可用时必须表现为未就绪，而不是健康。"""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unready",
                "database": "unavailable",
                # 探针响应可能进入监控系统，不回传可能带连接串的异常原文。
                "error": f"database connectivity check failed: {type(exc).__name__}",
            },
        )
    return JSONResponse(content={"status": "ready", "database": "ok"})

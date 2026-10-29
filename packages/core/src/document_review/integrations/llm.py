# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""LLM 统一接入层：模型分级、并发限流、重试与 trace 采集。

所有引擎 / 算子对 LLM 的调用必须经 `LlmService`，不得直接实例化模型客户端，
便于统一预算、脱敏与测试注入 fake provider。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel

from document_review.config import LlmSettings as Settings

MODEL_PROFILES = ("text", "vision", "light")


class LlmOutputError(RuntimeError):
    """模型输出无法按目标 Schema 解析。"""


class LlmConfigError(ValueError):
    """模型档位或端点配置无法解析。"""


@dataclass(frozen=True, slots=True)
class ModelRoute:
    """一次 LLM 调用实际使用的端点与档位解析结果。"""

    model_profile: str
    base_url: str
    model: str
    degraded: bool = False
    fallback_from: str | None = None


@dataclass(frozen=True, slots=True)
class StructuredResponse:
    """provider 层返回的结构化响应。"""

    parsed: Any
    raw: dict[str, Any]
    usage: dict[str, int]
    route: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class LlmCall:
    """一次业务级 LLM 调用结果与可回放 trace。"""

    data: Any
    trace: dict[str, Any]


class ModelProvider(Protocol):
    """结构化调用 provider 协议；生产与测试各自实现。"""

    async def structured(
        self,
        schema: type[BaseModel],
        messages: list[dict[str, Any]],
        *,
        model_profile: str,
        temperature: float,
        max_tokens: int | None,
        images: list[bytes] | None,
    ) -> StructuredResponse: ...


def resolve_model_name(settings: Settings, model_profile: str) -> str:
    """按档位解析模型名；未配置专用模型时回退主模型。"""
    return resolve_model_route(settings, model_profile).model


def resolve_model_route(settings: Settings, model_profile: str) -> ModelRoute:
    """解析档位端点；vision / light 缺专用 model 时显式降级主模型。"""
    if model_profile not in MODEL_PROFILES:
        raise LlmConfigError(f"未知模型档位: {model_profile}")

    base_url = getattr(settings, f"llm_{model_profile}_base_url") or settings.llm_base_url
    profile_model = getattr(settings, f"llm_{model_profile}_model")
    model = profile_model or settings.llm_model
    if not base_url:
        raise LlmConfigError(f"LLM 网关未配置: model_profile={model_profile}")
    if not model:
        raise LlmConfigError(
            f"主模型未配置: model_profile={model_profile}；请设置档位专用 model 或 LLM_MODEL"
        )

    degraded = model_profile in ("vision", "light") and not profile_model
    return ModelRoute(
        model_profile=model_profile,
        base_url=base_url,
        model=model,
        degraded=degraded,
        fallback_from=model_profile if degraded else None,
    )


def _route_trace(route: ModelRoute) -> dict[str, Any]:
    """生成安全 trace；API key 不进入 trace。"""
    return {
        "model_profile": route.model_profile,
        "model": route.model,
        "degraded": route.degraded,
        "fallback_from": route.fallback_from,
    }


class LangChainModelProvider:
    """基于 langchain-openai 的生产 provider（OpenAI-compatible 私有网关）。"""

    def __init__(
        self,
        settings: Settings,
        *,
        model_factory: Callable[..., Any] | None = None,
    ):
        self._settings = settings
        self._model_factory = model_factory or self._default_model_factory

    def _default_model_factory(self, **kwargs: Any) -> Any:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(**kwargs)

    async def structured(
        self,
        schema: type[BaseModel],
        messages: list[dict[str, Any]],
        *,
        model_profile: str,
        temperature: float,
        max_tokens: int | None,
        images: list[bytes] | None,
    ) -> StructuredResponse:
        route = resolve_model_route(self._settings, model_profile)
        api_key = route_api_key(self._settings, route)
        model = self._model_factory(
            base_url=route.base_url,
            api_key=api_key or "not-set",
            model=route.model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=self._settings.llm_request_timeout_s,
            **(
                {"extra_body": self._settings.llm_extra_body}
                if getattr(self._settings, "llm_extra_body", None) is not None
                else {}
            ),
        )
        runnable = model.with_structured_output(schema, include_raw=True)
        result = await runnable.ainvoke(_with_images(messages, images))
        parsing_error = result.get("parsing_error")
        if parsing_error is not None:
            raise LlmOutputError(f"结构化输出解析失败: {parsing_error}")
        raw = result.get("raw")
        usage = dict(getattr(raw, "usage_metadata", None) or {})
        return StructuredResponse(
            parsed=result.get("parsed"),
            raw=_raw_content(raw),
            usage={
                "input_tokens": int(usage.get("input_tokens", 0)),
                "output_tokens": int(usage.get("output_tokens", 0)),
            },
            route=_route_trace(route),
        )


def route_api_key(settings: Settings, route: ModelRoute) -> str:
    """按档位还原 API key；该值只传给模型客户端，不进入 trace。"""
    return getattr(settings, f"llm_{route.model_profile}_api_key") or settings.llm_api_key


class LlmService:
    """业务级调用入口：全局并发、重试一次与 trace 采集。"""

    def __init__(
        self,
        provider: ModelProvider,
        *,
        max_concurrency: int = 4,
        retry_attempts: int = 1,
        retry_base_delay: float = 0.1,
    ):
        self.provider = provider
        self.max_concurrency = max_concurrency
        self.retry_attempts = retry_attempts
        self.retry_base_delay = retry_base_delay
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def call_structured(
        self,
        *,
        schema: type[BaseModel],
        system: str,
        messages: list[dict[str, Any]],
        model_profile: str = "text",
        temperature: float = 0.0,
        max_tokens: int | None = None,
        images: list[bytes] | None = None,
    ) -> LlmCall:
        """执行一次结构化调用；trace 中不包含图片二进制与凭据。"""
        payload = [{"role": "system", "content": system}, *messages]
        started = time.monotonic()
        attempts = 0
        last_error: Exception | None = None
        for attempt in range(self.retry_attempts + 1):
            attempts = attempt + 1
            try:
                async with self._semaphore:
                    response = await self.provider.structured(
                        schema,
                        payload,
                        model_profile=model_profile,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        images=images,
                    )
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                if isinstance(exc, LlmConfigError):
                    raise
                if attempt < self.retry_attempts:
                    await asyncio.sleep(self.retry_base_delay * (2**attempt))
        if last_error is not None:
            raise last_error
        trace = {
            "model_profile": model_profile,
            "route": response.route or {"model_profile": model_profile, "degraded": False},
            "messages": _sanitize_messages(payload, images),
            "response": response.raw,
            "usage": response.usage,
            "image_count": len(images or []),
            "attempts": attempts,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
        return LlmCall(data=response.parsed, trace=trace)


def build_llm_service(settings: Settings) -> LlmService | None:
    """按配置构建服务；未配置网关地址时返回 None（调用方走兜底）。"""
    has_gateway = any(
        (
            settings.llm_base_url,
            settings.llm_text_base_url,
            settings.llm_vision_base_url,
            settings.llm_light_base_url,
        )
    )
    if not has_gateway:
        return None
    return LlmService(
        LangChainModelProvider(settings),
        max_concurrency=settings.llm_max_concurrency,
    )


def _with_images(
    messages: list[dict[str, Any]], images: Sequence[bytes] | None
) -> list[dict[str, Any]]:
    """把图片以 data URL 附加到最后一条 user 消息（引擎受控，不由模型取文件）。"""
    if not images:
        return messages
    result = [dict(message) for message in messages]
    for message in reversed(result):
        if message.get("role") == "user":
            parts: list[dict[str, Any]] = [
                {"type": "text", "text": str(message.get("content", ""))}
            ]
            parts.extend(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{_image_mime(image)};base64,{_b64(image)}"},
                }
                for image in images
            )
            message["content"] = parts
            break
    else:
        result.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ""},
                    *(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{_image_mime(image)};base64,{_b64(image)}"},
                        }
                        for image in images
                    ),
                ],
            }
        )
    return result


def _sanitize_messages(
    messages: list[dict[str, Any]], images: Sequence[bytes] | None
) -> list[dict[str, Any]]:
    """trace 脱敏：图片以占位符替代，避免二进制入库。"""
    marker = "[image bytes]"
    sanitized = []
    for message in messages:
        copied = dict(message)
        content = copied.get("content")
        if isinstance(content, list):
            copied["content"] = [
                marker if part.get("type") == "image_url" else part for part in content
            ]
        sanitized.append(copied)
    if images:
        sanitized.append({"role": "system", "content": {"images": [marker] * len(images)}})
    return sanitized


def _raw_content(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    content = getattr(raw, "content", None)
    tool_calls = getattr(raw, "tool_calls", None)
    return {
        "content": content,
        "tool_calls": [
            {
                "name": call.get("name"),
                "args": call.get("args"),
            }
            for call in (tool_calls or [])
            if isinstance(call, dict)
        ],
    }


def _b64(image: bytes) -> str:
    import base64

    return base64.b64encode(image).decode("ascii")


def _image_mime(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    raise ValueError("不支持的视觉图片格式")

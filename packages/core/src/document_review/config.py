# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""模型配置值对象；不自动读取环境变量或初始化外部资源。"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LlmSettings:
    """OpenAI 兼容模型端点与调用预算，由宿主显式传入。"""

    llm_base_url: str = ""
    llm_api_key: str = field(default="", repr=False)
    llm_model: str = ""
    llm_text_base_url: str = ""
    llm_text_api_key: str = field(default="", repr=False)
    llm_text_model: str = ""
    llm_vision_model: str = ""
    llm_vision_base_url: str = ""
    llm_vision_api_key: str = field(default="", repr=False)
    llm_light_base_url: str = ""
    llm_light_api_key: str = field(default="", repr=False)
    llm_light_model: str = ""
    llm_request_timeout_s: float = 60
    llm_max_concurrency: int = 4
    llm_extra_body: dict[str, Any] | None = None

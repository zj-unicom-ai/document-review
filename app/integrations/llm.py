# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""兼容原平台导入路径；实现统一由 document_review 核心包提供。"""

from document_review.integrations.llm import *  # noqa: F403
from document_review.integrations.llm import _with_images as _with_images

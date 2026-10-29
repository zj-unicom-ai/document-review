# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""算子包：导入全部算子模块以完成自注册。"""

from app.operators import (  # noqa: F401
    external_data_check,
    extract_fields,
    list_for_each,
    text_judge,
    vision_judge,
)
from app.operators.registry import (
    all_operators,
    get_operator,
    known_op_codes,
    register,
)

__all__ = ["all_operators", "get_operator", "known_op_codes", "register"]

# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""规则模型档位路由校验；保证一次规则执行内档位唯一。"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from app.operators.registry import get_operator

MODEL_PROFILES = ("text", "vision", "light")


class ModelRoutingError(ValueError):
    """模型档位缺失、非法或与规则 / 算子声明冲突。"""


def validate_model_routing(rule: Any) -> str:
    """归一化并校验规则档位；返回计划快照使用的档位。"""
    return validate_model_routing_values(
        rule_type=rule.rule_type,
        model_profile=rule.model_profile,
        definition=rule.definition,
    )


def validate_model_routing_values(
    *,
    rule_type: str,
    model_profile: str | None,
    definition: Mapping[str, Any],
) -> str:
    """供保存前校验复用；输入为规则类型、主表档位和 DSL。"""
    row_profile = model_profile
    definition = definition if isinstance(definition, Mapping) else {}
    dsl_profile = definition.get("model_profile")

    if row_profile is not None and row_profile not in MODEL_PROFILES:
        raise ModelRoutingError(f"非法模型档位: {row_profile}")
    if dsl_profile is not None and dsl_profile not in MODEL_PROFILES:
        raise ModelRoutingError(f"非法模型档位: {dsl_profile}")
    if row_profile is not None and dsl_profile is not None and row_profile != dsl_profile:
        raise ModelRoutingError(
            f"规则主表 model_profile={row_profile} 与 definition.model_profile={dsl_profile} 冲突"
        )

    profile = row_profile or dsl_profile or "text"
    if rule_type == "structured":
        if dsl_profile is not None or row_profile is not None:
            raise ModelRoutingError("structured 规则不支持声明 model_profile")
        return profile

    _validate_operator_profiles(definition, profile)
    return profile


def _validate_operator_profiles(definition: Mapping[str, Any], profile: str) -> None:
    """hybrid 规则内所有占用模型的算子必须使用同一档位。"""
    profiles: dict[str, str] = {}
    for op_code, operator_profile in _iter_model_operators(definition.get("ops") or []):
        profiles[op_code] = operator_profile

    if len(set(profiles.values())) > 1:
        raise ModelRoutingError("同一 hybrid 规则内的 LLM 算子模型档位不一致")
    for op_code, operator_profile in profiles.items():
        if operator_profile != profile:
            raise ModelRoutingError(
                f"算子 {op_code} 声明模型档位 {operator_profile}，与规则档位 {profile} 冲突"
            )


def _iter_model_operators(ops: Any) -> Iterator[tuple[str, str]]:
    """遍历顶层与列表子算子中声明占用模型的算子。"""
    if not isinstance(ops, list):
        return
    for op_config in ops:
        if not isinstance(op_config, Mapping):
            continue
        op_code = op_config.get("op")
        if not isinstance(op_code, str):
            continue
        operator = get_operator(op_code)
        if operator is not None and operator.model_profile is not None:
            yield op_code, operator.model_profile

        params = op_config.get("params")
        if op_code == "list_for_each" and isinstance(params, Mapping):
            yield from _iter_model_operators(params.get("child_ops") or [])

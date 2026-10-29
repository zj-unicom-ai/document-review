# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""规则 DSL 保存前可执行性校验。"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.engine.model_routing import ModelRoutingError, validate_model_routing_values
from app.engine.tools import UnknownToolError, validate_tool_whitelist
from app.models.concept import Concept
from app.operators.registry import get_operator

_FULL_PLACEHOLDER = re.compile(r"^\$\{([A-Za-z0-9_]+)\}$")
_EMBEDDED_PLACEHOLDER = re.compile(r"\$\{([A-Za-z0-9_]+)\}")
_EVIDENCE_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


async def validate_rule_definition(
    session: AsyncSession,
    tenant_id: str,
    rule_type: str,
    definition: Mapping[str, Any],
    model_profile: str | None = None,
) -> None:
    """确保保存后的规则具备当前代码可执行的最小完整性。"""
    if not isinstance(definition, Mapping):
        raise ValidationError("规则 definition 必须是对象")

    try:
        validate_model_routing_values(
            rule_type=rule_type,
            model_profile=model_profile,
            definition=definition,
        )
    except ModelRoutingError as exc:
        raise ValidationError(str(exc)) from exc

    anchor = definition.get("anchor")
    concept_code = anchor.get("concept") if isinstance(anchor, Mapping) else None
    if not isinstance(concept_code, str) or not concept_code.strip():
        raise ValidationError("规则 anchor.concept 不能为空")

    concept = await _visible_concept(session, tenant_id, concept_code)
    if concept is None:
        raise ValidationError(f"概念不存在或租户不可见: {concept_code}")
    await _validate_evidence(session, tenant_id, definition)

    if rule_type == "llm":
        _validate_llm_definition(definition)
        return

    if rule_type not in {"structured", "hybrid"}:
        raise ValidationError(f"不支持的规则类型: {rule_type}")

    ops = definition.get("ops")
    if not isinstance(ops, list) or not ops:
        raise ValidationError("structured / hybrid 规则必须包含非空 ops 数组")

    raw_top_params = definition.get("params")
    top_params = raw_top_params if isinstance(raw_top_params, Mapping) else {}
    for index, op_config in enumerate(ops):
        if not isinstance(op_config, Mapping):
            raise ValidationError(f"ops[{index}] 必须是对象")

        op_code = op_config.get("op")
        operator = get_operator(str(op_code)) if isinstance(op_code, str) else None
        if operator is None:
            raise ValidationError(f"ops[{index}] 引用未知检查能力: {op_code}")

        if concept.data_kind not in operator.applicable_data_kind:
            raise ValidationError(
                f"ops[{index}] 数据类型不匹配：概念 {concept_code} 是 {concept.data_kind}，"
                f"检查能力仅支持 {','.join(operator.applicable_data_kind)}"
            )

        _validate_fail(index, op_config)
        raw_params = _resolve_placeholders(op_config.get("params", {}), top_params)
        try:
            operator.params_model.model_validate(raw_params)
        except PydanticValidationError as exc:
            detail = "; ".join(
                f"{'.'.join(str(part) for part in error['loc']) or 'params'}: {error['msg']}"
                for error in exc.errors()
            )
            raise ValidationError(f"ops[{index}] 参数不合法：{detail}") from exc


async def _visible_concept(
    session: AsyncSession, tenant_id: str, concept_code: str
) -> Concept | None:
    rows = (
        (
            await session.execute(
                select(Concept).where(
                    Concept.concept_code == concept_code,
                    Concept.is_deleted.is_(False),
                    or_(Concept.tenant_id == "", Concept.tenant_id == tenant_id),
                )
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return None
    if len(rows) > 1:
        raise ValidationError(f"概念 {concept_code} 可见记录不唯一，请先清理重复概念")
    return rows[0]


async def _validate_evidence(
    session: AsyncSession,
    tenant_id: str,
    definition: Mapping[str, Any],
) -> None:
    """校验可选多证据声明，避免运行期引用不可见概念。"""
    evidence = definition.get("evidence")
    if evidence is None:
        return
    if not isinstance(evidence, Mapping):
        raise ValidationError("规则 evidence 必须是对象")

    for key, spec in evidence.items():
        if not isinstance(key, str) or not _EVIDENCE_KEY.fullmatch(key):
            raise ValidationError(f"evidence key 只能使用字母、数字与下划线: {key}")
        if not isinstance(spec, Mapping):
            raise ValidationError(f"证据 {key} 必须是对象")
        concept_code = spec.get("concept")
        if not isinstance(concept_code, str) or not concept_code.strip():
            raise ValidationError(f"证据 {key} 缺少 concept")
        if await _visible_concept(session, tenant_id, concept_code) is None:
            raise ValidationError(f"证据 {key} 概念不存在或租户不可见: {concept_code}")
        if "required" in spec and not isinstance(spec.get("required"), bool):
            raise ValidationError(f"证据 {key}.required 必须是布尔值")


def _validate_fail(index: int, op_config: Mapping[str, Any]) -> None:
    fail = op_config.get("fail")
    if not isinstance(fail, Mapping):
        raise ValidationError(f"ops[{index}].fail 不能为空")
    for field in ("title", "content"):
        if not isinstance(fail.get(field), str) or not fail[field].strip():
            raise ValidationError(f"ops[{index}].fail.{field} 不能为空")


def _validate_llm_definition(definition: Mapping[str, Any]) -> None:
    instruction = definition.get("instruction")
    if not isinstance(instruction, str) or not instruction.strip():
        raise ValidationError("llm 规则 instruction 不能为空")

    output_schema = definition.get("output_schema")
    if not isinstance(output_schema, Mapping) or output_schema.get("type") != "object":
        raise ValidationError("llm 规则 output_schema 必须是 object Schema")

    tools = definition.get("tools", [])
    if not isinstance(tools, list):
        raise ValidationError("llm 规则 tools 必须是数组")
    try:
        validate_tool_whitelist(list(tools))
    except UnknownToolError as exc:
        raise ValidationError(f"llm 规则工具白名单不合法: {exc}") from exc


def _resolve_placeholders(value: Any, params: Mapping[str, Any]) -> Any:
    """保存前解析顶层参数占位符，让算子参数按真实类型校验。"""
    if isinstance(value, str):
        full = _FULL_PLACEHOLDER.fullmatch(value)
        if full and full.group(1) in params:
            return params[full.group(1)]

        def replace(match: re.Match[str]) -> str:
            replacement = params.get(match.group(1), match.group(0))
            return str(replacement)

        return _EMBEDDED_PLACEHOLDER.sub(replace, value)
    if isinstance(value, Mapping):
        return {key: _resolve_placeholders(item, params) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_placeholders(item, params) for item in value]
    return value

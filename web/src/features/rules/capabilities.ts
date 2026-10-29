// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import type { Concept, Operator, Rule } from "../../api/endpoints";

// LLM 理解类能力形态覆盖广、配置最简，作为新建规则默认推荐置顶展示。
export const AI_OPERATOR_CODE = "text_judge";
export const VISION_OPERATOR_CODE = "vision_judge";

/** 按概念数据形态过滤可用算子；文本 / 视觉理解置顶。 */
export function operatorsForConcept(concept: Concept, operators: Operator[]): Operator[] {
  const matched = operators.filter((op) => op.applicable_data_kind.includes(concept.data_kind));
  const recommended = [AI_OPERATOR_CODE, VISION_OPERATOR_CODE];
  return [
    ...matched.filter((op) => recommended.includes(op.op_code)),
    ...matched.filter((op) => !recommended.includes(op.op_code)),
  ];
}

function definition(record: Rule | undefined | null) {
  return (record?.definition ?? {}) as Record<string, unknown>;
}

/** 从规则锚点解析检查对象概念；不改变后端 DSL 契约。 */
export function conceptForRule(rule: Rule, concepts: Concept[]): Concept | null {
  const anchor = definition(rule).anchor as Record<string, unknown> | undefined;
  const conceptCode = typeof anchor?.concept === "string" ? anchor.concept : "";
  return concepts.find((item) => item.concept_code === conceptCode) ?? null;
}

function appendOperatorCodes(codes: string[], ops: unknown) {
  if (!Array.isArray(ops)) return;
  for (const item of ops) {
    if (!item || typeof item !== "object") continue;
    const record = item as Record<string, unknown>;
    if (typeof record.op === "string") codes.push(record.op);
    appendOperatorCodes(codes, record.child_ops);
  }
}

/** 解析规则实际使用的能力；llm 简化规则未写入 ops 时按模型档位映射。 */
export function capabilityNamesForRule(rule: Rule, operators: Operator[]): string[] {
  const nameByCode = new Map(operators.map((item) => [item.op_code, item.name] as const));
  const codes: string[] = [];
  appendOperatorCodes(codes, definition(rule).ops);

  if (!codes.length && rule.rule_type === "llm") {
    codes.push(rule.model_profile === "vision" ? VISION_OPERATOR_CODE : AI_OPERATOR_CODE);
  }

  return [...new Set(codes)].map((code) => nameByCode.get(code) ?? code);
}

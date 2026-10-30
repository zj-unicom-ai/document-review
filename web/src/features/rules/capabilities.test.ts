// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { expect, test } from "vitest";
import type { Concept, Operator, Rule } from "../../api/endpoints";
import { capabilityNamesForRule, conceptForRule, operatorsForConcept } from "./capabilities";

const concept: Concept = {
  id: 1,
  tenant_id: "",
  concept_code: "company_basic_info",
  concept_name: "企业基本信息表",
  aliases: [],
  data_kind: "table",
  source: "platform",
  created_at: "",
  updated_at: "",
};

function makeOperator(id: number, opCode: string, kinds: string[]): Operator {
  return {
    id,
    op_code: opCode,
    name: opCode,
    description: "",
    applicable_data_kind: kinds,
    params_schema: { type: "object" },
    result_semantics: "hit_is_violation",
    executor: `x:${opCode}`,
    model_profile: null,
    created_at: "",
    updated_at: "",
  };
}

const operators: Operator[] = [
  makeOperator(1, "extract_fields", ["field", "table"]),
  makeOperator(2, "text_judge", ["field", "section", "image_group", "item_list", "table", "document"]),
  makeOperator(3, "vision_judge", ["image_group"]),
  makeOperator(4, "external_data_check", ["field", "table"]),
];

const rule: Rule = {
  id: 10,
  tenant_id: "",
  rule_code: "R-001",
  name: "企业地址必填",
  description: null,
  rule_type: "structured",
  classify_id: null,
  severity_default: "一般",
  blocking_policy: "block",
  on_error_policy: "annotate",
  output_mode: "violations",
  model_profile: null,
  enabled: true,
  definition: {
    anchor: { concept: "company_basic_info", required: true },
    ops: [
      { op: "extract_fields", params: {} },
      {
        op: "list_for_each",
        params: {},
        child_ops: [{ op: "text_judge", params: {} }],
      },
    ],
  },
  note: null,
  created_at: "",
  updated_at: "",
};

test("BL-062：按概念形态过滤能力，文本理解置顶为默认", () => {
  const available = operatorsForConcept(concept, operators);

  expect(available.map((op) => op.op_code)).toEqual(["text_judge", "extract_fields", "external_data_check"]);
});

test("BL-062：图片概念下文本与视觉理解置顶", () => {
  const photoConcept: Concept = { ...concept, data_kind: "image_group" };

  expect(operatorsForConcept(photoConcept, operators).map((op) => op.op_code)).toEqual([
    "text_judge",
    "vision_judge",
  ]);
});

test("BL-090：从规则锚点和嵌套能力解析检查对象与检查能力", () => {
  expect(conceptForRule(rule, [concept])?.concept_name).toBe("企业基本信息表");
  expect(capabilityNamesForRule(rule, operators)).toEqual([
    "extract_fields",
    "list_for_each",
    "text_judge",
  ]);
});

test("BL-090：llm 规则按模型档位映射能力", () => {
  const textRule: Rule = {
    ...rule,
    rule_type: "llm",
    model_profile: "text",
    definition: { anchor: { concept: "missing_concept" } },
  };
  const visionRule: Rule = { ...textRule, model_profile: "vision" };

  expect(capabilityNamesForRule(textRule, operators)).toEqual(["text_judge"]);
  expect(capabilityNamesForRule(visionRule, operators)).toEqual(["vision_judge"]);
  expect(conceptForRule(textRule, [concept])).toBeNull();
});

// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { useEffect, useMemo, useState } from "react";
import {
  createRule,
  updateRule,
  type Classification,
  type Concept,
  type Operator,
  type Rule,
  type RuleCreate,
} from "../../api/endpoints";
import { Button } from "../../components/Button";
import { Modal } from "../../components/Modal";
import { Field, Select, TextInput } from "../../components/Field";
import { ErrorBanner } from "../../components/StateBlocks";
import { dataKindLabel } from "../../i18n/zh-CN";
import { operatorsForConcept } from "./capabilities";
import { ClassifySelect } from "./ClassifySelect";
import { SchemaField } from "./SchemaField";
import { defaultValuesFromSchema, serializeValuesBySchema, type FormValues, type JsonSchema } from "./schemaForm";
import { parseJsonDraft } from "../../utils/json";

type RuleFormState = {
  id?: number;
  rule_code: string;
  name: string;
  description: string;
  classify_id: string;
  severity_default: "严重" | "一般" | "提醒";
  failTitle: string;
  failContent: string;
};

// 清单逐项核查容器与可作为子检查的 AI 算子（BL-099 第一期口径）
const LIST_FOR_EACH_OP = "list_for_each";
const CHILD_CHECK_OPS = ["text_judge", "vision_judge"] as const;

type ChildCheck = {
  op_code: string;
  instruction: string;
  failTitle: string;
  failContent: string;
};

const emptyChildCheck = (): ChildCheck => ({
  op_code: "text_judge",
  instruction: "",
  failTitle: "",
  failContent: "",
});

const emptySchema: JsonSchema = { type: "object", properties: {} };

// AI 描述判断规则的固定输出契约；title / content 由 LLM 按规则名与描述输出。
const LLM_RULE_OUTPUT_SCHEMA: JsonSchema = {
  type: "object",
  properties: {
    violations: {
      type: "array",
      items: {
        type: "object",
        properties: {
          title: { type: "string" },
          content: { type: "string" },
          page_idx: { type: "integer" },
        },
        required: ["title", "content", "page_idx"],
      },
    },
    confidence: { type: "number" },
    reasoning: { type: "string" },
  },
  required: ["violations", "confidence", "reasoning"],
} as JsonSchema;

function initialState(rule: Rule | null, concepts: Concept[], operators: Operator[]) {
  const definition = (rule?.definition ?? {}) as Record<string, unknown>;
  const anchor = (definition.anchor ?? {}) as Record<string, unknown>;
  const ops = Array.isArray(definition.ops) ? (definition.ops as Array<Record<string, unknown>>) : [];
  const firstOp = ops[0] ?? {};
  const isLlmRule = rule?.rule_type === "llm";
  // 新建默认推荐 AI 描述判断；编辑按规则实际算子回填。
  const opCode = isLlmRule
    ? "text_judge"
    : typeof firstOp.op === "string"
      ? firstOp.op
      : "text_judge";
  const conceptCode = typeof anchor.concept === "string" ? anchor.concept : concepts[0]?.concept_code ?? "";
  const operator = operators.find((item) => item.op_code === opCode) ?? null;
  const schema = (operator?.params_schema ?? emptySchema) as JsonSchema;
  const topParams = (definition.params ?? {}) as FormValues;
  const opParams = (firstOp.params ?? {}) as FormValues;
  const fail = (firstOp.fail ?? {}) as Record<string, unknown>;
  const firstOpParams = (firstOp.params ?? {}) as Record<string, unknown>;
  const rawChildOps = Array.isArray(firstOpParams.child_ops)
    ? (firstOpParams.child_ops as Array<Record<string, unknown>>)
    : [];
  const childChecks: ChildCheck[] = rawChildOps.map((item) => {
    const params = (item.params ?? {}) as Record<string, unknown>;
    const fail = (item.fail ?? {}) as Record<string, unknown>;
    return {
      op_code: typeof item.op === "string" ? item.op : "text_judge",
      instruction: typeof params.instruction === "string" ? params.instruction : "",
      failTitle: typeof fail.title === "string" ? fail.title : "",
      failContent: typeof fail.content === "string" ? fail.content : "",
    };
  });
  // hybrid + 单个逐条核查容器 + 子检查均为第一期支持算子时走表单模式，其余保持 JSON。
  const isListForEachForm =
    rule?.rule_type === "hybrid" &&
    ops.length === 1 &&
    firstOp.op === LIST_FOR_EACH_OP &&
    childChecks.every((check) => CHILD_CHECK_OPS.includes(check.op_code as "text_judge"));
  const instruction =
    typeof definition.instruction === "string"
      ? definition.instruction
      : typeof firstOpParams.instruction === "string"
        ? firstOpParams.instruction
        : "";
  // 含表单外高级字段（tools / budget 等）的 llm 规则回 JSON 模式，避免编辑时丢字段。
  const hasAdvancedLlmFields = [
    "tools",
    "budget",
    "params",
    "secondary_concepts",
    "context_scopes",
    "require_evidence",
    "require_visual_coverage",
  ].some((key) => key in definition);
  return {
    open: Boolean(rule),
    conceptCode,
    instruction,
    opCode,
    paramValues: { ...defaultValuesFromSchema(schema), ...topParams, ...opParams },
    form: {
      id: rule?.id,
      rule_code: rule?.rule_code ?? "",
      name: rule?.name ?? "",
      description: rule?.description ?? "",
      classify_id: rule?.classify_id ? String(rule.classify_id) : "",
      severity_default: rule?.severity_default ?? "一般",
      failTitle: typeof fail.title === "string" ? fail.title : "",
      failContent: typeof fail.content === "string" ? fail.content : "",
    },
    advancedMode: Boolean(rule) && (isLlmRule
      ? hasAdvancedLlmFields
      : isListForEachForm ? false : rule?.rule_type !== "structured" || ops.length !== 1),
    advancedDraft: JSON.stringify(definition, null, 2),
    childChecks,
  };
}

const propertyLabels: Record<string, string> = {
  fields: "提取字段清单",
  output_key: "输出保存名",
  instruction: "检查要求描述",
  output_schema: "输出数据格式",
  max_input_chars: "最大输入字符数",
  max_images: "最多图片数",
  resource_key: "外部资源标识",
  query: "查询条件",
  match_field: "核验字段名",
  fallback_value: "兜底值",
  child_ops: "子检查列表",
  child_params_from_item: "从列表项取值的参数",
};

// 参数级填写示例：让非技术用户不看文档也知道填什么（BL-056 A2）。
const paramHints: Record<string, string> = {
  fields: "填要提取的栏目名，多个用逗号分隔。例如：企业名称, 地址",
  resource_key: "填外部资源登记标识。例如：expert_library",
  query: "填查询条件 JSON。例如：{\"type\": \"fire\"}",
  match_field: "填要与外部数据比对的栏目名。例如：企业名称",
  output_key: "填提取结果的保存名。例如：company_info",
};

export function RuleEditor({
  concepts,
  operators,
  classifications,
  initialRule,
  open,
  onCancel,
  onSaved,
}: {
  concepts: Concept[];
  operators: Operator[];
  classifications: Classification[];
  initialRule: Rule | null;
  open: boolean;
  onCancel: () => void;
  onSaved: (rule: Rule) => void;
}) {
  const initial = useMemo(
    () => initialState(initialRule, concepts, operators),
    [classifications, concepts, initialRule, operators],
  );
  const [conceptCode, setConceptCode] = useState(initial.conceptCode);
  const [opCode, setOpCode] = useState(initial.opCode);
  const [instruction, setInstruction] = useState(initial.instruction);
  const [paramValues, setParamValues] = useState<FormValues>(initial.paramValues);
  const [form, setForm] = useState<RuleFormState>(initial.form);
  const [childChecks, setChildChecks] = useState<ChildCheck[]>(initial.childChecks);
  const [advancedMode, setAdvancedMode] = useState(initial.advancedMode);
  const [advancedDraft, setAdvancedDraft] = useState(initial.advancedDraft);
  const [errors, setErrors] = useState<string[]>([]);
  const [saveError, setSaveError] = useState("");
  const [saving, setSaving] = useState(false);

  const concept =
    concepts.find((item) => item.concept_code === conceptCode) ??
    (conceptCode ? null : concepts[0] ?? null);
  // 按检查对象形态过滤算子，LLM 理解类能力置顶为默认推荐。
  const availableOperators = useMemo(
    () => (concept ? operatorsForConcept(concept, operators) : []),
    [concept, operators],
  );
  const operator = availableOperators.find((item) => item.op_code === opCode) ?? availableOperators[0] ?? null;
  const isAiOperator =
    operator?.op_code === "text_judge" || operator?.op_code === "vision_judge";
  const isListForEach = operator?.op_code === LIST_FOR_EACH_OP;
  // 子检查算子不受锚点数据类型过滤（视觉理解本身只挂照片组，但可作为清单子检查）
  const childOperators = useMemo(
    () => operators.filter((item) => CHILD_CHECK_OPS.includes(item.op_code as "text_judge")),
    [operators],
  );
  const schema = (operator?.params_schema ?? emptySchema) as JsonSchema;

  useEffect(() => {
    if (operator) {
      setParamValues(defaultValuesFromSchema(operator.params_schema as JsonSchema));
    }
  }, [operator?.op_code]);

  function resetNewForm() {
    const next = initialState(null, concepts, operators);
    setConceptCode(next.conceptCode);
    setOpCode(next.opCode);
    setInstruction(next.instruction);
    setParamValues(next.paramValues);
    setForm(next.form);
    setChildChecks([]);
    setAdvancedMode(false);
    setAdvancedDraft("{}");
    setErrors([]);
    setSaveError("");
  }

  function closeEditor() {
    // 新增态由父页面受控展示；先清理草稿，再通知父组件关闭。
    if (!form.id) {
      resetNewForm();
    }
    onCancel();
  }

  function selectConcept(nextConceptCode: string) {
    const nextConcept = concepts.find((item) => item.concept_code === nextConceptCode);
    setConceptCode(nextConceptCode);
    if (!nextConcept) {
      setOpCode("");
      setParamValues({});
      return;
    }
    // 切换检查对象后按新形态取可用算子，AI 内容判断置顶为默认。
    const nextOperators = operatorsForConcept(nextConcept, operators);
    const nextOperator = nextOperators[0];
    setOpCode(nextOperator?.op_code ?? "");
    setParamValues(defaultValuesFromSchema((nextOperator?.params_schema ?? emptySchema) as JsonSchema));
  }

  function buildDefinition() {
    if (!operator || !concept) {
      return {};
    }
    if (isListForEach) {
      const classifyId = form.classify_id ? Number(form.classify_id) : undefined;
      return {
        anchor: { concept: concept.concept_code, required: true },
        params: {},
        ops: [
          {
            op: LIST_FOR_EACH_OP,
            params: {
              child_ops: childChecks.map((check) => ({
                op: check.op_code,
                params: { instruction: check.instruction.trim() },
                fail: {
                  title: check.failTitle.trim() || form.name || "检查未通过",
                  content: check.failContent.trim() || "文档内容不满足检查要求",
                  severity: form.severity_default,
                  classify_id: classifyId,
                },
              })),
            },
            // 外层 fail 为保存校验必填项；逐条命中按子检查模板装配，外层不生效。
            fail: {
              title: form.name || "清单逐条核查未通过",
              content: form.description || "清单条目未满足子检查要求。",
              severity: form.severity_default,
              classify_id: classifyId,
            },
          },
        ],
      };
    }
    const params = serializeValuesBySchema(schema, paramValues);
    return {
      anchor: { concept: concept.concept_code, required: true },
      params,
      ops: [
        {
          op: operator.op_code,
          params: Object.fromEntries(Object.keys(params).map((key) => [key, `\${${key}}`])),
          fail: {
            title: form.failTitle || form.name || "检查未通过",
            content: form.failContent || form.description || "文档内容不满足检查要求",
            severity: form.severity_default,
            classify_id: form.classify_id ? Number(form.classify_id) : undefined,
          },
        },
      ],
    };
  }

  function preparePayload(): RuleCreate | null {
    const localErrors: string[] = [];
    if (!form.rule_code.trim()) localErrors.push("规则代码不能为空");
    if (!form.name.trim()) localErrors.push("规则名称不能为空");
    if (!concept) localErrors.push("请选择检查对象");
    if (isListForEach) {
      if (!childChecks.length) localErrors.push("至少添加一条子检查");
      childChecks.forEach((check, index) => {
        const no = index + 1;
        if (!check.instruction.trim()) localErrors.push(`第 ${no} 条子检查的检查要求描述不能为空`);
        if (!check.failTitle.trim()) localErrors.push(`第 ${no} 条子检查的违规标题不能为空`);
        if (!check.failContent.trim()) localErrors.push(`第 ${no} 条子检查的违规内容不能为空`);
      });
      // 引擎约束：同一 hybrid 规则内 LLM 算子必须同档位，混用会被后端拒绝。
      if (new Set(childChecks.map((check) => check.op_code)).size > 1) {
        localErrors.push("子检查能力需一致：文本理解与视觉理解不能混用在同一条规则");
      }
      setErrors(localErrors);
      if (localErrors.length || !concept) {
        return null;
      }
      return {
        rule_code: form.rule_code.trim(),
        name: form.name.trim(),
        description: form.description,
        rule_type: "hybrid" as const,
        classify_id: form.classify_id ? Number(form.classify_id) : null,
        severity_default: form.severity_default,
        blocking_policy: "block" as const,
        on_error_policy: "annotate" as const,
        output_mode: "violations" as const,
        model_profile: childChecks.some((check) => check.op_code === "vision_judge") ? "vision" : "text",
        enabled: true,
        definition: buildDefinition(),
        note: null,
      };
    }
    // AI 描述判断：一句话描述即规则，违规标题 / 内容由 LLM 输出装配。
    if (isAiOperator) {
      if (!instruction.trim()) {
        localErrors.push("请填写检查要求描述");
      }
      setErrors(localErrors);
      if (localErrors.length || !concept) {
        return null;
      }
      return {
        rule_code: form.rule_code.trim(),
        name: form.name.trim(),
        description: form.description || instruction.trim(),
        rule_type: "llm",
        classify_id: form.classify_id ? Number(form.classify_id) : null,
        severity_default: form.severity_default,
        blocking_policy: "block" as const,
        on_error_policy: "annotate" as const,
        output_mode: "violations" as const,
        model_profile: operator.op_code === "vision_judge" ? "vision" : "text",
        enabled: true,
        definition: {
          anchor: { concept: concept.concept_code, required: true },
          instruction: instruction.trim(),
          output_schema: LLM_RULE_OUTPUT_SCHEMA,
        },
        note: null,
      };
    }

    if (!operator) localErrors.push("该检查对象暂无可用检查方式");
    if (!form.failTitle.trim()) localErrors.push("违规标题不能为空");
    if (!form.failContent.trim()) localErrors.push("违规内容不能为空");

    let definition: Record<string, unknown> | null = null;
    if (operator) {
      try {
        definition = advancedMode
          ? parseJsonDraft<Record<string, unknown>>(advancedDraft)
          : buildDefinition();
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        localErrors.push(
          Object.entries(propertyLabels).reduce(
            (result, [key, label]) => result.replaceAll(key, label),
            message,
          ),
        );
      }
    }
    setErrors(localErrors);
    if (localErrors.length || !definition) {
      return null;
    }

    return {
      rule_code: form.rule_code.trim(),
      name: form.name.trim(),
      description: form.description,
      // 编辑既有规则时 JSON 模式保留原类型与档位，避免 hybrid 被误标为 structured
      rule_type: (form.id ? initialRule?.rule_type : undefined) ?? "structured",
      classify_id: form.classify_id ? Number(form.classify_id) : null,
      severity_default: form.severity_default,
      blocking_policy: "block" as const,
      on_error_policy: "annotate" as const,
      output_mode: "violations" as const,
      model_profile: form.id ? initialRule?.model_profile ?? null : null,
      enabled: true,
      definition,
      note: null,
    };
  }

  async function save() {
    const payload = preparePayload();
    if (!payload) {
      return;
    }

    setSaving(true);
    setSaveError("");
    try {
      const saved = form.id ? await updateRule(form.id, payload) : await createRule(payload);
      onSaved(saved);
      if (!form.id) {
        resetNewForm();
      }
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : String(error));
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return null;
  }

  return (
    <Modal title={form.id ? "编辑规则" : "新增规则"} open onClose={closeEditor}>
      <div className="rule-editor-form">
      {errors.length ? <ErrorBanner error={errors.join("；")} title="表单校验失败" /> : null}
      <ErrorBanner error={saveError} />

      <div className="form-grid">
        <Field label="规则代码" required>
          <TextInput value={form.rule_code} disabled={Boolean(form.id)} onChange={(event) => setForm({ ...form, rule_code: event.target.value })} />
        </Field>
        <Field label="规则名称" required>
          <TextInput value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
        </Field>
        <Field label="检查对象" required>
          <Select
            value={concept?.concept_code ?? ""}
            onChange={(event) => {
              selectConcept(event.target.value);
            }}
          >
            {concepts.map((item) => (
              <option key={item.id} value={item.concept_code}>
                {item.concept_name}（{dataKindLabel(item.data_kind)}）
              </option>
            ))}
          </Select>
        </Field>
        <Field label="检查能力" required>
          <Select
            value={operator?.op_code ?? ""}
            onChange={(event) => {
              const nextOperator = availableOperators.find((item) => item.op_code === event.target.value);
              setOpCode(event.target.value);
              setParamValues(defaultValuesFromSchema((nextOperator?.params_schema ?? emptySchema) as JsonSchema));
            }}
            disabled={!operator}
          >
            {availableOperators.map((item) => (
              <option key={item.id} value={item.op_code}>
                {item.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="默认级别">
          <Select value={form.severity_default} onChange={(event) => setForm({ ...form, severity_default: event.target.value as RuleFormState["severity_default"] })}>
            <option value="严重">严重</option>
            <option value="一般">一般</option>
            <option value="提醒">提醒</option>
          </Select>
        </Field>
        <Field label="业务分类">
          <ClassifySelect
            classifications={classifications}
            value={form.classify_id ? Number(form.classify_id) : null}
            onChange={(classifyId) =>
              setForm({ ...form, classify_id: classifyId === null ? "" : String(classifyId) })
            }
          />
        </Field>
      </div>

      {!operator ? (
        <div className="capability-placeholder">该检查对象暂无可用检查方式。</div>
      ) : (
        <>
          {isListForEach ? (
            <div className="child-check-stack">
              <p className="capability-note">
                逐条核查会对清单中的每一条记录分别执行下列子检查；检查要求与违规标题 / 内容
                可用 <code>{"{{item.字段}}"}</code> 引用当前条目内容（例如 <code>{"{{item.description}}"}</code>）。
              </p>
              {childChecks.map((check, index) => (
                <div className="child-check-card" key={index}>
                  <div className="form-grid">
                    <Field label={`第 ${index + 1} 条子检查能力`} required>
                      <Select
                        value={check.op_code}
                        onChange={(event) =>
                          setChildChecks(
                            childChecks.map((item, i) =>
                              i === index ? { ...item, op_code: event.target.value } : item,
                            ),
                          )
                        }
                      >
                        {childOperators.map((item) => (
                          <option key={item.id} value={item.op_code}>
                            {item.name}
                          </option>
                        ))}
                      </Select>
                    </Field>
                    <Field label={`第 ${index + 1} 条违规标题（模板）`} required>
                      <TextInput
                        value={check.failTitle}
                        placeholder="例如：隐患{{item.no}}整改建议不具体"
                        onChange={(event) =>
                          setChildChecks(
                            childChecks.map((item, i) =>
                              i === index ? { ...item, failTitle: event.target.value } : item,
                            ),
                          )
                        }
                      />
                    </Field>
                    <Field label={`第 ${index + 1} 条违规内容（模板）`} required>
                      <TextInput
                        value={check.failContent}
                        placeholder="例如：隐患{{item.no}}的整改建议未写明具体措施"
                        onChange={(event) =>
                          setChildChecks(
                            childChecks.map((item, i) =>
                              i === index ? { ...item, failContent: event.target.value } : item,
                            ),
                          )
                        }
                      />
                    </Field>
                  </div>
                  <Field label={`第 ${index + 1} 条检查要求（一句话，AI 执行时按此判断）`} required>
                    <textarea
                      className="text-input"
                      rows={3}
                      placeholder="例如：整改建议必须写明具体措施，过于笼统即不合规"
                      value={check.instruction}
                      onChange={(event) =>
                        setChildChecks(
                          childChecks.map((item, i) =>
                            i === index ? { ...item, instruction: event.target.value } : item,
                          ),
                        )
                      }
                    />
                  </Field>
                  <Button
                    type="button"
                    onClick={() => setChildChecks(childChecks.filter((_, i) => i !== index))}
                  >
                    删除该子检查
                  </Button>
                </div>
              ))}
              <Button type="button" onClick={() => setChildChecks([...childChecks, emptyChildCheck()])}>
                添加子检查
              </Button>
            </div>
          ) : isAiOperator ? (
            <Field label="规则描述" required>
              <textarea
                className="text-input"
                rows={3}
                placeholder="请输入检查描述，AI执行时按此判断"
                value={instruction}
                onChange={(event) => setInstruction(event.target.value)}
              />
            </Field>
          ) : (
            <>
              <div className="form-grid">
                {Object.entries(schema.properties ?? {}).map(([key, property]) => {
                  const requiredKeys = (schema.required ?? []) as string[];
                  return (
                    <SchemaField
                      key={key}
                      schema={property}
                      label={`${operator.name}：${propertyLabels[key] ?? property.title ?? key}`}
                      placeholder={paramHints[key]}
                      required={requiredKeys.includes(key)}
                      value={paramValues[key]}
                      onChange={(value) => setParamValues({ ...paramValues, [key]: value })}
                    />
                  );
                })}
              </div>
              <div className="form-grid">
                <Field label="违规标题" required>
                  <TextInput value={form.failTitle} onChange={(event) => setForm({ ...form, failTitle: event.target.value })} />
                </Field>
                <Field label="违规内容" required>
                  <TextInput value={form.failContent} onChange={(event) => setForm({ ...form, failContent: event.target.value })} />
                </Field>
              </div>
            </>
          )}
        </>
      )}

      <div className="form-actions">
        <Button type="button" onClick={closeEditor}>
          取消
        </Button>
        <Button type="button" variant="primary" disabled={!operator || saving} onClick={() => void save()}>
          保存规则
        </Button>
      </div>
      </div>
    </Modal>
  );
}

// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { fireEvent } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, expect, test, vi } from "vitest";
import type { Classification, Concept, Operator, Rule } from "../../api/endpoints";
import { createRule, updateRule } from "../../api/endpoints";
import { RuleEditor } from "./RuleEditor";

vi.mock("../../api/endpoints", () => ({
  createRule: vi.fn(),
  updateRule: vi.fn(),
}));

const concepts: Concept[] = [
  {
    id: 1,
    tenant_id: "",
    concept_code: "company_basic_info",
    concept_name: "企业基本信息表",
    aliases: [],
    data_kind: "table",
    source: "platform",
    created_at: "",
    updated_at: "",
  },
];

const operators: Operator[] = [
  {
    id: 1,
    op_code: "extract_fields",
    name: "信息提取",
    description: "从锚点范围提取指定信息供后续规则使用",
    applicable_data_kind: ["field", "table"],
    params_schema: {
      type: "object",
      required: ["fields"],
      properties: {
        fields: { type: "array", items: { type: "string" } },
      },
    },
    result_semantics: "hit_is_violation",
    executor: "app.operators.extract_fields:ExtractFields",
    model_profile: null,
    created_at: "",
    updated_at: "",
  },
];

const llmJudgeOperator: Operator = {
  ...operators[0],
  id: 2,
  op_code: "text_judge",
  name: "文本理解",
  description: "阅读锚点锁定的文本内容，按规则的自然语言描述判断是否合规",
  applicable_data_kind: ["field", "section", "image_group", "item_list", "table", "document"],
  params_schema: { type: "object" },
};

const classifications: Classification[] = [];

beforeEach(() => {
  vi.mocked(createRule).mockClear();
});

function Harness() {
  const [payload, setPayload] = useState<unknown>(null);
  return (
    <>
      <RuleEditor
        open
        concepts={concepts}
        operators={operators}
        classifications={classifications}
        initialRule={null}
        onCancel={() => undefined}
        onSaved={(rule) => setPayload(rule)}
      />
      {payload ? <pre>{JSON.stringify(payload)}</pre> : null}
    </>
  );
}

test("业务用户通过表单创建规则且页面不暴露 op_code", async () => {
  vi.mocked(createRule).mockResolvedValue({
    id: 9,
    tenant_id: "tenant-A",
    rule_code: "FORM-001",
    name: "企业地址必填",
    description: "",
    rule_type: "structured",
    classify_id: null,
    severity_default: "一般",
    blocking_policy: "block",
    on_error_policy: "annotate",
    output_mode: "violations",
    model_profile: null,
    enabled: true,
    definition: {},
    note: null,
    created_at: "",
    updated_at: "",
  });
  const user = userEvent.setup();
  render(<Harness />);

  // BL-098 A4：检查对象下拉的数据类型展示中文标签
  expect(screen.getByRole("option", { name: "企业基本信息表（表格）" })).toBeInTheDocument();
  expect(screen.queryByText("企业基本信息表（table）")).not.toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("检查对象"), "company_basic_info");
  await user.selectOptions(screen.getByLabelText("检查能力"), "extract_fields");
  await user.selectOptions(screen.getByLabelText("检查能力"), "extract_fields");
  await user.type(screen.getByLabelText("规则代码"), "FORM-001");
  await user.type(screen.getByLabelText("规则名称"), "企业地址必填");
  await user.type(screen.getByLabelText("信息提取：提取字段清单"), "企业地址");
  await user.type(screen.getByLabelText("违规标题"), "企业地址缺失");
  await user.type(screen.getByLabelText("违规内容"), "企业地址不能为空");
  await user.click(screen.getByRole("button", { name: "保存规则" }));

  expect(createRule).toHaveBeenCalledTimes(1);
  expect(await screen.findByText(/FORM-001/)).toBeInTheDocument();
  expect(document.body.textContent).not.toContain("extract_fields");
});

test("无匹配检查能力时显示能力边界并禁止保存", () => {
  render(
    <RuleEditor
      open
      concepts={concepts}
      operators={[]}
      classifications={classifications}
      initialRule={null}
      onCancel={() => undefined}
      onSaved={() => undefined}
    />,
  );


  expect(screen.getByText(/该检查对象暂无可用检查方式/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "保存规则" })).toBeDisabled();
});

test("必填参数和违规输出缺失时保留用户已填内容", async () => {
  const user = userEvent.setup();
  render(
    <RuleEditor
      open
      concepts={concepts}
      operators={operators}
      classifications={classifications}
      initialRule={null}
      onCancel={() => undefined}
      onSaved={() => undefined}
    />,
  );

  await user.selectOptions(screen.getByLabelText("检查能力"), "extract_fields");

  await user.type(screen.getByLabelText("规则代码"), "FORM-002");
  await user.type(screen.getByLabelText("规则名称"), "企业名称必填");
  await user.click(screen.getByRole("button", { name: "保存规则" }));

  expect(await screen.findByText(/提取字段清单 至少需要一个值/)).toBeInTheDocument();
  expect(screen.getByText(/违规标题不能为空/)).toBeInTheDocument();
  // BL-101：必填字段渲染红色星号（伪元素，label 文本不受污染）
  expect(document.querySelectorAll(".field-label.is-required").length).toBeGreaterThan(0);
  expect(screen.getByLabelText("规则代码")).toHaveValue("FORM-002");
  expect(screen.getByLabelText("规则名称")).toHaveValue("企业名称必填");
  expect(createRule).not.toHaveBeenCalled();
});

test("后端校验失败时展示错误且保留表单值", async () => {
  vi.mocked(createRule).mockRejectedValueOnce(new Error("概念不存在或租户不可见"));
  const user = userEvent.setup();
  render(
    <RuleEditor
      open
      concepts={concepts}
      operators={operators}
      classifications={classifications}
      initialRule={null}
      onCancel={() => undefined}
      onSaved={() => undefined}
    />,
  );

  await user.selectOptions(screen.getByLabelText("检查能力"), "extract_fields");

  await user.type(screen.getByLabelText("规则代码"), "FORM-004");
  await user.type(screen.getByLabelText("规则名称"), "后端错误保留");
  await user.type(screen.getByLabelText("信息提取：提取字段清单"), "企业名称");
  await user.type(screen.getByLabelText("违规标题"), "企业名称缺失");
  await user.type(screen.getByLabelText("违规内容"), "企业名称不能为空");
  await user.click(screen.getByRole("button", { name: "保存规则" }));

  expect(await screen.findByText(/概念不存在或租户不可见/)).toBeInTheDocument();
  expect(screen.getByLabelText("规则代码")).toHaveValue("FORM-004");
  expect(screen.getByLabelText("规则名称")).toHaveValue("后端错误保留");
  expect(screen.getByLabelText("违规标题")).toHaveValue("企业名称缺失");
});

test("BL-055 A1/A2：文本理解只需一句话描述即可创建规则", async () => {
  vi.mocked(createRule).mockResolvedValue({
    id: 10,
    tenant_id: "tenant-A",
    rule_code: "AI-001",
    name: "地址精确到街道",
    description: "地址需要精确到街道及以下",
    rule_type: "llm",
    classify_id: null,
    severity_default: "一般",
    blocking_policy: "block",
    on_error_policy: "annotate",
    output_mode: "violations",
    model_profile: "text",
    enabled: true,
    definition: {},
    note: null,
    created_at: "",
    updated_at: "",
  });
  const user = userEvent.setup();
  render(
    <RuleEditor
      open
      concepts={concepts}
      operators={[...operators, llmJudgeOperator]}
      classifications={classifications}
      initialRule={null}
      onCancel={() => undefined}
      onSaved={() => undefined}
    />,
  );

  await user.selectOptions(screen.getByLabelText("检查对象"), "company_basic_info");
  expect(screen.getByLabelText("规则描述")).toBeInTheDocument();
  await user.type(screen.getByLabelText("规则代码"), "AI-001");
  await user.type(screen.getByLabelText("规则名称"), "地址精确到街道");
  await user.type(
    screen.getByLabelText("规则描述"),
    "地址需要精确到街道及以下，未写到街道/镇/乡级别即不合规",
  );
  await user.click(screen.getByRole("button", { name: "保存规则" }));

  expect(createRule).toHaveBeenCalledTimes(1);
  const payload = vi.mocked(createRule).mock.calls[0][0];
  expect(payload.rule_type).toBe("llm");
  expect(payload.model_profile).toBe("text");
  const definition = payload.definition as {
    instruction: string;
    output_schema: { required: string[] };
  };
  expect(definition.instruction).toContain("地址需要精确到街道及以下");
  expect(definition.output_schema.required).toEqual(["violations", "confidence", "reasoning"]);
});

test("BL-055 E1：AI 描述为空拦截保存", async () => {
  const user = userEvent.setup();
  render(
    <RuleEditor
      open
      concepts={concepts}
      operators={[...operators, llmJudgeOperator]}
      classifications={classifications}
      initialRule={null}
      onCancel={() => undefined}
      onSaved={() => undefined}
    />,
  );

  await user.type(screen.getByLabelText("规则代码"), "AI-002");
  await user.type(screen.getByLabelText("规则名称"), "描述为空");
  await user.click(screen.getByRole("button", { name: "保存规则" }));

  expect(screen.getByText(/请填写检查要求描述/)).toBeInTheDocument();
  expect(createRule).not.toHaveBeenCalled();
});


test("BL-060：含明细的一级点击展开，选择二级完成挂载", async () => {
  const classificationsWithTree: Classification[] = [
    { id: 50, classify_id: 9001, parent_id: null, level: 1, name: "含明细的父级", sort_order: 0, tenant_id: "", created_at: "", updated_at: "" },
    { id: 51, classify_id: 9002, parent_id: 50, level: 2, name: "末级分类", sort_order: 1, tenant_id: "", created_at: "", updated_at: "" },
    { id: 52, classify_id: 9003, parent_id: null, level: 1, name: "独立一级分类", sort_order: 9, tenant_id: "", created_at: "", updated_at: "" },
  ];
  vi.mocked(createRule).mockResolvedValue({
    id: 11,
    tenant_id: "tenant-A",
    rule_code: "CLS-001",
    name: "分类测试",
    description: "",
    rule_type: "llm",
    classify_id: 51,
    severity_default: "一般",
    blocking_policy: "block",
    on_error_policy: "annotate",
    output_mode: "violations",
    model_profile: "text",
    enabled: true,
    definition: {},
    note: null,
    created_at: "",
    updated_at: "",
  });
  const user = userEvent.setup();
  render(
    <RuleEditor
      open
      concepts={concepts}
      operators={[...operators, llmJudgeOperator]}
      classifications={classificationsWithTree}
      initialRule={null}
      onCancel={() => undefined}
      onSaved={() => undefined}
    />,
  );

  await user.click(screen.getByLabelText("业务分类"));
  // 含明细的一级只展开不作为选择项。
  await user.click(screen.getByRole("button", { name: /含明细的父级/ }));
  await user.click(screen.getByRole("option", { name: "末级分类" }));
  await user.type(screen.getByLabelText("规则代码"), "CLS-001");
  await user.type(screen.getByLabelText("规则名称"), "分类测试");
  await user.type(screen.getByLabelText("规则描述"), "检查要求描述");
  await user.click(screen.getByRole("button", { name: "保存规则" }));

  expect(createRule).toHaveBeenCalledTimes(1);
  expect(vi.mocked(createRule).mock.calls[0][0].classify_id).toBe(51);
});

test("BL-060：无明细一级点击即挂载，不出现二级", async () => {
  const classificationsWithTree: Classification[] = [
    { id: 50, classify_id: 9001, parent_id: null, level: 1, name: "含明细的父级", sort_order: 0, tenant_id: "", created_at: "", updated_at: "" },
    { id: 51, classify_id: 9002, parent_id: 50, level: 2, name: "末级分类", sort_order: 1, tenant_id: "", created_at: "", updated_at: "" },
    { id: 52, classify_id: 9003, parent_id: null, level: 1, name: "独立一级分类", sort_order: 9, tenant_id: "", created_at: "", updated_at: "" },
  ];
  const user = userEvent.setup();
  render(
    <RuleEditor
      open
      concepts={concepts}
      operators={[...operators, llmJudgeOperator]}
      classifications={classificationsWithTree}
      initialRule={null}
      onCancel={() => undefined}
      onSaved={() => undefined}
    />,
  );

  await user.click(screen.getByLabelText("业务分类"));
  await user.click(screen.getByRole("option", { name: "独立一级分类" }));

  expect(screen.getByText("独立一级分类")).toBeInTheDocument();
  // 展开面板收起后无二级输入（一级即最末级）。
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
});

test("保存新增规则后清理旧表单", async () => {
  vi.mocked(createRule).mockResolvedValue({
    id: 9,
    tenant_id: "tenant-A",
    rule_code: "FORM-RESET",
    name: "企业地址必填",
    description: "",
    rule_type: "structured",
    classify_id: null,
    severity_default: "一般",
    blocking_policy: "block",
    on_error_policy: "annotate",
    output_mode: "violations",
    model_profile: null,
    enabled: true,
    definition: {},
    note: null,
    created_at: "",
    updated_at: "",
  });
  const user = userEvent.setup();
  render(
    <RuleEditor
      open
      concepts={concepts}
      operators={operators}
      classifications={classifications}
      initialRule={null}
      onCancel={() => undefined}
      onSaved={() => undefined}
    />,
  );

  await user.selectOptions(screen.getByLabelText("检查对象"), "company_basic_info");
  await user.selectOptions(screen.getByLabelText("检查能力"), "extract_fields");
  await user.type(screen.getByLabelText("规则代码"), "FORM-RESET");
  await user.type(screen.getByLabelText("规则名称"), "企业地址必填");
  await user.type(screen.getByLabelText("信息提取：提取字段清单"), "企业地址");
  await user.type(screen.getByLabelText("违规标题"), "企业地址缺失");
  await user.type(screen.getByLabelText("违规内容"), "企业地址不能为空");
  await user.click(screen.getByRole("button", { name: "保存规则" }));

  await waitFor(() => {
    expect(screen.getByLabelText("规则代码")).toHaveValue("");
  });
  expect(vi.mocked(createRule)).toHaveBeenCalledTimes(1);
});


test("新增规则点击关闭按钮通知父组件关闭并清理表单", async () => {
  const onCancel = vi.fn();
  const user = userEvent.setup();
  render(
    <RuleEditor
      open
      concepts={concepts}
      operators={operators}
      classifications={classifications}
      initialRule={null}
      onCancel={onCancel}
      onSaved={() => undefined}
    />,
  );

  await user.type(screen.getByLabelText("规则代码"), "CLOSE-001");
  await user.click(screen.getByRole("button", { name: "关闭" }));

  expect(onCancel).toHaveBeenCalledTimes(1);
  expect(screen.getByLabelText("规则代码")).toHaveValue("");
});

test("新增规则点击取消通知父组件关闭并清理表单", async () => {
  const onCancel = vi.fn();
  const user = userEvent.setup();
  render(
    <RuleEditor
      open
      concepts={concepts}
      operators={operators}
      classifications={classifications}
      initialRule={null}
      onCancel={onCancel}
      onSaved={() => undefined}
    />,
  );

  await user.type(screen.getByLabelText("规则代码"), "CANCEL-001");
  await user.click(screen.getByRole("button", { name: "取消" }));

  expect(onCancel).toHaveBeenCalledTimes(1);
  expect(screen.getByLabelText("规则代码")).toHaveValue("");
});

// ---------- BL-099：清单逐条核查（hybrid）表单 ----------

const itemConcept: Concept = {
  ...concepts[0],
  id: 2,
  concept_code: "item_list",
  concept_name: "条目列表",
  data_kind: "item_list",
};

const listForEachOperator: Operator = {
  ...operators[0],
  id: 3,
  op_code: "list_for_each",
  name: "清单逐条核查",
  description: "对清单中的每一条记录逐条执行子检查。",
  applicable_data_kind: ["item_list"],
  params_schema: { type: "object" },
};

const visionJudgeOperator: Operator = {
  ...operators[0],
  id: 4,
  op_code: "vision_judge",
  name: "视觉理解",
  description: "理解图片内容并按自然语言要求判断。",
  applicable_data_kind: ["image_group"],
  params_schema: { type: "object" },
};

function renderListForEachEditor(initialRule: Rule | null = null) {
  render(
    <RuleEditor
      open
      concepts={[...concepts, itemConcept]}
      operators={[...operators, listForEachOperator, visionJudgeOperator]}
      classifications={classifications}
      initialRule={initialRule}
      onCancel={() => undefined}
      onSaved={() => undefined}
    />,
  );
}

test("BL-099 A1/A2/A3: 逐条核查配置提交 hybrid DSL 且视觉档位正确", async () => {
  vi.mocked(createRule).mockResolvedValue({ ...concepts[0], id: 10 } as never);
  const user = userEvent.setup();
  renderListForEachEditor();

  await user.selectOptions(screen.getByLabelText("检查对象"), "item_list");
  await user.selectOptions(screen.getByLabelText("检查能力"), "list_for_each");
  expect(screen.getByText(/逐条核查会对清单中的每一条记录/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "添加子检查" }));
  await user.selectOptions(screen.getByLabelText("第 1 条子检查能力"), "vision_judge");
  // 占位符含大括号，fireEvent.change 避免 userEvent.type 的按键语法歧义
  fireEvent.change(screen.getByLabelText("第 1 条违规标题（模板）"), {
    target: { value: "条目{{item.no}}照片水印不合格" },
  });
  fireEvent.change(screen.getByLabelText("第 1 条违规内容（模板）"), {
    target: { value: "条目{{item.no}}的照片缺少标准水印" },
  });
  await user.type(
    screen.getByLabelText("第 1 条检查要求（一句话，AI 执行时按此判断）"),
    "检查照片水印是否包含时间、天气、地址、经纬度",
  );
  await user.type(screen.getByLabelText("规则代码"), "WM-FORM-001");
  await user.type(screen.getByLabelText("规则名称"), "条目照片水印核查");
  await user.click(screen.getByRole("button", { name: "保存规则" }));

  expect(createRule).toHaveBeenCalledTimes(1);
  const payload = vi.mocked(createRule).mock.calls[0][0];
  expect(payload.rule_type).toBe("hybrid");
  expect(payload.model_profile).toBe("vision");
  const ops = (payload.definition as Record<string, unknown>).ops as Array<Record<string, any>>;
  expect(ops[0].op).toBe("list_for_each");
  expect(ops[0].params.child_ops[0].op).toBe("vision_judge");
  expect(ops[0].params.child_ops[0].params.instruction).toContain("经纬度");
  // 占位符必须原样保留，交给引擎按当前条目渲染
  expect(ops[0].params.child_ops[0].fail.title).toBe("条目{{item.no}}照片水印不合格");
  expect(ops[0].params.child_ops[0].fail.content).toBe("条目{{item.no}}的照片缺少标准水印");
});

test("BL-099 A3: 仅文本理解子检查时档位为 text", async () => {
  vi.mocked(createRule).mockResolvedValue({ ...concepts[0], id: 11 } as never);
  const user = userEvent.setup();
  renderListForEachEditor();

  await user.selectOptions(screen.getByLabelText("检查对象"), "item_list");
  await user.selectOptions(screen.getByLabelText("检查能力"), "list_for_each");
  await user.click(screen.getByRole("button", { name: "添加子检查" }));
  await user.type(screen.getByLabelText("第 1 条违规标题（模板）"), "整改建议不具体");
  await user.type(screen.getByLabelText("第 1 条违规内容（模板）"), "整改建议未写明具体措施");
  await user.type(
    screen.getByLabelText("第 1 条检查要求（一句话，AI 执行时按此判断）"),
    "整改建议必须具体可执行",
  );
  await user.type(screen.getByLabelText("规则代码"), "WM-FORM-002");
  await user.type(screen.getByLabelText("规则名称"), "条目整改建议核查");
  await user.click(screen.getByRole("button", { name: "保存规则" }));

  const payload = vi.mocked(createRule).mock.calls[0][0];
  expect(payload.rule_type).toBe("hybrid");
  expect(payload.model_profile).toBe("text");
  const ops = (payload.definition as Record<string, unknown>).ops as Array<Record<string, any>>;
  expect(ops[0].params.child_ops[0].op).toBe("text_judge");
});

test("BL-099 A4: 编辑既有 hybrid 逐条规则回显子检查", async () => {
  vi.mocked(updateRule).mockResolvedValue({ ...concepts[0], id: 42 } as never);
  const rule: Rule = {
    ...concepts[0],
    id: 42,
    tenant_id: "1",
    rule_code: "WM-EDIT-001",
    name: "条目照片水印核查",
    description: "",
    rule_type: "hybrid",
    classify_id: null,
    severity_default: "一般",
    blocking_policy: "block",
    on_error_policy: "annotate",
    output_mode: "violations",
    model_profile: "vision",
    enabled: true,
    definition: {
      anchor: { concept: "item_list", required: true },
      ops: [
        {
          op: "list_for_each",
          params: {
            child_ops: [
              {
                op: "vision_judge",
                params: { instruction: "检查水印四要素与白字无底样式" },
                fail: {
                  title: "条目{{{{item.no}}}}照片水印不合格",
                  content: "照片缺少标准水印",
                  severity: "一般",
                },
              },
            ],
          },
          fail: { title: "清单逐条核查未通过", content: "条目未满足要求", severity: "一般" },
        },
      ],
    },
    note: null,
    created_at: "",
    updated_at: "",
  } as unknown as Rule;
  const user = userEvent.setup();
  renderListForEachEditor(rule);

  // 表单模式回显：子检查卡片出现且值正确
  expect(screen.getByLabelText("第 1 条子检查能力")).toHaveValue("vision_judge");
  expect(screen.getByLabelText("第 1 条违规标题（模板）")).toHaveValue("条目{{{{item.no}}}}照片水印不合格");
  expect(screen.getByLabelText("第 1 条检查要求（一句话，AI 执行时按此判断）")).toHaveValue(
    "检查水印四要素与白字无底样式",
  );
  await user.type(
    screen.getByLabelText("第 1 条检查要求（一句话，AI 执行时按此判断）"),
    "，缺任一要素即不合格",
  );
  await user.click(screen.getByRole("button", { name: "保存规则" }));

  expect(updateRule).toHaveBeenCalledTimes(1);
  const payload = vi.mocked(updateRule).mock.calls[0][1];
  expect((payload as Record<string, unknown>).rule_type).toBe("hybrid");
  const ops = (payload.definition as Record<string, unknown>).ops as Array<Record<string, any>>;
  expect(ops[0].params.child_ops[0].params.instruction).toBe(
    "检查水印四要素与白字无底样式，缺任一要素即不合格",
  );
});

test("BL-099 E1: 文本与视觉子检查混用时拒绝提交", async () => {
  const user = userEvent.setup();
  renderListForEachEditor();

  await user.selectOptions(screen.getByLabelText("检查对象"), "item_list");
  await user.selectOptions(screen.getByLabelText("检查能力"), "list_for_each");
  await user.click(screen.getByRole("button", { name: "添加子检查" }));
  await user.click(screen.getByRole("button", { name: "添加子检查" }));
  await user.selectOptions(screen.getByLabelText("第 2 条子检查能力"), "vision_judge");
  await user.type(screen.getByLabelText("规则代码"), "WM-MIX-001");
  await user.type(screen.getByLabelText("规则名称"), "混合档位");
  await user.click(screen.getByRole("button", { name: "保存规则" }));

  expect(await screen.findByText(/子检查能力需一致/)).toBeInTheDocument();
  expect(createRule).not.toHaveBeenCalled();
});

test("BL-099 E2: 缺少子检查或必填内容时拒绝提交", async () => {
  const user = userEvent.setup();
  renderListForEachEditor();

  await user.selectOptions(screen.getByLabelText("检查对象"), "item_list");
  await user.selectOptions(screen.getByLabelText("检查能力"), "list_for_each");
  await user.type(screen.getByLabelText("规则代码"), "WM-EMPTY-001");
  await user.type(screen.getByLabelText("规则名称"), "空子检查");
  await user.click(screen.getByRole("button", { name: "保存规则" }));
  expect(await screen.findByText(/至少添加一条子检查/)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "添加子检查" }));
  await user.click(screen.getByRole("button", { name: "保存规则" }));
  expect(await screen.findByText(/第 1 条子检查的检查要求描述不能为空/)).toBeInTheDocument();
  expect(screen.getByText(/第 1 条子检查的违规标题不能为空/)).toBeInTheDocument();
  expect(createRule).not.toHaveBeenCalled();
});

test("BL-099 E3: 非结构化清单概念不出现清单逐条核查能力", async () => {
  const user = userEvent.setup();
  render(
    <RuleEditor
      open
      concepts={concepts}
      operators={[...operators, listForEachOperator, visionJudgeOperator]}
      classifications={classifications}
      initialRule={null}
      onCancel={() => undefined}
      onSaved={() => undefined}
    />,
  );

  await user.selectOptions(screen.getByLabelText("检查对象"), "company_basic_info");
  const capability = screen.getByLabelText("检查能力") as HTMLSelectElement;
  expect([...capability.options].map((option) => option.value)).not.toContain("list_for_each");
});

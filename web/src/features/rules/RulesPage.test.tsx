// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import {
  createRule,
  deleteRule,
  listClassifications,
  listConcepts,
  listRules,
  listOperators,
} from "../../api/endpoints";
import { RulesPage } from "./RulesPage";
import { TenantProvider } from "../../tenant/TenantProvider";

vi.mock("../../api/endpoints", () => ({
  listConcepts: vi.fn(),
  listClassifications: vi.fn(),
  listRules: vi.fn(),
  listOperators: vi.fn(),
  createRule: vi.fn(),
  updateRule: vi.fn(),
  enableRule: vi.fn(),
  disableRule: vi.fn(),
  deleteRule: vi.fn(),
}));

const listConceptsMock = vi.mocked(listConcepts);
const listClassificationsMock = vi.mocked(listClassifications);
const listRulesMock = vi.mocked(listRules);
const listOperatorsMock = vi.mocked(listOperators);
const createRuleMock = vi.mocked(createRule);
const deleteRuleMock = vi.mocked(deleteRule);

function renderPage(ui: React.ReactElement) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <TenantProvider>{ui}</TenantProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  globalThis.localStorage.setItem("document-review.tenant-id", "tenant-A");
  listConceptsMock.mockResolvedValue({
    items: [
      {
        id: 1,
        tenant_id: "tenant-A",
        concept_code: "company_basic_info",
        concept_name: "企业基本信息表",
        aliases: [],
        data_kind: "table",
        source: "tenant_custom",
        created_at: "",
        updated_at: "",
      },
    ],
    total: 3,
    page: 1,
    page_size: 20,
  });
  listClassificationsMock.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
  listRulesMock.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
  listOperatorsMock.mockResolvedValue({
    items: [
      {
        id: 1,
        op_code: "extract_fields",
        name: "信息提取",
        description: "检查字段是否有值",
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
      {
        id: 2,
        op_code: "text_judge",
        name: "文本理解",
        description: "AI 文本判断",
        applicable_data_kind: ["field", "table"],
        params_schema: { type: "object" },
        result_semantics: "hit_is_violation",
        executor: "app.operators.text_judge:TextJudge",
        model_profile: "text",
        created_at: "",
        updated_at: "",
      },
      {
        id: 3,
        op_code: "vision_judge",
        name: "视觉理解",
        description: "AI 图片判断",
        applicable_data_kind: ["image_group"],
        params_schema: { type: "object" },
        result_semantics: "hit_is_violation",
        executor: "app.operators.vision_judge:VisionJudge",
        model_profile: "vision",
        created_at: "",
        updated_at: "",
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  });
  createRuleMock.mockResolvedValue({
    id: 9,
    tenant_id: "tenant-A",
    rule_code: "REG-001",
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
});

test("确认后删除租户自有规则", async () => {
  listRulesMock.mockResolvedValueOnce({
    items: [
      {
        id: 9,
        tenant_id: "tenant-A",
        rule_code: "DELETE-001",
        name: "可删除规则",
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
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  });
  deleteRuleMock.mockResolvedValue(undefined as never);
  renderPage(
    <MemoryRouter>
      <RulesPage />
    </MemoryRouter>,
  );

  await userEvent.setup().click(await screen.findByRole("button", { name: "删除" }));

  await screen.findByRole("dialog", { name: "删除规则" });
  await userEvent.setup().click(screen.getByRole("button", { name: "确认删除" }));
  expect(deleteRuleMock).toHaveBeenCalledWith(9);
});

test("规则列表展示检查对象与检查能力", async () => {
  listRulesMock.mockResolvedValueOnce({
    items: [
      {
        id: 10,
        tenant_id: "tenant-A",
        rule_code: "STRUCT-001",
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
        definition: {
          anchor: { concept: "company_basic_info", required: true },
          ops: [{ op: "extract_fields", params: { fields: [] } }],
        },
        note: null,
        created_at: "",
        updated_at: "",
      },
      {
        id: 11,
        tenant_id: "tenant-A",
        rule_code: "AI-001",
        name: "服务轨迹核验",
        description: "",
        rule_type: "llm",
        classify_id: null,
        severity_default: "一般",
        blocking_policy: "block",
        on_error_policy: "annotate",
        output_mode: "violations",
        model_profile: "vision",
        enabled: true,
        definition: {
          anchor: { concept: "missing_concept", required: true },
          instruction: "检查照片",
        },
        note: null,
        created_at: "",
        updated_at: "",
      },
    ],
    total: 2,
    page: 1,
    page_size: 20,
  });

  renderPage(
    <MemoryRouter>
      <RulesPage />
    </MemoryRouter>,
  );

  expect(await screen.findByText("企业基本信息表")).toBeInTheDocument();
  expect(screen.getByText("信息提取")).toBeInTheDocument();
  expect(screen.getByText("未知检查对象")).toBeInTheDocument();
  expect(screen.getByText("视觉理解")).toBeInTheDocument();
});

test("规则列表长名称和检查对象按 10 字符截断且表头居中", async () => {
  const longName = "这是一个特别特别特别长的规则名称用来验证截断";
  const longConcept = "这是一个特别特别特别长的检查对象概念名称";
  listConceptsMock.mockResolvedValue({
    items: [
      {
        id: 9,
        tenant_id: "tenant-A",
        concept_code: "long_concept",
        concept_name: longConcept,
        aliases: [],
        data_kind: "table",
        source: "tenant_custom",
        created_at: "",
        updated_at: "",
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  });
  listRulesMock.mockResolvedValue({
    items: [
      {
        id: 12,
        tenant_id: "tenant-A",
        rule_code: "LONG-001",
        name: longName,
        description: "",
        rule_type: "structured",
        classify_id: null,
        severity_default: "一般",
        blocking_policy: "block",
        on_error_policy: "annotate",
        output_mode: "violations",
        model_profile: null,
        enabled: true,
        definition: {
          anchor: { concept: "long_concept", required: true },
          ops: [{ op: "extract_fields", params: { fields: [] } }],
        },
        note: null,
        created_at: "",
        updated_at: "",
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  });

  renderPage(
    <MemoryRouter>
      <RulesPage />
    </MemoryRouter>,
  );

  expect(await screen.findByTitle(longName)).toHaveTextContent(`${longName.slice(0, 10)}...`);
  expect(screen.getByTitle(longConcept)).toHaveTextContent(
    `${longConcept.slice(0, 10)}...`,
  );
  const header = screen.getByRole("columnheader", { name: "操作" });
  expect(header).toHaveClass("table-header");
});

test("取消确认时不删除规则", async () => {
  listRulesMock.mockResolvedValueOnce({
    items: [
      {
        id: 9,
        tenant_id: "tenant-A",
        rule_code: "CANCEL-001",
        name: "取消删除规则",
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
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  });
  renderPage(
    <MemoryRouter>
      <RulesPage />
    </MemoryRouter>,
  );

  await userEvent.setup().click(await screen.findByRole("button", { name: "删除" }));

  expect(screen.getByRole("dialog", { name: "删除规则" })).toBeInTheDocument();
  await userEvent.setup().click(screen.getByRole("button", { name: "取消" }));
  expect(deleteRuleMock).not.toHaveBeenCalled();
});

test("删除被引用规则时展示冲突且列表保留", async () => {
  listRulesMock.mockResolvedValueOnce({
    items: [
      {
        id: 9,
        tenant_id: "tenant-A",
        rule_code: "HZ-1011-001",
        name: "被引用规则",
        description: "",
        rule_type: "structured",
        classify_id: null,
        severity_default: "严重",
        blocking_policy: "block",
        on_error_policy: "annotate",
        output_mode: "violations",
        model_profile: null,
        enabled: true,
        definition: {},
        note: null,
        created_at: "",
        updated_at: "",
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  });
  deleteRuleMock.mockRejectedValueOnce(new Error("规则仍被规则集引用，请先从规则集移除后再删除"));
  renderPage(
    <MemoryRouter>
      <RulesPage />
    </MemoryRouter>,
  );

  await userEvent.setup().click(await screen.findByRole("button", { name: "删除" }));

  await userEvent.setup().click(await screen.findByRole("button", { name: "确认删除" }));
  expect(await screen.findByText(/规则仍被规则集引用/)).toBeInTheDocument();
  expect(screen.getByText("HZ-1011-001")).toBeInTheDocument();
});

test("新增规则通过业务表单自动生成 DSL 并提交", async () => {
  const user = userEvent.setup();
  renderPage(
    <MemoryRouter>
      <RulesPage />
    </MemoryRouter>,
  );

  await screen.findByText("暂无规则");
  await user.click(screen.getByRole("button", { name: "新增规则" }));
  await user.selectOptions(screen.getByLabelText("检查对象"), "company_basic_info");
  await user.selectOptions(screen.getByLabelText("检查能力"), "extract_fields");
  await screen.findByText("信息提取");
  await user.type(screen.getByLabelText("规则代码"), "REG-001");
  await user.type(screen.getByLabelText("规则名称"), "企业地址必填");
  await user.type(screen.getByLabelText("信息提取：提取字段清单"), "企业地址");
  await user.type(screen.getByLabelText("违规标题"), "企业地址缺失");
  await user.type(screen.getByLabelText("违规内容"), "企业地址不能为空");
  await user.click(screen.getByRole("button", { name: "保存规则" }));

  expect(createRuleMock).toHaveBeenCalledTimes(1);
  const payload = createRuleMock.mock.calls[0][0];
  expect(payload.rule_code).toBe("REG-001");
  expect(payload.definition).toMatchObject({
    anchor: { concept: "company_basic_info", required: true },
    params: { fields: ["企业地址"] },
    ops: [
      {
        op: "extract_fields",
        params: { fields: "${fields}" },
        fail: { title: "企业地址缺失", content: "企业地址不能为空" },
      },
    ],
  });
  expect(document.body.textContent).not.toContain("extract_fields");
});

test("新增规则入口位于右上角并打开弹窗", async () => {
  renderPage(
    <MemoryRouter>
      <RulesPage />
    </MemoryRouter>,
  );

  await screen.findByText("暂无规则");
  const header = document.querySelector(".page-header");
  expect(header).not.toBeNull();
  const createButton = within(header as HTMLElement).getByRole("button", { name: "新增规则" });
  await userEvent.setup().click(createButton);

  expect(screen.getByRole("dialog", { name: "新增规则" })).toHaveClass("modal");
  expect(screen.queryByText("从业务目标开始建立规则")).toBeNull();
});

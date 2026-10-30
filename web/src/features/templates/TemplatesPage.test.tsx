// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import {
  createTemplate,
  createTemplateFromProfile,
  deleteTemplate,
  listConcepts,
  listRuleSets,
  listRules,
  listTemplates,
  trialTemplate,
  type DocumentTemplate,
  type TemplateTrialResult,
} from "../../api/endpoints";
import { TemplatesPage } from "./TemplatesPage";

vi.mock("../../api/endpoints", () => ({
  listTemplates: vi.fn(),
  listRuleSets: vi.fn(),
  listConcepts: vi.fn(),
  listRules: vi.fn(),
  createTemplate: vi.fn(),
  updateTemplate: vi.fn(),
  deleteTemplate: vi.fn(),
  trialTemplate: vi.fn(),
  createTemplateFromProfile: vi.fn(),
}));

const trialResult: TemplateTrialResult = {
  profile_id: 7,
  file_sha256: "a".repeat(64),
  discovery_method: "llm_discovery",
  template_id: null,
  doc_summary: "LLM 识别报告",
  bindings: [
    {
      concept_code: "document_sections",
      status: "bound",
      targets: [{ kind: "section", locator: {}, confidence: 0.9 }],
    },
  ],
  suggested_detect_conditions: [{ type: "md_contains", keyword: "测试报告" }],
  rule_set_id: 3,
  rule_set_selection_reason: "已按显式 rule_set_id 选择",
  rule_preview: [
    {
      rule_id: 9,
      rule_code: "TPL-001",
      rule_name: "总结章节必填",
      rule_type: "structured",
      status: "success",
      violations: [
        {
          rule_id: "TPL-001",
          rule_name: "总结章节必填",
          classify_id: 0,
          title: "总结缺失",
          severity: "一般",
          content: "缺少总结章节",
          page_idx: 0,
          mark_text: [],
          meta: { blocking: true, skip_result: false, observation: false },
        },
      ],
      extracted: null,
      skip_reason: null,
      error: null,
      duration_ms: 5,
    },
  ],
};

const detailTemplate: DocumentTemplate = {
  id: 6,
  tenant_id: "tenant-A",
  name: "通用报告模板",
  status: "active",
  description: null,
  detect_conditions: [
    { type: "section_title_regex", pattern: "一、检查基本情况" },
    { type: "md_contains", keyword: "项目资料" },
  ],
  concept_bindings: [
    {
      concept_code: "1",
      status: "bound",
      targets: [
        {
          kind: "table",
          locator: { anchor_keywords: ["条目", "汇总"], field_aliases: ["条目描述"] },
          page_idx_hint: 2,
          confidence: 0.92,
          confirmed_by: "template",
        },
        {
          kind: "section",
          locator: {},
          page_idx: 3,
          confidence: 0.86,
          confirmed_by: "llm",
        },
        {
          kind: "item_list",
          locator: {},
          page_idx: 5,
          confidence: 0.88,
          confirmed_by: "template",
        },
      ],
    },
  ],
  source_run_id: null,
  source_profile_id: 18,
  created_at: "2026-10-10T09:30:00",
  updated_at: "2026-10-10T10:00:00",
};

const listTemplatesMock = vi.mocked(listTemplates);
const listRuleSetsMock = vi.mocked(listRuleSets);
const listConceptsMock = vi.mocked(listConcepts);
const listRulesMock = vi.mocked(listRules);
const trialTemplateMock = vi.mocked(trialTemplate);
const createTemplateMock = vi.mocked(createTemplate);
const createTemplateFromProfileMock = vi.mocked(createTemplateFromProfile);
const deleteTemplateMock = vi.mocked(deleteTemplate);

beforeEach(() => {
  listTemplatesMock.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
  listRuleSetsMock.mockResolvedValue({
    items: [
      {
        id: 3,
        tenant_id: "tenant-A",
        name: "文档审查规则包",
        template_id: null,
        is_standard_pack: false,
        items: [],
        description: null,
        created_at: "",
        updated_at: "",
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  });
  trialTemplateMock.mockReset();
  createTemplateMock.mockReset();
  createTemplateFromProfileMock.mockReset();
  deleteTemplateMock.mockReset();
  listConceptsMock.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
  listRulesMock.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
});

function renderPage() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <TemplatesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function openCreateModal(user: ReturnType<typeof userEvent.setup>) {
  const header = document.querySelector(".page-header");
  expect(header).not.toBeNull();
  const createButton = within(header as HTMLElement).getByRole("button", { name: "新建模板" });
  await user.click(createButton);
  return within(screen.getByRole("dialog", { name: "新建模板" }));
}

function sampleFile() {
  return new File([new Uint8Array([1, 2, 3])], "sample.pdf", { type: "application/pdf" });
}

test("模板列表首屏仅保留右上角新建入口", async () => {
  renderPage();

  expect(await screen.findByText("暂无模板")).toBeInTheDocument();
  const header = document.querySelector(".page-header");
  expect(header).not.toBeNull();
  expect(within(header as HTMLElement).getByRole("button", { name: "新建模板" })).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(screen.queryByLabelText("模板文件")).toBeNull();
  expect(screen.queryByText(/JSON/)).toBeNull();
});

test("确认后删除模板并刷新列表", async () => {
  listTemplatesMock.mockResolvedValue({
    items: [detailTemplate],
    total: 1,
    page: 1,
    page_size: 20,
  });
  deleteTemplateMock.mockResolvedValue(undefined as never);
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByRole("button", { name: "删除" }));
  const dialog = screen.getByRole("dialog", { name: "删除模板" });
  expect(within(dialog).getByText('确定删除模板「通用报告模板」吗？')).toBeInTheDocument();
  await user.click(within(dialog).getByRole("button", { name: "确认删除" }));

  await waitFor(() => expect(deleteTemplateMock).toHaveBeenCalledWith(6));
  expect(await screen.findByText("模板「通用报告模板」已删除。")).toBeInTheDocument();
  expect(screen.queryByRole("dialog", { name: "删除模板" })).toBeNull();
});

test("取消模板删除不调用接口", async () => {
  listTemplatesMock.mockResolvedValue({
    items: [detailTemplate],
    total: 1,
    page: 1,
    page_size: 20,
  });
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByRole("button", { name: "删除" }));
  await user.click(await screen.findByRole("button", { name: "取消" }));

  expect(deleteTemplateMock).not.toHaveBeenCalled();
});

test("模板删除失败时显示明确错误", async () => {
  listTemplatesMock.mockResolvedValue({
    items: [detailTemplate],
    total: 1,
    page: 1,
    page_size: 20,
  });
  deleteTemplateMock.mockRejectedValue(new Error("模板仍被规则集引用"));
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByRole("button", { name: "删除" }));
  await user.click(await screen.findByRole("button", { name: "确认删除" }));

  expect(await screen.findByText("模板仍被规则集引用")).toBeInTheDocument();
});

test("模板详情弹窗展示画像绑定与识别条件", async () => {
  listTemplatesMock.mockResolvedValueOnce({
    items: [detailTemplate],
    total: 1,
    page: 1,
    page_size: 20,
  });
  listConceptsMock.mockResolvedValueOnce({
    items: [
      {
        id: 21,
        tenant_id: "tenant-A",
        concept_code: "1",
        concept_name: "检查概况",
        description: null,
        aliases: [],
        data_kind: "section",
        source: "tenant_custom",
        seeded_from: null,
        created_at: "",
        updated_at: "",
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  });
  listRulesMock.mockResolvedValueOnce({
    items: [
      {
        id: 31,
        tenant_id: "tenant-A",
        rule_code: "HZ-001",
        name: "检查概况完整性",
        description: null,
        rule_type: "structured",
        classify_id: null,
        severity_default: "严重",
        blocking_policy: "block",
        on_error_policy: "annotate",
        output_mode: "violations",
        model_profile: null,
        enabled: true,
        definition: { anchor: { concept: "1" }, ops: [] },
        note: null,
        created_at: "",
        updated_at: "",
      },
      {
        id: 32,
        tenant_id: "tenant-A",
        rule_code: "HZ-002",
        name: "停用的检查概况规则",
        description: null,
        rule_type: "structured",
        classify_id: null,
        severity_default: "一般",
        blocking_policy: "advise",
        on_error_policy: "annotate",
        output_mode: "violations",
        model_profile: null,
        enabled: false,
        definition: { anchor: { concept: "1" }, ops: [] },
        note: null,
        created_at: "",
        updated_at: "",
      },
    ],
    total: 2,
    page: 1,
    page_size: 20,
  });
  const user = userEvent.setup();
  renderPage();

  await screen.findByText("通用报告模板");
  await user.click(screen.getByRole("button", { name: "详情" }));

  const detail = within(screen.getByRole("dialog", { name: "模板详情：通用报告模板" }));
  expect(detail.getByText("启用")).toBeInTheDocument();
  expect(detail.getByText("18")).toBeInTheDocument();
  expect(detail.getByText("章节标题匹配：一、检查基本情况")).toBeInTheDocument();
  expect(detail.getByText("全文包含关键词：项目资料")).toBeInTheDocument();
  expect(detail.getByText("检查概况（编码：1）")).toBeInTheDocument();
  expect(detail.getByText("已绑定 · 3 个目标")).toBeInTheDocument();
  expect(
    detail.getByText(
      "这里展示的是模板的概念位置绑定，不是规则集绑定。规则集里的规则通过概念编码引用这些位置。",
    ),
  ).toBeInTheDocument();
  expect(detail.getByText("引用该位置的规则：检查概况完整性")).toBeInTheDocument();
  expect(detail.getByText("表格 · 第 3 页提示 · 置信度 92%")).toBeInTheDocument();
  expect(detail.getByText("定位条件：表格关键词=条目、汇总；字段别名=条目描述")).toBeInTheDocument();
  expect(detail.getByText("章节 · 第 4 页章节内容 · 置信度 86%")).toBeInTheDocument();
  // BL-098 A5：画像目标类型展示通用叫法，不出现「条目清单」
  expect(detail.getByText("结构化清单 · 第 6 页内容 · 置信度 88%")).toBeInTheDocument();
  expect(detail.queryByText(/条目清单 ·/)).not.toBeInTheDocument();
  expect(detail.getAllByText("定位方式：页级定位").length).toBeGreaterThan(0);
  expect(
    detail.getAllByText("精确条件：未识别到章节标题 / 表格关键词").length,
  ).toBeGreaterThan(0);
  expect(detail.queryByText(/JSON/)).toBeNull();
});

test("模板详情为空时显示识别条件与绑定占位", async () => {
  listTemplatesMock.mockResolvedValueOnce({
    items: [{ ...detailTemplate, detect_conditions: [], concept_bindings: [] }],
    total: 1,
    page: 1,
    page_size: 20,
  });
  const user = userEvent.setup();
  renderPage();

  await screen.findByText("通用报告模板");
  await user.click(screen.getByRole("button", { name: "详情" }));

  const detail = within(screen.getByRole("dialog", { name: "模板详情：通用报告模板" }));
  expect(detail.getByText("暂无识别条件")).toBeInTheDocument();
  expect(detail.getByText("暂无概念绑定")).toBeInTheDocument();
  expect(detail.queryByText(/JSON/)).toBeNull();
});

test("概念编码不存在时显示未知概念并保留目标", async () => {
  listTemplatesMock.mockResolvedValueOnce({
    items: [
      {
        ...detailTemplate,
        concept_bindings: [
          {
            concept_code: "missing-concept",
            status: "bound",
            targets: [
              {
                kind: "section",
                locator: {},
                page_idx: 1,
                confidence: 0.8,
                confirmed_by: "llm",
              },
            ],
          },
        ],
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  });
  const user = userEvent.setup();
  renderPage();

  await screen.findByText("通用报告模板");
  await user.click(screen.getByRole("button", { name: "详情" }));

  const detail = within(screen.getByRole("dialog", { name: "模板详情：通用报告模板" }));
  expect(detail.getByText("未知概念（编码：missing-concept）")).toBeInTheDocument();
  expect(detail.getByText("当前启用的规则未引用该位置")).toBeInTheDocument();
});

test("关闭模板详情弹窗不触发写请求", async () => {
  listTemplatesMock.mockResolvedValueOnce({
    items: [detailTemplate],
    total: 1,
    page: 1,
    page_size: 20,
  });
  const user = userEvent.setup();
  renderPage();

  await screen.findByText("通用报告模板");
  await user.click(screen.getByRole("button", { name: "详情" }));
  await user.click(screen.getByRole("button", { name: "关闭" }));

  expect(screen.queryByRole("dialog")).toBeNull();
  expect(screen.getByText("通用报告模板")).toBeInTheDocument();
  expect(createTemplateFromProfileMock).not.toHaveBeenCalled();
  expect(trialTemplateMock).not.toHaveBeenCalled();
});

test("新建模板弹窗要求模板文件与显式规则集后试跑", async () => {
  trialTemplateMock.mockResolvedValue(trialResult);
  const user = userEvent.setup();
  renderPage();

  await screen.findByText("暂无模板");
  const modal = await openCreateModal(user);
  expect(modal.getByText("模板文件仅用于画像生成，不正式审查")).toBeInTheDocument();
  expect(modal.getByRole("button", { name: "模板创建" })).toBeDisabled();
  expect(modal.queryByText(/自动选择/)).toBeNull();
  await user.upload(modal.getByLabelText("模板文件"), sampleFile());
  expect(modal.getByRole("button", { name: "模板创建" })).toBeDisabled();
  await user.selectOptions(modal.getByLabelText("规则集"), "3");
  expect(modal.getByRole("button", { name: "模板创建" })).toBeEnabled();
  await user.click(modal.getByRole("button", { name: "模板创建" }));

  expect(await screen.findByText("LLM 识别报告")).toBeInTheDocument();
  expect(screen.getByText("document_sections")).toBeInTheDocument();
  expect(screen.getByText("总结章节必填")).toBeInTheDocument();
  expect(screen.queryByText(/JSON/)).toBeNull();
  const [file, ruleSetId] = trialTemplateMock.mock.calls[0];
  expect(file.name).toBe("sample.pdf");
  expect(ruleSetId).toBe(3);
});

test("模板创建后使用系统建议条件和自动绑定生成模板", async () => {
  trialTemplateMock.mockResolvedValue(trialResult);
  createTemplateFromProfileMock.mockResolvedValue({
    id: 11,
    tenant_id: "tenant-A",
    name: "通用报告模板",
    status: "active",
    description: null,
    detect_conditions: trialResult.suggested_detect_conditions,
    concept_bindings: trialResult.bindings,
    source_run_id: null,
    source_profile_id: 7,
    created_at: "",
    updated_at: "",
  });
  const user = userEvent.setup();
  renderPage();

  await screen.findByText("暂无模板");
  const modal = await openCreateModal(user);
  await user.selectOptions(modal.getByLabelText("规则集"), "3");
  await user.upload(modal.getByLabelText("模板文件"), sampleFile());
  await user.click(modal.getByRole("button", { name: "模板创建" }));
  await screen.findByText("LLM 识别报告");
  await user.type(screen.getByLabelText("模板名称"), "通用报告模板");
  await user.click(screen.getByRole("button", { name: "生成并启用模板" }));

  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(await screen.findByText("模板生成成功，已启用。")).toBeInTheDocument();
  expect(createTemplateFromProfileMock).toHaveBeenCalledWith(7, {
    name: "通用报告模板",
    description: null,
    detect_conditions: [{ type: "md_contains", keyword: "测试报告" }],
  });
  expect(createTemplateMock).not.toHaveBeenCalled();
});

test("样例缺少有效绑定时禁止生成并提示更换样例", async () => {
  trialTemplateMock.mockResolvedValueOnce({
    ...trialResult,
    bindings: [],
    rule_preview: [],
  });
  const user = userEvent.setup();
  renderPage();

  await screen.findByText("暂无模板");
  const modal = await openCreateModal(user);
  await user.selectOptions(modal.getByLabelText("规则集"), "3");
  await user.upload(modal.getByLabelText("模板文件"), sampleFile());
  await user.click(modal.getByRole("button", { name: "模板创建" }));

  expect(await screen.findByText("LLM 识别报告")).toBeInTheDocument();
  expect(
    screen.getByText("当前样例结构不足以生成模板，请更换一份更完整的标准样例。"),
  ).toBeInTheDocument();
  expect(screen.queryByLabelText("模板名称")).toBeNull();
  expect(screen.queryByRole("button", { name: "生成并启用模板" })).toBeNull();
  expect(createTemplateFromProfileMock).not.toHaveBeenCalled();
});

test("系统未生成识别条件时禁止生成模板", async () => {
  trialTemplateMock.mockResolvedValueOnce({
    ...trialResult,
    suggested_detect_conditions: [],
  });
  const user = userEvent.setup();
  renderPage();

  await screen.findByText("暂无模板");
  const modal = await openCreateModal(user);
  await user.selectOptions(modal.getByLabelText("规则集"), "3");
  await user.upload(modal.getByLabelText("模板文件"), sampleFile());
  await user.click(modal.getByRole("button", { name: "模板创建" }));

  expect(await screen.findByText("LLM 识别报告")).toBeInTheDocument();
  expect(
    screen.getByText("当前样例结构不足以生成模板，请更换一份更完整的标准样例。"),
  ).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "生成并启用模板" })).toBeNull();
  expect(createTemplateFromProfileMock).not.toHaveBeenCalled();
});

test("关闭新建模板弹窗不生成且重新打开重置流程", async () => {
  const user = userEvent.setup();
  renderPage();

  await screen.findByText("暂无模板");
  const modal = await openCreateModal(user);
  await user.selectOptions(modal.getByLabelText("规则集"), "3");
  await user.upload(modal.getByLabelText("模板文件"), sampleFile());
  await user.click(screen.getByRole("button", { name: "关闭" }));

  expect(screen.queryByRole("dialog")).toBeNull();
  const nextModal = await openCreateModal(user);
  expect(nextModal.getByLabelText("模板文件")).toHaveValue("");
  expect(nextModal.getByRole("button", { name: "模板创建" })).toBeDisabled();
  expect(createTemplateFromProfileMock).not.toHaveBeenCalled();
});

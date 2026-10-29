// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import globalCss from "../../styles/global.css?raw";
import {
  deleteRuleSet,
  createRuleSet,
  getRuleSet,
  getRuleSetTemplateCompatibility,
  listRuleSets,
  listRules,
  replaceRuleSetItems,
} from "../../api/endpoints";
import { RuleSetsPage } from "./RuleSetsPage";
import { TenantProvider } from "../../tenant/TenantProvider";

vi.mock("../../api/endpoints", () => ({
  listRules: vi.fn(),
  listRuleSets: vi.fn(),
  getRuleSet: vi.fn(),
  getRuleSetTemplateCompatibility: vi.fn(),
  createRuleSet: vi.fn(),
  updateRuleSet: vi.fn(),
  replaceRuleSetItems: vi.fn(),
  deleteRuleSet: vi.fn(),
}));

const listRulesMock = vi.mocked(listRules);
const listRuleSetsMock = vi.mocked(listRuleSets);
const replaceItemsMock = vi.mocked(replaceRuleSetItems);
const getRuleSetMock = vi.mocked(getRuleSet);
const compatibilityMock = vi.mocked(getRuleSetTemplateCompatibility);
const createRuleSetMock = vi.mocked(createRuleSet);

function renderPage(ui: React.ReactElement) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <TenantProvider>{ui}</TenantProvider>
    </QueryClientProvider>,
  );
}
const deleteRuleSetMock = vi.mocked(deleteRuleSet);

test("编辑弹窗启用开关与表单控件垂直居中", () => {
  const itemRule = globalCss.match(/\.rule-set-item\s*{([^}]*)}/);
  const switchRule = globalCss.match(/\.rule-set-item \.switch\s*{([^}]*)}/);
  const trackRule = globalCss.match(/\.switch-track\s*{([^}]*)}/);

  expect(itemRule?.[1]).toMatch(/(^|;)\s*align-items:\s*end(?:\s*;|$)/);
  expect(switchRule?.[1]).toMatch(/(^|;)\s*height:\s*38px(?:\s*;|$)/);
  expect(switchRule?.[1]).toMatch(/(^|;)\s*align-items:\s*center(?:\s*;|$)/);
  expect(trackRule?.[1]).toMatch(/(^|;)\s*width:\s*42px(?:\s*;|$)/);
  expect(trackRule?.[1]).toMatch(/(^|;)\s*height:\s*24px(?:\s*;|$)/);
  expect(globalCss).not.toContain(".switch-input");
});

beforeEach(() => {
  globalThis.localStorage.setItem("document-review.tenant-id", "tenant-A");
  listRulesMock.mockResolvedValue({
    items: [
      {
        id: 3,
        tenant_id: "tenant-A",
        rule_code: "REG-003",
        name: "章节缺失",
        rule_type: "structured",
        severity_default: "严重",
        blocking_policy: "block",
        on_error_policy: "annotate",
        output_mode: "violations",
        enabled: true,
        definition: {},
        created_at: "",
        updated_at: "",
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  });
  listRuleSetsMock.mockResolvedValue({
    items: [
      {
        id: 8,
        tenant_id: "tenant-A",
        name: "标准包",
        is_standard_pack: false,
        items: [
          {
            id: 12,
            rule_set_id: 8,
            rule_id: 3,
            execution_order: 1,
            enabled: true,
            params_override: { min_photos: 2 },
            created_at: "",
            updated_at: "",
          },
        ],
        created_at: "",
        updated_at: "",
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  });
  replaceItemsMock.mockResolvedValue({} as never);
  createRuleSetMock.mockResolvedValue({} as never);
  getRuleSetMock.mockResolvedValue({
    id: 8,
    tenant_id: "tenant-A",
    name: "标准包",
    is_standard_pack: false,
    items: [
      {
        id: 12,
        rule_set_id: 8,
        rule_id: 3,
        execution_order: 1,
        enabled: true,
        params_override: { min_photos: 2 },
        created_at: "",
        updated_at: "",
      },
    ],
    created_at: "",
    updated_at: "",
  });
  compatibilityMock.mockResolvedValue([
    {
      rule_set_id: 8,
      template_id: 6,
      template_name: "通用报告模板",
      status: "partial",
      exact_count: 1,
      weak_count: 0,
      missing_count: 0,
      rules: [
        {
          rule_id: 3,
          rule_code: "REG-003",
          rule_name: "章节缺失",
          concept_code: "1",
          required: true,
          action: "reused",
          binding_quality: "exact",
          message: "模板已提供章节、表格或字段级稳定定位。",
        },
      ],
    },
  ]);
});

test("列表页不直接展示规则明细且编辑入口打开弹窗", async () => {
  const user = userEvent.setup();
  const summary = {
    id: 8,
    tenant_id: "tenant-A",
    name: "标准包",
    is_standard_pack: false,
    items: [],
    created_at: "",
    updated_at: "",
  };
  listRuleSetsMock.mockResolvedValueOnce({
    items: [summary],
    total: 1,
    page: 1,
    page_size: 20,
  });
  getRuleSetMock.mockResolvedValueOnce({
    ...summary,
    items: [
      {
        id: 12,
        rule_set_id: 8,
        rule_id: 3,
        execution_order: 1,
        enabled: true,
        params_override: { min_photos: 2 },
        created_at: "",
        updated_at: "",
      },
    ],
  });

  renderPage(
    <MemoryRouter>
      <RuleSetsPage />
    </MemoryRouter>,
  );

  expect(await screen.findByRole("cell", { name: "标准包" })).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(screen.queryByLabelText("规则")).toBeNull();
  expect(screen.queryByRole("button", { name: "添加规则" })).toBeNull();
  expect(screen.queryByText(/参数覆盖/)).toBeNull();
  expect(getRuleSetMock).toHaveBeenCalledWith(8);

  await user.click(screen.getByRole("button", { name: "编辑" }));

  expect(screen.getByRole("dialog", { name: "编辑规则集：标准包" })).toHaveClass("modal");
  expect(within(screen.getByRole("dialog")).getByLabelText("规则")).toBeInTheDocument();
});

test("编辑弹窗支持调整顺序启停并保留历史参数覆盖", async () => {
  const user = userEvent.setup();
  renderPage(
    <MemoryRouter>
      <RuleSetsPage />
    </MemoryRouter>,
  );

  await screen.findByRole("cell", { name: "标准包" });
  await user.click(screen.getByRole("button", { name: "编辑" }));
  const editor = within(screen.getByRole("dialog", { name: "编辑规则集：标准包" }));
  fireEvent.change(editor.getByLabelText("执行顺序"), { target: { value: "2" } });
  expect(editor.queryByRole("checkbox")).toBeNull();
  const enabledSwitch = editor.getByRole("switch", { name: "启用" });
  expect(enabledSwitch).toHaveAttribute("aria-checked", "true");
  await user.click(enabledSwitch);
  expect(enabledSwitch).toHaveAttribute("aria-checked", "false");
  expect(replaceItemsMock).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "保存规则项" }));

  expect(replaceItemsMock).toHaveBeenCalledWith(8, {
    items: [
      {
        rule_id: 3,
        execution_order: 2,
        enabled: false,
        params_override: { min_photos: 2 },
      },
    ],
  });
  await waitFor(() => expect(compatibilityMock).toHaveBeenCalledTimes(2));
  expect(screen.getByRole("dialog", { name: "编辑规则集：标准包" })).toBeInTheDocument();
  expect(screen.getByText("模板兼容性评估")).toBeInTheDocument();
});

test("编辑弹窗展示规则集与模板兼容性报告", async () => {
  const user = userEvent.setup();
  renderPage(
    <MemoryRouter>
      <RuleSetsPage />
    </MemoryRouter>,
  );

  await screen.findByRole("cell", { name: "标准包" });
  await user.click(screen.getByRole("button", { name: "编辑" }));

  const editor = within(screen.getByRole("dialog", { name: "编辑规则集：标准包" }));
  expect(await screen.findByText("模板兼容性评估")).toBeInTheDocument();
  expect(editor.getByText("通用报告模板")).toBeInTheDocument();
  expect(editor.getByText(/部分兼容/)).toBeInTheDocument();
  expect(editor.getByText("章节缺失")).toBeInTheDocument();
  expect(editor.getByText(/可复用/)).toBeInTheDocument();
  expect(editor.getByText(/稳定定位/)).toBeInTheDocument();
});

test("兼容性报告读取失败时不影响规则项编辑", async () => {
  compatibilityMock.mockRejectedValueOnce(new Error("评估服务不可用"));
  const user = userEvent.setup();
  renderPage(
    <MemoryRouter>
      <RuleSetsPage />
    </MemoryRouter>,
  );

  await screen.findByRole("cell", { name: "标准包" });
  await user.click(screen.getByRole("button", { name: "编辑" }));

  expect(await screen.findByText("模板兼容性读取失败")).toBeInTheDocument();
  const editor = within(screen.getByRole("dialog", { name: "编辑规则集：标准包" }));
  expect(editor.getByLabelText("规则")).toBeInTheDocument();
  expect(editor.getByRole("button", { name: "保存规则项" })).toBeEnabled();
});

test("关闭编辑弹窗不保存且重新打开恢复服务端数据", async () => {
  const user = userEvent.setup();
  renderPage(
    <MemoryRouter>
      <RuleSetsPage />
    </MemoryRouter>,
  );

  await screen.findByRole("cell", { name: "标准包" });
  await user.click(screen.getByRole("button", { name: "编辑" }));
  const editor = within(screen.getByRole("dialog", { name: "编辑规则集：标准包" }));
  fireEvent.change(editor.getByLabelText("执行顺序"), { target: { value: "9" } });
  await user.click(editor.getByRole("button", { name: "关闭" }));

  expect(screen.queryByRole("dialog")).toBeNull();
  await user.click(screen.getByRole("button", { name: "编辑" }));
  expect(within(screen.getByRole("dialog")).getByLabelText("执行顺序")).toHaveValue("1");
  expect(replaceItemsMock).not.toHaveBeenCalled();
  expect(screen.queryByText(/参数覆盖/)).toBeNull();
});

test("编辑弹窗支持移除后重新添加规则", async () => {
  const user = userEvent.setup();
  renderPage(
    <MemoryRouter>
      <RuleSetsPage />
    </MemoryRouter>,
  );

  await screen.findByRole("cell", { name: "标准包" });
  await user.click(screen.getByRole("button", { name: "编辑" }));
  const editor = within(screen.getByRole("dialog", { name: "编辑规则集：标准包" }));
  await user.click(editor.getByRole("button", { name: "移除规则" }));
  await user.click(editor.getByRole("button", { name: "添加规则" }));
  await user.click(editor.getByRole("button", { name: "保存规则项" }));

  expect(replaceItemsMock).toHaveBeenCalledWith(8, {
    items: [
      {
        rule_id: 3,
        execution_order: 1,
        enabled: true,
        params_override: {},
      },
    ],
  });
});

test("确认后删除租户自有规则集", async () => {
  deleteRuleSetMock.mockResolvedValue(undefined as never);

  renderPage(
    <MemoryRouter>
      <RuleSetsPage />
    </MemoryRouter>,
  );

  await screen.findByRole("cell", { name: "标准包" });
  await userEvent.setup().click(screen.getByRole("button", { name: "删除规则集" }));

  await screen.findByRole("dialog", { name: "删除规则集" });
  await userEvent.setup().click(screen.getByRole("button", { name: "确认删除" }));
  expect(deleteRuleSetMock).toHaveBeenCalledWith(8);
});


test("创建规则集入口位于右上角并使用弹窗", async () => {
  const user = userEvent.setup();
  renderPage(
    <MemoryRouter>
      <RuleSetsPage />
    </MemoryRouter>,
  );

  await screen.findByRole("cell", { name: "标准包" });
  const header = document.querySelector(".page-header");
  expect(header).not.toBeNull();
  const createButton = within(header as HTMLElement).getByRole("button", { name: "创建规则集" });
  await user.click(createButton);

  expect(screen.getByRole("dialog", { name: "创建规则集" })).toHaveClass("modal");
  await user.type(screen.getByLabelText("规则集名称"), "新规则集");
  await user.click(screen.getByRole("button", { name: "保存规则集" }));

  await waitFor(() => expect(createRuleSetMock).toHaveBeenCalledWith({
    name: "新规则集",
    is_standard_pack: false,
    description: null,
    items: [],
  }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
});

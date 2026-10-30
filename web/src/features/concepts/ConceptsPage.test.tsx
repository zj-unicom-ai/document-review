// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import { createConcept, listConcepts } from "../../api/endpoints";
import { deleteConcept } from "../../api/endpoints";
import { ConceptsPage } from "./ConceptsPage";
import { TenantProvider } from "../../tenant/TenantProvider";

vi.mock("../../api/endpoints", () => ({
  listConcepts: vi.fn(),
  createConcept: vi.fn(),
  updateConcept: vi.fn(),
  deleteConcept: vi.fn(),
}));

const listConceptsMock = vi.mocked(listConcepts);
const createConceptMock = vi.mocked(createConcept);
const deleteConceptMock = vi.mocked(deleteConcept);

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
    items: [],
    total: 0,
    page: 1,
    page_size: 20,
  });
  createConceptMock.mockResolvedValue({} as never);
});

test("确认后删除租户自定义概念", async () => {
  listConceptsMock.mockResolvedValueOnce({
    items: [
      {
        id: 9,
        tenant_id: "tenant-A",
        concept_code: "custom_concept",
        concept_name: "自定义概念",
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
  deleteConceptMock.mockResolvedValue(undefined as never);
  renderPage(
    <MemoryRouter>
      <ConceptsPage />
    </MemoryRouter>,
  );

  await userEvent.setup().click(await screen.findByRole("button", { name: "删除" }));

  await screen.findByRole("dialog", { name: "删除概念" });
  await userEvent.setup().click(screen.getByRole("button", { name: "确认删除" }));
  expect(deleteConceptMock).toHaveBeenCalledWith(9);
});

test("平台概念显示禁用删除按钮", async () => {
  listConceptsMock.mockResolvedValueOnce({
    items: [
      {
        id: 10,
        tenant_id: "",
        concept_code: "platform_concept",
        concept_name: "平台概念",
        aliases: [],
        data_kind: "table",
        source: "platform",
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
      <ConceptsPage />
    </MemoryRouter>,
  );

  const button = await screen.findByRole("button", { name: "平台数据只读" });
  expect(button).toBeDisabled();
});

test("BL-098 A3: 数据类型展示中文标签且提交值仍为原编码", async () => {
  listConceptsMock.mockResolvedValueOnce({
    items: [
      {
        id: 12,
        tenant_id: "tenant-A",
        concept_code: "issue_list",
        concept_name: "问题清单",
        aliases: [],
        data_kind: "item_list",
        source: "tenant_custom",
        created_at: "",
        updated_at: "",
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  });
  const user = userEvent.setup();
  renderPage(
    <MemoryRouter>
      <ConceptsPage />
    </MemoryRouter>,
  );

  // 列表数据类型展示中文标签，不出现英文原值
  expect(await screen.findByText("问题清单")).toBeInTheDocument();
  expect(screen.getByText("结构化清单")).toBeInTheDocument();
  expect(screen.queryByText("item_list")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "新增概念" }));
  const select = screen.getByLabelText("数据类型");
  // 展示为中文标签，提交值保持后端枚举编码
  expect(screen.getByRole("option", { name: "结构化清单" })).toBeInTheDocument();
  expect(select).toHaveValue("field");
  expect(screen.queryByRole("option", { name: "item_list" })).not.toBeInTheDocument();
});

test("新增概念时把别名输入拆成数组并提交", async () => {
  const user = userEvent.setup();
  renderPage(
    <MemoryRouter>
      <ConceptsPage />
    </MemoryRouter>,
  );

  await screen.findByText("暂无概念");
  await user.click(screen.getByRole("button", { name: "新增概念" }));
  expect(screen.getByRole("dialog", { name: "新增概念" })).toHaveClass("modal");
  await user.type(screen.getByLabelText("概念编码"), "company_basic_info");
  await user.type(screen.getByLabelText("概念名称"), "企业基本信息");
  await user.type(screen.getByLabelText("同义词（逗号分隔）"), "企业信息, 基本情况");
  await user.click(screen.getByRole("button", { name: "保存概念" }));

  await waitFor(() =>
    expect(createConceptMock).toHaveBeenCalledWith({
      concept_code: "company_basic_info",
      concept_name: "企业基本信息",
      description: "",
      aliases: ["企业信息", "基本情况"],
      data_kind: "field",
      source: "tenant_custom",
    }),
  );
});

test("概念删除失败时在列表区展示错误", async () => {
  listConceptsMock.mockResolvedValueOnce({
    items: [
      {
        id: 11,
        tenant_id: "tenant-A",
        concept_code: "delete_failed",
        concept_name: "删除失败概念",
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
  deleteConceptMock.mockRejectedValue(new Error("概念仍被规则引用"));
  const user = userEvent.setup();

  renderPage(
    <MemoryRouter>
      <ConceptsPage />
    </MemoryRouter>,
  );

  await user.click(await screen.findByRole("button", { name: "删除" }));
  await user.click(await screen.findByRole("button", { name: "确认删除" }));

  expect(await screen.findByText("概念仍被规则引用")).toBeInTheDocument();
  expect(screen.getByText("删除失败概念")).toBeInTheDocument();
});

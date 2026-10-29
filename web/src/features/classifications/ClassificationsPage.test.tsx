// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import {
  createClassification,
  deleteClassification,
  listClassifications,
  previewClassificationDelete,
  updateClassification,
} from "../../api/endpoints";
import { ClassificationsPage } from "./ClassificationsPage";
import { TenantProvider } from "../../tenant/TenantProvider";

vi.mock("../../api/endpoints", () => ({
  listClassifications: vi.fn(),
  createClassification: vi.fn(),
  updateClassification: vi.fn(),
  previewClassificationDelete: vi.fn(),
  deleteClassification: vi.fn(),
}));

const listMock = vi.mocked(listClassifications);
const createMock = vi.mocked(createClassification);
const deleteMock = vi.mocked(deleteClassification);
const previewMock = vi.mocked(previewClassificationDelete);
const updateMock = vi.mocked(updateClassification);

function buildClassification(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: 77,
    tenant_id: "tenant-A",
    classify_id: 1010,
    parent_id: null as number | null,
    level: 1,
    name: "根维度",
    sort_order: 0,
    created_at: "",
    updated_at: "",
    ...overrides,
  };
}

function renderPage(ui: React.ReactElement) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <TenantProvider>{ui}</TenantProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  globalThis.localStorage.setItem("document-review.tenant-id", "tenant-A");
  listMock.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
  createMock.mockResolvedValue({} as never);
  updateMock.mockResolvedValue({} as never);
  previewMock.mockResolvedValue({
    classification_count: 1,
    child_count: 0,
    rule_count: 0,
  });
});

test("新增根级分类刷新后默认可见", async () => {
  const root = buildClassification({ id: 91, classify_id: 1010, name: "新根维度" });
  listMock.mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 20 });
  listMock.mockResolvedValueOnce({ items: [root], total: 1, page: 1, page_size: 20 });
  createMock.mockResolvedValue(root as never);
  const user = userEvent.setup();
  renderPage(
    <MemoryRouter>
      <ClassificationsPage />
    </MemoryRouter>,
  );

  await screen.findByText("暂无分类");
  await user.click(screen.getByRole("button", { name: "新增分类" }));
  await user.type(screen.getByLabelText("分类编号"), "1010");
  await user.type(screen.getByLabelText("分类名称"), "新根维度");
  await user.click(screen.getByRole("button", { name: "保存分类" }));

  expect(await screen.findByText("新根维度")).toBeInTheDocument();
  const nameHeader = screen.getByRole("columnheader", { name: "名称" });
  expect(nameHeader).toHaveClass("column-align-left");
  expect(nameHeader).toHaveClass("classification-name-header");
  expect(nameHeader).toHaveStyle({ width: "32%" });
  expect(screen.queryByRole("columnheader", { name: "描述" })).toBeNull();
});

test("确认后删除租户自定义分类", async () => {
  listMock.mockResolvedValueOnce({
    items: [
      {
        id: 9,
        tenant_id: "tenant-A",
        classify_id: 9001,
        parent_id: null,
        level: 2,
        name: "自定义分类",
        sort_order: 0,
        created_at: "",
        updated_at: "",
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  });
  deleteMock.mockResolvedValue(undefined as never);
  renderPage(
    <MemoryRouter>
      <ClassificationsPage />
    </MemoryRouter>,
  );

  // 并行测试时 React Query 响应可能晚于默认 1 秒等待；先等列表真实渲染。
  await screen.findByText("自定义分类", {}, { timeout: 5000 });
  await userEvent.setup().click(await screen.findByRole("button", { name: "删除" }));

  await screen.findByRole("dialog", { name: "删除业务分类" });
  await userEvent.setup().click(screen.getByRole("button", { name: "确认删除" }));
  expect(deleteMock).toHaveBeenCalledWith(9);
});

test("分类名称层级保持左对齐容器", async () => {
  listMock.mockResolvedValueOnce({
    items: [buildClassification({ id: 91, classify_id: 9100, name: "根维度" })],
    total: 1,
    page: 1,
    page_size: 20,
  });

  renderPage(
    <MemoryRouter>
      <ClassificationsPage />
    </MemoryRouter>,
  );

  const name = await screen.findByText("根维度");
  expect(name.closest(".classification-name-cell")).toHaveClass("classification-name-cell");
});

test("编辑分类提交基础信息和父级", async () => {
  listMock.mockResolvedValueOnce({
    items: [
      buildClassification({ id: 77, classify_id: 1010, name: "根维度" }),
      buildClassification({ id: 88, classify_id: 1011, parent_id: 77, level: 2, name: "其他根" }),
    ],
    total: 2,
    page: 1,
    page_size: 20,
  });
  const user = userEvent.setup();
  renderPage(
    <MemoryRouter>
      <ClassificationsPage />
    </MemoryRouter>,
  );

  await screen.findAllByText("根维度");
  await user.click(screen.getAllByRole("button", { name: "编辑" })[0]);
  expect(screen.getByRole("dialog", { name: "编辑分类" })).toHaveClass("modal");
  await user.clear(screen.getByLabelText("分类名称"));
  await user.type(screen.getByLabelText("分类名称"), "新根维度");
  await user.clear(screen.getByLabelText("排序"));
  await user.type(screen.getByLabelText("排序"), "3");
  await user.click(screen.getByRole("button", { name: "保存分类" }));

  await waitFor(() =>
    expect(updateMock).toHaveBeenCalledWith(77, {
      classify_id: 1010,
      parent_id: null,
      name: "新根维度",
      description: "",
      sort_order: 3,
    }),
  );
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
});

test("新增根级分类使用弹窗并提交一级层级", async () => {
  const user = userEvent.setup();
  renderPage(
    <MemoryRouter>
      <ClassificationsPage />
    </MemoryRouter>,
  );

  await screen.findByText("暂无分类");
  const header = document.querySelector(".page-header");
  expect(header).not.toBeNull();
  expect(within(header as HTMLElement).getByRole("button", { name: "新增分类" })).toBeDefined();
  await user.click(screen.getByRole("button", { name: "新增分类" }));

  expect(screen.getByRole("dialog", { name: "新增分类" })).toHaveClass("modal");
  await user.type(screen.getByLabelText("分类编号"), "1011");
  await user.type(screen.getByLabelText("分类名称"), "服务人员");
  await user.click(screen.getByRole("button", { name: "保存分类" }));

  await waitFor(() =>
    expect(createMock).toHaveBeenCalledWith({
      classify_id: 1011,
      parent_id: null,
      level: 1,
      name: "服务人员",
      description: "",
      sort_order: 0,
    }),
  );
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
});

test("新增子级分类提交所选根分类", async () => {
  listMock.mockResolvedValueOnce({
    items: [
      buildClassification({ id: 77, classify_id: 1010, name: "根维度", level: 1 }),
      buildClassification({ id: 88, classify_id: 1011, parent_id: 77, level: 2, name: "旧子项" }),
    ],
    total: 2,
    page: 1,
    page_size: 20,
  });
  const user = userEvent.setup();
  renderPage(
    <MemoryRouter>
      <ClassificationsPage />
    </MemoryRouter>,
  );

  await screen.findAllByText("根维度");
  await user.click(screen.getByRole("button", { name: "新增分类" }));
  await user.selectOptions(screen.getByLabelText("分类级别"), "child");
  await user.selectOptions(screen.getByLabelText("父级分类"), "77");
  await user.type(screen.getByLabelText("分类编号"), "1012");
  await user.type(screen.getByLabelText("分类名称"), "服务人员");
  await user.click(screen.getByRole("button", { name: "保存分类" }));

  await waitFor(() =>
    expect(createMock).toHaveBeenCalledWith({
      classify_id: 1012,
      parent_id: 77,
      level: 2,
      name: "服务人员",
      description: "",
      sort_order: 0,
    }),
  );
});

test("子级分类未选择父分类时禁止保存", async () => {
  listMock.mockResolvedValueOnce({
    items: [buildClassification()],
    total: 1,
    page: 1,
    page_size: 20,
  });
  const user = userEvent.setup();
  renderPage(
    <MemoryRouter>
      <ClassificationsPage />
    </MemoryRouter>,
  );

  await screen.findAllByText("根维度");
  await user.click(screen.getByRole("button", { name: "新增分类" }));
  await user.selectOptions(screen.getByLabelText("分类级别"), "child");
  await user.type(screen.getByLabelText("分类编号"), "1012");
  await user.type(screen.getByLabelText("分类名称"), "服务人员");

  expect(screen.getByRole("button", { name: "保存分类" })).toBeDisabled();
  expect(createMock).not.toHaveBeenCalled();
});

test("分类列表默认只显示根分类，展开后显示对应子分类", async () => {
  listMock.mockResolvedValueOnce({
    items: [
      buildClassification({ id: 77, classify_id: 1010, name: "根维度一" }),
      buildClassification({ id: 88, classify_id: 1011, parent_id: 77, level: 2, name: "一组子项" }),
      buildClassification({ id: 99, classify_id: 1020, name: "根维度二" }),
      buildClassification({ id: 110, classify_id: 1021, parent_id: 99, level: 2, name: "二组子项" }),
    ],
    total: 4,
    page: 1,
    page_size: 20,
  });
  const user = userEvent.setup();
  renderPage(
    <MemoryRouter>
      <ClassificationsPage />
    </MemoryRouter>,
  );

  await screen.findAllByText("根维度一");
  expect(screen.queryByText("一组子项")).toBeNull();
  expect(screen.queryByText("二组子项")).toBeNull();

  await user.click(screen.getByRole("button", { name: "展开 根维度一 的子分类" }));
  expect(await screen.findByText("一组子项")).toBeInTheDocument();
  expect(screen.queryByText("二组子项")).toBeNull();

  await user.click(screen.getByRole("button", { name: "收起 根维度一 的子分类" }));
  await waitFor(() => expect(screen.queryByText("一组子项")).toBeNull());
});

test("新增子分类成功后自动展开父分类", async () => {
  const root = buildClassification({ id: 77, classify_id: 1010, name: "根维度" });
  const child = buildClassification({
    id: 88,
    classify_id: 1012,
    parent_id: 77,
    level: 2,
    name: "新子项",
  });
  listMock.mockResolvedValueOnce({
    items: [root],
    total: 1,
    page: 1,
    page_size: 20,
  });
  listMock.mockResolvedValueOnce({
    items: [root, child],
    total: 2,
    page: 1,
    page_size: 20,
  });
  createMock.mockResolvedValue(child as never);
  const user = userEvent.setup();
  renderPage(
    <MemoryRouter>
      <ClassificationsPage />
    </MemoryRouter>,
  );

  await screen.findByText("根维度");
  await user.click(screen.getByRole("button", { name: "新增分类" }));
  await user.selectOptions(screen.getByLabelText("分类级别"), "child");
  await user.selectOptions(screen.getByLabelText("父级分类"), "77");
  await user.type(screen.getByLabelText("分类编号"), "1012");
  await user.type(screen.getByLabelText("分类名称"), "新子项");
  await user.click(screen.getByRole("button", { name: "保存分类" }));

  expect(await screen.findByText("新子项")).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("有规则引用时删除前展示影响并要求二次确认", async () => {
  listMock.mockResolvedValueOnce({
    items: [
      buildClassification({ id: 77, classify_id: 1010, name: "根维度" }),
      buildClassification({ id: 88, classify_id: 1011, parent_id: 77, level: 2, name: "子项" }),
    ],
    total: 2,
    page: 1,
    page_size: 20,
  });
  previewMock.mockResolvedValue({
    classification_count: 2,
    child_count: 1,
    rule_count: 1,
  });
  deleteMock.mockResolvedValue(undefined as never);
  const user = userEvent.setup();

  renderPage(
    <MemoryRouter>
      <ClassificationsPage />
    </MemoryRouter>,
  );

  await screen.findAllByText("根维度");
  await user.click(await screen.findByRole("button", { name: "删除" }));

  expect(previewMock).toHaveBeenCalledWith(77);
  const dialog = await screen.findByRole("dialog", { name: "删除业务分类" });
  expect(within(dialog).getByText(/1 条规则将解除分类关联/)).toBeInTheDocument();
  expect(within(dialog).getByText(/将删除 2 个分类（含 1 个子分类）/)).toBeInTheDocument();
  await user.click(within(dialog).getByRole("button", { name: "确认删除" }));
  expect(await within(dialog).findByRole("button", { name: "再次确认删除" })).toBeInTheDocument();
  await user.click(within(dialog).getByRole("button", { name: "再次确认删除" }));
  expect(deleteMock).toHaveBeenCalledWith(77);
});

test("分类删除失败时在列表区展示错误", async () => {
  listMock.mockResolvedValueOnce({
    items: [buildClassification({ id: 99, classify_id: 1010, name: "删除失败分类" })],
    total: 1,
    page: 1,
    page_size: 20,
  });
  deleteMock.mockRejectedValue(new Error("分类仍被子分类引用"));
  const user = userEvent.setup();

  renderPage(
    <MemoryRouter>
      <ClassificationsPage />
    </MemoryRouter>,
  );

  await user.click(await screen.findByRole("button", { name: "删除" }));
  await user.click(await screen.findByRole("button", { name: "确认删除" }));

  expect(await screen.findByText("分类仍被子分类引用")).toBeInTheDocument();
  expect(screen.getByText("删除失败分类")).toBeInTheDocument();
});

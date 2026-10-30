// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import { createTenant, listTenants } from "../../api/endpoints";
import { TenantsPage } from "./TenantsPage";

vi.mock("../../api/endpoints", () => ({
  listTenants: vi.fn(),
  createTenant: vi.fn(),
  updateTenant: vi.fn(),
}));

const listTenantsMock = vi.mocked(listTenants);
const createTenantMock = vi.mocked(createTenant);

function renderPage(ui: React.ReactElement) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      {ui}
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  globalThis.localStorage.setItem("document-review.tenant-id", "tenant-A");
  listTenantsMock.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
  createTenantMock.mockResolvedValue({} as never);
});

test("A1-A3 新增租户入口使用居中弹窗并提交表单", async () => {
  const user = userEvent.setup();
  renderPage(
    <MemoryRouter>
      <TenantsPage />
    </MemoryRouter>,
  );

  await screen.findByText("暂无租户");
  const header = document.querySelector(".page-header");
  expect(header).not.toBeNull();
  const createButton = within(header as HTMLElement).getByRole("button", { name: "新增租户" });
  expect(screen.queryByRole("dialog", { name: "新增租户" })).toBeNull();

  await user.click(createButton);
  const dialog = screen.getByRole("dialog", { name: "新增租户" });
  expect(dialog).toHaveClass("modal");

  await user.type(screen.getByLabelText("租户编码"), "new-tenant");
  await user.type(screen.getByLabelText("租户名称"), "新租户");
  await user.type(screen.getByLabelText("联系人"), "张三");
  await user.type(screen.getByLabelText("备注"), "试点租户");
  await user.click(screen.getByRole("button", { name: "保存租户" }));

  await waitFor(() =>
    expect(createTenantMock).toHaveBeenCalledWith({
      code: "new-tenant",
      name: "新租户",
      contact: "张三",
      note: "试点租户",
    }),
  );
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
});

test("E1 保存失败时弹窗保留并展示错误", async () => {
  createTenantMock.mockRejectedValue(new Error("租户编码已存在"));
  const user = userEvent.setup();
  renderPage(
    <MemoryRouter>
      <TenantsPage />
    </MemoryRouter>,
  );

  await screen.findByText("暂无租户");
  await user.click(screen.getByRole("button", { name: "新增租户" }));
  await user.type(screen.getByLabelText("租户编码"), "exists");
  await user.type(screen.getByLabelText("租户名称"), "已存在租户");
  await user.click(screen.getByRole("button", { name: "保存租户" }));

  expect(await screen.findByText("租户编码已存在")).toBeInTheDocument();
  expect(screen.getByRole("dialog", { name: "新增租户" })).toBeInTheDocument();
});

test("保留超管租户不提供停用操作", async () => {
  listTenantsMock.mockResolvedValue({
    items: [
      {
        id: 1,
        code: "superadmin",
        name: "平台超级管理员",
        status: "active",
        contact: null,
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
      <TenantsPage />
    </MemoryRouter>,
  );

  const button = await screen.findByRole("button", { name: "保留租户" });
  expect(button).toBeDisabled();
  expect(screen.queryByRole("button", { name: "停用" })).toBeNull();
});

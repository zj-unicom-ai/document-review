// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import {
  createRole,
  deleteRole,
  listMenuPermissions,
  listRoles,
  updateRole,
} from "../../api/endpoints";
import { RolesPage } from "./RolesPage";

vi.mock("../../api/endpoints", () => ({
  listRoles: vi.fn(),
  createRole: vi.fn(),
  updateRole: vi.fn(),
  deleteRole: vi.fn(),
  listMenuPermissions: vi.fn(),
}));

const listRolesMock = vi.mocked(listRoles);
const listMenuPermissionsMock = vi.mocked(listMenuPermissions);
const createRoleMock = vi.mocked(createRole);
const deleteRoleMock = vi.mocked(deleteRole);
const updateRoleMock = vi.mocked(updateRole);

function renderPage() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <RolesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const builtinRole = {
  id: 1,
  tenant_code: "tenant-A",
  code: "tenant_admin",
  name: "租户管理员",
  description: null,
  is_system: true,
  status: "active",
  menu_codes: ["reviews"],
  user_count: 1,
  created_at: "",
  updated_at: "",
};

beforeEach(() => {
  listRolesMock.mockResolvedValue({
    items: [builtinRole],
    total: 1,
    page: 1,
    page_size: 20,
  });
  listMenuPermissionsMock.mockResolvedValue([
    { code: "reviews", name: "文档审查", group: "业务", assignable: true },
    { code: "rules", name: "规则配置", group: "规则管理", assignable: true },
    { code: "system_users", name: "用户管理", group: "系统管理", assignable: false },
  ]);
  createRoleMock.mockResolvedValue({} as never);
  deleteRoleMock.mockResolvedValue(undefined);
  updateRoleMock.mockResolvedValue({} as never);
});

test("E7 内置角色只读且删除入口禁用", async () => {
  renderPage();

  expect(screen.queryByRole("columnheader", { name: "菜单权限" })).not.toBeInTheDocument();
  const row = await screen.findByRole("row", { name: /租户管理员/ });
  expect(within(row).getByRole("button", { name: "删除" })).toBeDisabled();
  expect(within(row).getByText("内置")).toBeInTheDocument();
});

test("A4 创建自定义角色时绑定可分配菜单", async () => {
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("租户管理员");

  await user.click(screen.getByRole("button", { name: "新增角色" }));
  const dialog = screen.getByRole("dialog", { name: "新增角色" });
  expect(document.querySelector(".modal.role-form-modal")).not.toBeNull();
  expect(document.querySelector(".role-form-grid")).not.toBeNull();
  await user.type(screen.getByLabelText(/^角色编码/), "rule_viewer");
  await user.type(screen.getByLabelText("角色名称"), "规则查看员");
  await user.click(within(dialog).getByRole("checkbox", { name: /文档审查/ }));
  await user.click(within(dialog).getByRole("checkbox", { name: /规则配置/ }));
  await user.click(screen.getByRole("button", { name: "保存角色" }));

  await waitFor(() =>
    expect(createRoleMock).toHaveBeenCalledWith({
      code: "rule_viewer",
      name: "规则查看员",
      description: "",
      menu_codes: ["reviews", "rules"],
    }),
  );
});

test("A4 菜单权限按两级菜单分组并支持整组选择", async () => {
  listMenuPermissionsMock.mockResolvedValue([
    { code: "reviews", name: "文档审查", group: "业务", assignable: true, parent: null },
    { code: "operators", name: "检查能力", group: "业务", assignable: true, parent: null },
    { code: "rules", name: "规则配置", group: "规则管理", assignable: true, parent: "规则管理" },
    { code: "concepts", name: "概念管理", group: "规则管理", assignable: true, parent: "规则管理" },
    { code: "rule_sets", name: "规则集", group: "规则管理", assignable: true, parent: "规则管理" },
    { code: "system_templates", name: "模板管理", group: "系统管理", assignable: true, parent: "系统管理" },
    { code: "system_resources", name: "资源管理", group: "系统管理", assignable: true, parent: "系统管理" },
    { code: "system_users", name: "用户管理", group: "系统管理", assignable: false, parent: "系统管理" },
  ]);
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("租户管理员");

  await user.click(screen.getByRole("button", { name: "新增角色" }));
  const dialog = screen.getByRole("dialog", { name: "新增角色" });
  expect(within(dialog).getByText("菜单权限")).toBeInTheDocument();
  expect(within(dialog).getByRole("group", { name: "菜单权限" })).toBeInTheDocument();
  expect(within(dialog).getByRole("checkbox", { name: "文档审查" })).toBeInTheDocument();
  expect(within(dialog).getByRole("checkbox", { name: "检查能力" })).toBeInTheDocument();
  expect(within(dialog).getByRole("checkbox", { name: "全选：规则管理" })).toBeInTheDocument();
  expect(within(dialog).getByRole("button", { name: "展开：规则管理" })).toBeInTheDocument();
  expect(within(dialog).queryByRole("checkbox", { name: "规则配置" })).not.toBeInTheDocument();
  expect(within(dialog).queryByRole("checkbox", { name: /用户管理/ })).not.toBeInTheDocument();

  await user.click(within(dialog).getByRole("button", { name: "展开：规则管理" }));
  expect(within(dialog).getByRole("checkbox", { name: "规则配置" })).toBeInTheDocument();

  await user.type(screen.getByLabelText(/^角色编码/), "rule_manager");
  await user.type(screen.getByLabelText("角色名称"), "规则管理员");
  await user.click(within(dialog).getByRole("checkbox", { name: "全选：规则管理" }));
  await user.click(screen.getByRole("button", { name: "保存角色" }));

  await waitFor(() =>
    expect(createRoleMock).toHaveBeenCalledWith({
      code: "rule_manager",
      name: "规则管理员",
      description: "",
      menu_codes: ["rules", "concepts", "rule_sets"],
    }),
  );
});

test("E9 删除已分配角色失败时保留错误提示", async () => {
  listRolesMock.mockResolvedValue({
    items: [
      {
        ...builtinRole,
        id: 2,
        code: "rule_viewer",
        name: "规则查看员",
        is_system: false,
        user_count: 2,
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  });
  deleteRoleMock.mockRejectedValue(new Error("角色已分配用户，请先解绑用户"));
  const user = userEvent.setup();
  renderPage();

  const row = await screen.findByRole("row", { name: /规则查看员/ });
  await user.click(within(row).getByRole("button", { name: "删除" }));

  expect(await screen.findByText("角色已分配用户，请先解绑用户")).toBeInTheDocument();
});

test("A4 自定义角色支持编辑基础信息", async () => {
  listRolesMock.mockResolvedValue({
    items: [
      {
        ...builtinRole,
        id: 2,
        code: "rule_viewer",
        name: "规则查看员",
        is_system: false,
        description: "旧描述",
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  });
  const user = userEvent.setup();
  renderPage();
  const row = await screen.findByRole("row", { name: /规则查看员/ });

  await user.click(within(row).getByRole("button", { name: "编辑" }));
  await user.clear(screen.getByLabelText("角色名称"));
  await user.type(screen.getByLabelText("角色名称"), "规则配置员");
  await user.clear(screen.getByLabelText("描述"));
  await user.type(screen.getByLabelText("描述"), "负责规则配置");
  await user.click(screen.getByRole("button", { name: "保存角色" }));

  await waitFor(() =>
    expect(updateRoleMock).toHaveBeenCalledWith(2, {
      name: "规则配置员",
      description: "负责规则配置",
      menu_codes: ["reviews"],
    }),
  );
});

test("A3 内置普通角色允许调整菜单权限", async () => {
  listRolesMock.mockResolvedValue({
    items: [
      {
        ...builtinRole,
        id: 3,
        code: "member",
        name: "普通用户",
        menu_codes: ["reviews"],
        user_count: 5,
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  });
  const user = userEvent.setup();
  renderPage();
  const row = await screen.findByRole("row", { name: /普通用户/ });

  await user.click(within(row).getByRole("button", { name: "编辑" }));
  const dialog = screen.getByRole("dialog", { name: "编辑角色" });
  expect((within(dialog).getByLabelText(/^角色编码/) as HTMLInputElement).disabled).toBe(true);
  expect((within(dialog).getByLabelText("角色名称") as HTMLInputElement).disabled).toBe(true);
  await user.click(within(dialog).getByRole("checkbox", { name: /规则配置/ }));
  await user.click(screen.getByRole("button", { name: "保存角色" }));

  await waitFor(() =>
    expect(updateRoleMock).toHaveBeenCalledWith(3, { menu_codes: ["reviews", "rules"] }),
  );
});

// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import {
  createUser,
  deleteUser,
  listRoles,
  listUsers,
  updateUser,
} from "../../api/endpoints";
import { UsersPage } from "./UsersPage";

vi.mock("../../api/endpoints", () => ({
  listUsers: vi.fn(),
  createUser: vi.fn(),
  updateUser: vi.fn(),
  deleteUser: vi.fn(),
  listRoles: vi.fn(),
}));

const listUsersMock = vi.mocked(listUsers);
const listRolesMock = vi.mocked(listRoles);
const createUserMock = vi.mocked(createUser);
const updateUserMock = vi.mocked(updateUser);
const deleteUserMock = vi.mocked(deleteUser);

function renderPage() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  listRolesMock.mockResolvedValue({
    items: [
      {
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
      },
      {
        id: 2,
        tenant_code: "tenant-A",
        code: "member",
        name: "普通用户",
        description: null,
        is_system: true,
        status: "active",
        menu_codes: ["reviews"],
        user_count: 0,
        created_at: "",
        updated_at: "",
      },
    ],
    total: 2,
    page: 1,
    page_size: 20,
  });
  listUsersMock.mockResolvedValue({
    items: [
      {
        id: 10,
        tenant_code: "tenant-A",
        username: "a-member",
        display_name: "租户用户",
        status: "active",
        roles: [{ id: 2, code: "member", name: "普通用户" }],
        created_at: "",
        updated_at: "",
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  });
  createUserMock.mockResolvedValue({} as never);
  updateUserMock.mockResolvedValue({} as never);
  deleteUserMock.mockResolvedValue(undefined);
});

test("A3 用户列表展示角色且不暴露密码字段", async () => {
  renderPage();

  expect(await screen.findByText("a-member")).toBeInTheDocument();
  expect(screen.getByText("普通用户")).toBeInTheDocument();
  expect(screen.queryByText(/password_hash/i)).not.toBeInTheDocument();
});

test("A3 创建用户可绑定角色", async () => {
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("a-member");

  await user.click(screen.getByRole("button", { name: "新增用户" }));
  const dialog = screen.getByRole("dialog", { name: "新增用户" });
  await user.type(screen.getByLabelText("用户名"), "new-user");
  await user.type(screen.getByLabelText("显示名称"), "新用户");
  const password = screen.getByPlaceholderText("至少 8 位，保存后请提醒用户修改。");
  expect(password).toHaveAttribute("type", "password");
  expect(screen.queryByText("至少 8 位，保存后请提醒用户修改。")).not.toBeInTheDocument();
  await user.type(password, "new-user-secret");

  const roleTrigger = within(dialog).getByRole("button", { name: "选择角色" });
  await user.click(roleTrigger);
  await user.click(within(dialog).getByRole("option", { name: /租户管理员/ }));
  await user.click(within(dialog).getByRole("option", { name: /普通用户/ }));
  expect(within(dialog).getByRole("button", { name: "移除角色：租户管理员" })).toBeInTheDocument();
  expect(within(dialog).getByRole("button", { name: "移除角色：普通用户" })).toBeInTheDocument();

  await user.click(within(dialog).getByRole("button", { name: "移除角色：普通用户" }));
  expect(
    within(dialog).queryByRole("button", { name: "移除角色：普通用户" }),
  ).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "保存用户" }));

  await waitFor(() =>
    expect(createUserMock).toHaveBeenCalledWith({
      username: "new-user",
      display_name: "新用户",
      password: "new-user-secret",
      role_ids: [1],
    }),
  );
});

test("A1 用户表单使用受控两列布局并整行展示密码和角色", async () => {
  renderPage();
  await screen.findByText("a-member");
  await userEvent.setup().click(screen.getByRole("button", { name: "新增用户" }));

  expect(document.querySelector(".modal.user-form-modal")).not.toBeNull();
  expect(document.querySelector(".user-form-grid")).not.toBeNull();
  expect(document.querySelectorAll(".user-form-grid > .field-span")).toHaveLength(2);
});

test("E1 点击已选角色会取消选择", async () => {
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("a-member");
  await user.click(screen.getByRole("button", { name: "新增用户" }));
  const dialog = screen.getByRole("dialog", { name: "新增用户" });
  const roleTrigger = within(dialog).getByRole("button", { name: "选择角色" });

  await user.click(roleTrigger);
  await user.click(within(dialog).getByRole("option", { name: /租户管理员/ }));
  expect(within(dialog).getByRole("button", { name: "移除角色：租户管理员" })).toBeInTheDocument();

  await user.click(within(dialog).getByRole("option", { name: /租户管理员/ }));
  expect(
    within(dialog).queryByRole("button", { name: "移除角色：租户管理员" }),
  ).not.toBeInTheDocument();
  expect(within(dialog).getByText("请选择角色")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "保存用户" })).toBeDisabled();
});

test("E6 停用用户失败时展示后端保护信息", async () => {
  updateUserMock.mockRejectedValue(new Error("不能删除、停用或降级最后一个管理员"));
  const user = userEvent.setup();
  renderPage();
  const row = await screen.findByRole("row", { name: /a-member/ });
  await user.click(within(row).getByRole("button", { name: "停用" }));

  expect(
    await screen.findByText("不能删除、停用或降级最后一个管理员"),
  ).toBeInTheDocument();
});

test("A3 编辑用户可更新资料、角色并重置密码", async () => {
  const user = userEvent.setup();
  renderPage();
  const row = await screen.findByRole("row", { name: /a-member/ });

  await user.click(within(row).getByRole("button", { name: "编辑" }));
  const dialog = screen.getByRole("dialog", { name: "编辑用户" });
  const usernameInput = within(dialog).getByLabelText("用户名");
  expect((usernameInput as HTMLInputElement).disabled).toBe(true);
  await user.clear(screen.getByLabelText("显示名称"));
  await user.type(screen.getByLabelText("显示名称"), "更名用户");
  const password = screen.getByPlaceholderText("留空则不修改密码。");
  expect(screen.queryByText("留空则不修改密码。")).not.toBeInTheDocument();
  await user.type(password, "reset-user-secret");
  const roleTrigger = within(dialog).getByRole("button", { name: "选择角色" });
  await user.click(roleTrigger);
  await user.click(within(dialog).getByRole("option", { name: /租户管理员/ }));
  expect(within(dialog).getByRole("button", { name: "移除角色：租户管理员" })).toBeInTheDocument();
  expect(within(dialog).getByRole("button", { name: "移除角色：普通用户" })).toBeInTheDocument();

  await user.click(within(dialog).getByRole("button", { name: "移除角色：普通用户" }));
  await user.click(screen.getByRole("button", { name: "保存用户" }));

  await waitFor(() =>
    expect(updateUserMock).toHaveBeenCalledWith(10, {
      display_name: "更名用户",
      password: "reset-user-secret",
      role_ids: [1],
    }),
  );
});

test("A3 删除用户需要二次确认", async () => {
  const user = userEvent.setup();
  renderPage();
  const row = await screen.findByRole("row", { name: /a-member/ });

  await user.click(within(row).getByRole("button", { name: "删除" }));
  const dialog = screen.getByRole("dialog", { name: "删除用户" });
  expect(within(dialog).getByText(/确定删除用户 a-member/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "确认删除" }));

  await waitFor(() => expect(deleteUserMock).toHaveBeenCalledWith(10));
});

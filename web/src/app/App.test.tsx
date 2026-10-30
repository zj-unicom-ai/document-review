// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { App } from "./App";

const authUser = {
  id: 1,
  tenant_code: "superadmin",
  username: "admin",
  display_name: "平台超级管理员",
  roles: ["super_admin"],
  menu_codes: [
    "reviews",
    "operators",
    "rules",
    "concepts",
    "classifications",
    "rule_sets",
    "system_templates",
    "system_resources",
    "system_users",
    "system_roles",
    "system_tenants",
  ],
  status: "active",
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function mockFetch(handler: (path: string, init?: RequestInit) => Response) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input), "http://localhost").pathname;
    return handler(path, init);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

beforeEach(() => {
  globalThis.localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("未登录访问系统租户管理时跳转登录页", async () => {
  mockFetch((path) => (path === "/api/v1/auth/me" ? jsonResponse({ message: "未登录" }, 401) : jsonResponse({})));

  render(
    <MemoryRouter initialEntries={["/system/tenants"]}>
      <App />
    </MemoryRouter>,
  );

  expect(await screen.findByRole("heading", { name: "文档智能审查平台" })).toBeInTheDocument();
});

test("超管登录后可进入控制台、切换租户并登出", async () => {
  let authenticated = false;
  let authenticatedRole = "";
  mockFetch((path) => {
    if (path === "/api/v1/auth/login") {
      authenticated = true;
      authenticatedRole = "super_admin";
      return jsonResponse(authUser);
    }
    if (path === "/api/v1/auth/logout") {
      authenticated = false;
      return new Response(null, { status: 204 });
    }
    if (path === "/api/v1/auth/me") {
      return authenticated ? jsonResponse(authUser) : jsonResponse({ message: "未登录" }, 401);
    }
    if (path === "/api/v1/tenants") {
      return authenticated && authenticatedRole === "super_admin"
        ? jsonResponse({
            items: [
              {
                id: 1,
                code: "tenant-1",
                name: "租户一",
                status: "active",
                created_at: "",
                updated_at: "",
              },
            ],
            total: 1,
            page: 1,
            page_size: 200,
          })
        : jsonResponse({ message: "需要超管权限" }, 403);
    }
    return jsonResponse({});
  });

  render(
    <MemoryRouter initialEntries={["/login"]}>
      <App />
    </MemoryRouter>,
  );

  await screen.findByRole("heading", { name: "文档智能审查平台" });
  await userEvent.setup().type(screen.getByLabelText("用户名"), "admin");
  await userEvent.type(screen.getByLabelText("密码"), "a-super-secret-password");
  await userEvent.click(screen.getByRole("button", { name: "登录" }));

  // 顶部栏已移除；品牌区与用户卡展示当前租户
  expect(await screen.findByText("平台超级管理员")).toBeInTheDocument();
  expect(screen.getAllByText(/当前租户/).length).toBeGreaterThanOrEqual(1);
  expect(screen.queryByRole("heading", { name: "文档审查控制台" })).not.toBeInTheDocument();

  // 超管点「切换」后从真实租户列表下拉选择，选中即切换
  fireEvent.click(screen.getByRole("button", { name: "切换" }));
  const select = await screen.findByLabelText("选择租户");
  // 等待租户列表异步加载出选项
  await screen.findByText("租户一（tenant-1）");
  fireEvent.change(select, { target: { value: "tenant-1" } });
  // 品牌区与用户卡同步展示新租户（切换下拉收起后仅余两处文本）
  await waitFor(() => {
    expect(document.body.textContent).toContain("当前租户：tenant-1");
  });

  // 登出需二次确认：取消则保持登录
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "退出登录" }));
  expect(screen.getByRole("dialog", { name: "退出登录" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "取消" }));
  expect(screen.getByText("平台超级管理员")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "退出登录" }));
  await user.click(screen.getByRole("button", { name: "退出" }));
  expect(await screen.findByRole("heading", { name: "文档智能审查平台" })).toBeInTheDocument();
});

test("菜单分组默认收起，点击展开后子项可见", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), "http://localhost").pathname;
    if (path === "/api/v1/auth/me") {
      return jsonResponse(authUser);
    }
    return jsonResponse({});
  });
  vi.stubGlobal("fetch", fetchMock);

  render(
    <MemoryRouter initialEntries={["/reviews"]}>
      <App />
    </MemoryRouter>,
  );

  // 一级菜单：文档审查 / 检查能力 / 两个分组
  expect(await screen.findByRole("link", { name: "文档审查" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "检查能力" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "权限管理" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "工作台" })).not.toBeInTheDocument();

  // 分组默认收起
  const toggle = screen.getByRole("button", { name: "规则管理" });
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByRole("link", { name: "概念管理" })).not.toBeInTheDocument();

  // 点击展开，子项可见；再点收起
  fireEvent.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("link", { name: "规则配置" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "概念管理" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "规则分类" })).toBeInTheDocument();
  fireEvent.click(toggle);
  expect(screen.queryByRole("link", { name: "概念管理" })).not.toBeInTheDocument();
});

test("A7 普通用户只看到已授权菜单，直访未授权路由显示无权限", async () => {
  const memberUser = {
    ...authUser,
    id: 2,
    tenant_code: "tenant-A",
    username: "member",
    display_name: "普通用户",
    roles: ["member"],
    menu_codes: ["reviews"],
  };
  mockFetch((path) =>
    path === "/api/v1/auth/me"
      ? jsonResponse(memberUser)
      : jsonResponse({ items: [], total: 0, page: 1, page_size: 20 }),
  );

  render(
    <MemoryRouter initialEntries={["/reviews"]}>
      <App />
    </MemoryRouter>,
  );

  expect(await screen.findByRole("link", { name: "文档审查" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "检查能力" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "规则管理" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "系统管理" })).not.toBeInTheDocument();

  render(
    <MemoryRouter initialEntries={["/rules"]}>
      <App />
    </MemoryRouter>,
  );
  expect(await screen.findByRole("heading", { name: "无访问权限" })).toBeInTheDocument();
});

test("A8 普通租户用户固定本租户且不能切换", async () => {
  globalThis.localStorage.setItem("document-review.tenant-id", "tenant-B");
  const memberUser = {
    ...authUser,
    id: 3,
    tenant_code: "tenant-A",
    username: "a-member",
    display_name: "租户用户",
    roles: ["member"],
    menu_codes: ["reviews"],
  };
  mockFetch((path) =>
    path === "/api/v1/auth/me"
      ? jsonResponse(memberUser)
      : jsonResponse({ items: [], total: 0, page: 1, page_size: 20 }),
  );

  render(
    <MemoryRouter initialEntries={["/reviews"]}>
      <App />
    </MemoryRouter>,
  );

  await waitFor(() =>
    expect(document.body.textContent).toContain("当前租户：tenant-A"),
  );
  expect(globalThis.localStorage.getItem("document-review.tenant-id")).toBe("tenant-A");
  expect(screen.queryByRole("button", { name: "切换" })).not.toBeInTheDocument();
});

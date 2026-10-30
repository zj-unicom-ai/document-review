// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test, vi } from "vitest";
import { useAuth } from "../auth/AuthProvider";
import { useTenant } from "../tenant/TenantProvider";
import type { AuthUser } from "../api/endpoints";
import { AppShell } from "./AppShell";

vi.mock("../auth/AuthProvider", () => ({ useAuth: vi.fn() }));
vi.mock("../tenant/TenantProvider", () => ({ useTenant: vi.fn() }));

const baseUser: AuthUser = {
  id: 1,
  tenant_code: "tenant-A",
  username: "zhangsan",
  display_name: null,
  roles: [],
  menu_codes: ["reviews"],
  status: "active",
  created_at: "",
  updated_at: "",
};

function renderShell(user: AuthUser) {
  vi.mocked(useAuth).mockReturnValue({
    user,
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
  });
  vi.mocked(useTenant).mockReturnValue({
    tenantId: user.tenant_code,
    setTenantId: vi.fn(),
    requireTenant: vi.fn(),
  });

  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <AppShell />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("左下角用户信息优先显示非空 display_name", () => {
  renderShell({ ...baseUser, display_name: "张三" });

  const name = screen.getByText("张三");
  expect(name.closest(".session-meta")).not.toBeNull();
  expect(document.querySelector(".session-avatar")?.textContent).toBe("张");
  expect(screen.queryByText("zhangsan")).not.toBeInTheDocument();
});

test("display_name 为空时回退显示 username", () => {
  renderShell({ ...baseUser, display_name: "  " });

  expect(screen.getByText("zhangsan").closest(".session-meta")).not.toBeNull();
  expect(document.querySelector(".session-avatar")?.textContent).toBe("z");
  expect(screen.queryByText("  ")).not.toBeInTheDocument();
});

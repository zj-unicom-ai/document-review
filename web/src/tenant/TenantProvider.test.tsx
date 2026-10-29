// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { afterEach, beforeEach, test, vi } from "vitest";
import { apiClient, setDefaultTenantId } from "../api/client";
import { TenantProvider, useTenant } from "./TenantProvider";

function Harness() {
  const { tenantId, setTenantId, requireTenant } = useTenant();
  const [tenantError, setTenantError] = useState("");
  return (
    <div>
      <output>{tenantId || "未选择租户"}</output>
      <button type="button" onClick={() => setTenantId("tenant-A")}>
        保存租户
      </button>
      <button
        type="button"
        onClick={() => {
          try {
            requireTenant(tenantId);
          } catch (error) {
            setTenantError(String(error));
          }
        }}
      >
        捕获租户错误
      </button>
      {tenantError ? <p>{tenantError}</p> : null}
    </div>
  );
}

function HarnessWithSwitch() {
  const { setTenantId } = useTenant();
  return (
    <>
      <button type="button" onClick={() => setTenantId("tenant-A")}>
        切换到租户 A
      </button>
      <button type="button" onClick={() => setTenantId("tenant-B")}>
        切换到租户 B
      </button>
    </>
  );
}

beforeEach(() => {
  globalThis.localStorage.removeItem("document-review.tenant-id");
});

afterEach(() => {
  vi.unstubAllGlobals();
  setDefaultTenantId("");
});

test("切换租户会保存 localStorage 并清除 Query 缓存", () => {
  const queryClient = new QueryClient();
  const clearSpy = vi.spyOn(queryClient, "clear");

  render(
    <QueryClientProvider client={queryClient}>
      <TenantProvider>
        <Harness />
      </TenantProvider>
    </QueryClientProvider>,
  );

  expect(screen.getByText("未选择租户")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "保存租户" }));

  expect(screen.getByText("tenant-A")).toBeInTheDocument();
  expect(clearSpy).toHaveBeenCalledTimes(1);
  expect(globalThis.localStorage.getItem("document-review.tenant-id")).toBe("tenant-A");
});

test("BL-129 A1/A2 切换租户后首轮请求立即携带新租户头", async () => {
  globalThis.localStorage.removeItem("document-review.tenant-id");
  const fetchMock = vi.fn(async () => new Response("{}", { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  const queryClient = new QueryClient();
  // 清缓存会触发活跃 Observer 重建；这里同步模拟首轮请求，锁定竞态顺序。
  vi.spyOn(queryClient, "clear").mockImplementation(() => {
    void apiClient.get("/api/v1/clear-triggered");
  });

  render(
    <QueryClientProvider client={queryClient}>
      <TenantProvider>
        <HarnessWithSwitch />
      </TenantProvider>
    </QueryClientProvider>,
  );

  fireEvent.click(screen.getByRole("button", { name: "切换到租户 A" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  const firstCall = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
  expect(firstCall[1].headers).toMatchObject({ "X-Tenant-Id": "tenant-A" });

  fireEvent.click(screen.getByRole("button", { name: "切换到租户 B" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  const secondCall = fetchMock.mock.calls[1] as unknown as [string, RequestInit];
  expect(secondCall[1].headers).toMatchObject({ "X-Tenant-Id": "tenant-B" });
  vi.unstubAllGlobals();
});

test("requireTenant 在空租户时抛出中文错误", () => {
  const queryClient = new QueryClient();

  render(
    <QueryClientProvider client={queryClient}>
      <TenantProvider>
        <Harness />
      </TenantProvider>
    </QueryClientProvider>,
  );

  fireEvent.click(screen.getByRole("button", { name: "捕获租户错误" }));

  expect(screen.getByText(/请先选择租户/)).toBeInTheDocument();
});

test("恢复 localStorage 租户时首次查询就携带租户头", async () => {
  globalThis.localStorage.setItem("document-review.tenant-id", "tenant-A");
  const fetchMock = vi.fn(async () => new Response("{}", { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);

  function QueryProbe() {
    useQuery({
      queryKey: ["tenant-header-probe"],
      queryFn: () => apiClient.get("/api/v1/rules"),
    });
    return null;
  }

  render(
    <QueryClientProvider client={new QueryClient()}>
      <TenantProvider>
        <QueryProbe />
      </TenantProvider>
    </QueryClientProvider>,
  );

  await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
  expect(path).toBe("/api/v1/rules");
  expect(init.headers).toMatchObject({ "X-Tenant-Id": "tenant-A" });
  vi.unstubAllGlobals();
});

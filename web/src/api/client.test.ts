// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { afterEach, expect, test, vi } from "vitest";
import { ApiError, apiClient, setDefaultTenantId } from "./client";
import { parseJsonDraft } from "../utils/json";

afterEach(() => {
  vi.unstubAllGlobals();
  setDefaultTenantId("");
});

test("apiClient 会注入租户头并解析 JSON 响应", async () => {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify({ id: 7 }), {
    status: 200,
    headers: { "content-type": "application/json" },
  }));
  vi.stubGlobal("fetch", fetchMock);
  setDefaultTenantId("tenant-A");

  const data = await apiClient.get<{ id: number }>("/api/v1/rules/7");

  expect(data).toEqual({ id: 7 });
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/v1/rules/7",
    expect.objectContaining({ headers: { "X-Tenant-Id": "tenant-A" } }),
  );
});

test("apiClient 将 FastAPI 校验错误归一为 ApiError", async () => {
  const fetchMock = vi.fn(
    async () =>
      new Response(JSON.stringify({ detail: [{ msg: "名称不能为空" }] }), {
        status: 422,
        headers: { "content-type": "application/json" },
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
  setDefaultTenantId("tenant-A");

  await expect(apiClient.post("/api/v1/rules", { name: "" })).rejects.toThrow(
    /名称不能为空/,
  );
});

test("parseJsonDraft 拒绝非法 JSON 并保留解析错误", () => {
  expect(() => parseJsonDraft("{")).toThrow(/JSON 格式不合法/);
  expect(parseJsonDraft('{"anchor":{}}')).toEqual({ anchor: {} });
});

test("ApiError 保留状态码与响应体", () => {
  const error = new ApiError(403, "平台数据只读", { code: "immutable" });

  expect(error.status).toBe(403);
  expect(error.message).toBe("平台数据只读");
  expect(error.payload).toEqual({ code: "immutable" });
});

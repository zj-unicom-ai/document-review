// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import { createExternalResource, listExternalResources } from "../../api/endpoints";
import { ExternalResourcesPage } from "./ExternalResourcesPage";

vi.mock("../../api/endpoints", () => ({
  listExternalResources: vi.fn(),
  createExternalResource: vi.fn(),
  updateExternalResource: vi.fn(),
}));

beforeEach(() => {
  globalThis.localStorage.setItem("document-review.tenant-id", "tenant-A");
  vi.mocked(listExternalResources).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
  vi.mocked(createExternalResource).mockResolvedValue({} as never);
});

test("外部资源配置 JSON 会被解析后提交", async () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <ExternalResourcesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  await screen.findByText("暂无外部资源");
  fireEvent.change(screen.getByLabelText("资源 Key"), { target: { value: "expert_library" } });
  fireEvent.change(screen.getByLabelText("资源名称"), { target: { value: "专家库" } });
  fireEvent.change(screen.getByLabelText("配置 JSON"), {
    target: { value: '{"env":"EXPERT_DB_URL"}' },
  });
  fireEvent.click(screen.getByRole("button", { name: "创建资源" }));

  await waitFor(() =>
    expect(createExternalResource).toHaveBeenCalledWith(
      expect.objectContaining({
        resource_key: "expert_library",
        name: "专家库",
        config: { env: "EXPERT_DB_URL" },
      }),
    ),
  );
});

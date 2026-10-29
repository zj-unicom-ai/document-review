// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import {
  createReview,
  deleteReview,
  listReviews,
  listRuleSets,
} from "../../api/endpoints";
import { ReviewsPage } from "./ReviewsPage";

vi.mock("../../api/endpoints", () => ({
  listRuleSets: vi.fn(),
  createReview: vi.fn(),
  listReviews: vi.fn(),
  deleteReview: vi.fn(),
}));

const runFixture = (id: number) => ({
  id,
  tenant_id: "tenant-A",
  file_name: `report-${id}.pdf`,
  file_sha256: "a",
  file_path: "storage/report.pdf",
  file_size: 10,
  status: "completed" as const,
  profile_id: 1,
  rule_plan: [],
  result: "fail" as const,
  summary: null,
  annotated_pdf_path: "storage/annotated.pdf",
  error: null,
  token_cost: 20,
  duration_ms: 100,
  created_at: "2026-10-09T10:00:00",
  updated_at: "2026-10-09T10:00:00",
  violations: [],
  rule_set_name: "文档完整性检查规则",
});

beforeEach(() => {
  vi.mocked(listRuleSets).mockResolvedValue({
    items: [
      {
        id: 9,
        tenant_id: "tenant-A",
        name: "标准包",
        is_standard_pack: false,
        items: [],
        created_at: "",
        updated_at: "",
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  });
  vi.mocked(listReviews).mockResolvedValue({
    items: [runFixture(12), runFixture(11)],
    total: 12,
    page: 1,
    page_size: 10,
  });
  vi.mocked(deleteReview).mockResolvedValue(undefined as never);
  vi.mocked(createReview).mockResolvedValue({ id: 13 } as never);
});

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/reviews"]}>
        <ReviewsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("A1：无 REVIEWS 标题块，规则集置顶，上传区含提示并可提交", async () => {
  renderPage();

  expect(screen.queryByText("审查执行")).not.toBeInTheDocument();
  expect(screen.getByLabelText("选中规则集")).toBeInTheDocument();
  expect(screen.getByText("请上传需要审查的PDF文档")).toBeInTheDocument();

  await screen.findByText("标准包");
  // 进入页面默认选中第一个规则集
  await waitFor(() =>
    expect((screen.getByLabelText("选中规则集") as HTMLSelectElement).value).toBe("9"),
  );
  const file = new File(["%PDF-1.4"], "report.pdf", { type: "application/pdf" });
  fireEvent.change(screen.getByLabelText("上传 PDF"), { target: { files: [file] } });
  fireEvent.click(screen.getByRole("button", { name: "开始审查" }));

  await waitFor(() => expect(createReview).toHaveBeenCalledWith(file, 9));
});

test("E1：无可用规则集时阻止提交并提示", async () => {
  vi.mocked(listRuleSets).mockResolvedValue({
    items: [],
    total: 0,
    page: 1,
    page_size: 20,
  });
  renderPage();

  fireEvent.click(screen.getByRole("button", { name: "开始审查" }));

  expect(await screen.findByText("请先选择规则集")).toBeInTheDocument();
  expect(createReview).not.toHaveBeenCalled();
});

test("A2：历史列表展示文件 / 规则集 / 时间 / 状态 / 操作并支持删除", async () => {
  renderPage();

  expect(await screen.findByText("report-12.pdf")).toBeInTheDocument();
  expect(screen.getAllByText("文档完整性检查规则").length).toBe(2);
  expect(screen.getAllByText("2026-10-09 10:00:00").length).toBe(2);
  expect(screen.getAllByRole("button", { name: "详情" }).length).toBe(2);
  expect(screen.getByText(/第 1 \/ 2 页（共 12 条）/)).toBeInTheDocument();

  fireEvent.click(screen.getAllByRole("button", { name: "删除" })[0]);
  fireEvent.click(await screen.findByRole("button", { name: "取消" }));
  expect(deleteReview).not.toHaveBeenCalled();

  fireEvent.click(screen.getAllByRole("button", { name: "删除" })[0]);
  fireEvent.click(await screen.findByRole("button", { name: "确认删除" }));
  await waitFor(() => expect(deleteReview).toHaveBeenCalledWith(12));
});

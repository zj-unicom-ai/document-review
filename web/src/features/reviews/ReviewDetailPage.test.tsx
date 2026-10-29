// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, test, vi } from "vitest";
import {
  downloadAnnotatedPdf,
  getReview,
  getReviewPlan,
  listClassifications,
} from "../../api/endpoints";
import { ReviewDetailPage } from "./ReviewDetailPage";

vi.mock("react-pdf", () => ({
  Document: ({
    children,
    onLoadSuccess,
  }: {
    children: React.ReactNode;
    onLoadSuccess?: (payload: { numPages: number }) => void;
  }) => {
    useEffect(() => {
      onLoadSuccess?.({ numPages: 3 });
    }, [onLoadSuccess]);
    return <div data-testid="pdf-document">{children}</div>;
  },
  Page: () => <div data-testid="pdf-page" />,
  pdfjs: { GlobalWorkerOptions: { workerSrc: "" } },
}));

vi.mock("../../api/endpoints", () => ({
  getReview: vi.fn(),
  getReviewPlan: vi.fn(),
  getRuleExecutionTrace: vi.fn(),
  downloadAnnotatedPdf: vi.fn(),
  listClassifications: vi.fn(),
}));

vi.mocked(getReviewPlan).mockResolvedValue({ items: [] });
vi.mocked(listClassifications).mockResolvedValue({
  items: [
    { id: 66, classify_id: 1002, parent_id: null, level: 1, name: "二、真实性维度审核判定规则", description: null, sort_order: 2, tenant_id: "tenant-A", created_at: "", updated_at: "" },
    { id: 67, classify_id: 10021, parent_id: 66, level: 2, name: "1.服务轨迹核验", description: null, sort_order: 1, tenant_id: "tenant-A", created_at: "", updated_at: "" },
    { id: 68, classify_id: 10022, parent_id: 66, level: 2, name: "2.服务内容与实际匹配核验", description: null, sort_order: 2, tenant_id: "tenant-A", created_at: "", updated_at: "" },
  ],
  total: 3,
  page: 1,
  page_size: 20,
});

test("审查详情：状态中文化、Tab 切换违规项与批注预览、无执行计划", async () => {
  vi.mocked(getReview).mockResolvedValue({
    id: 12,
    tenant_id: "tenant-A",
    file_name: "report.pdf",
    file_sha256: "a",
    file_path: "storage/report.pdf",
    file_size: 10,
    status: "completed",
    profile_id: 1,
    rule_plan: [
      { rule_code: "REG-001", classify_id: 67 },
      { rule_code: "REG-002", classify_id: 68 },
    ],
    result: "fail",
    summary: null,
    annotated_pdf_path: "storage/annotated.pdf",
    error: null,
    token_cost: 20,
    duration_ms: 100,
    created_at: "",
    updated_at: "",
    violations: [
      {
        rule_id: "REG-001",
        rule_name: "章节缺失",
        classify_id: 67,
        title: "章节缺失",
        severity: "严重",
        content: "缺少总结",
        page_idx: 2,
        mark_text: [],
        meta: { blocking: true, confidence: 1, skip_result: false, observation: false },
      },
    ],
  } as never);
  vi.mocked(downloadAnnotatedPdf).mockResolvedValue(
    new Blob(["%PDF"], { type: "application/pdf" }) as never,
  );

  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/reviews/12"]}>
        <Routes>
          <Route path="/reviews/:reviewId" element={<ReviewDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  // 状态中文展示；头部无 REVIEW RUN 与英文状态/耗时描述
  expect(await screen.findByText("report.pdf")).toBeInTheDocument();
  expect(screen.getByText("已完成")).toBeInTheDocument();
  expect(screen.queryByText("REVIEW RUN")).not.toBeInTheDocument();
  expect(screen.queryByText(/耗时/)).not.toBeInTheDocument();
  expect(screen.getByText("不通过")).toBeInTheDocument(); // 结果也中文化

  // 无执行计划区块
  expect(screen.queryByText("执行计划")).not.toBeInTheDocument();

  // 默认 Tab：违规项详情，左右分类联动布局
  expect(screen.getByRole("tab", { name: "违规项详情", selected: true })).toBeInTheDocument();
  expect(screen.getByLabelText("审核规则分类")).toBeInTheDocument();
  expect(screen.getAllByText("二、真实性维度审核判定规则").length).toBeGreaterThan(0);
  expect(screen.getByText("章节缺失")).toBeInTheDocument();

  // 分类树默认折叠，不展示下一级。
  const caret = screen.getByRole("button", { name: "展开 二、真实性维度审核判定规则" });
  expect(caret).toHaveAttribute("aria-expanded", "false");
  expect(caret).not.toHaveClass("expanded");
  expect(screen.queryByRole("button", { name: /1\.服务轨迹核验/ })).not.toBeInTheDocument();

  // 展开后：有问题的叶子分类是红叉，无问题的是绿勾。
  await userEvent.setup().click(caret);
  expect(caret).toHaveAttribute("aria-expanded", "true");
  expect(caret).toHaveClass("expanded");
  const failedItem = screen.getByRole("button", { name: /1\.服务轨迹核验/ });
  expect(failedItem.querySelector(".status-failed")).toBeInTheDocument();
  const passedItem = screen.getByRole("button", { name: /2\.服务内容与实际匹配核验/ });
  expect(passedItem.querySelector(".status-passed")).toBeInTheDocument();
  // 分类必须复用规则分类管理的层级数据，不允许退化为“分类 67 / 分类 69”兜底。
  expect(screen.queryByText("规则绑定的分类")).not.toBeInTheDocument();
  expect(screen.queryByText("分类 67")).not.toBeInTheDocument();
  expect(screen.queryByText("分类 69")).not.toBeInTheDocument();

  // 布局必须是左分类 / 右详情；避免外层 panel flex 覆盖导致上下堆叠。
  const workspace = document.querySelector(".violation-workspace");
  expect(workspace).not.toBeNull();
  expect(workspace?.children).toHaveLength(2);
  expect(workspace?.children[0]).toHaveClass("classification-panel");
  expect(workspace?.children[1]).toHaveClass("violation-detail-panel");

  // 点击叶子分类，右侧只展示当前分类违规；右侧滚动容器独立于页面
  fireEvent.click(failedItem);
  expect(await screen.findByText("审核不合格")).toBeInTheDocument();
  expect(screen.getByText("章节缺失")).toBeInTheDocument();
  expect(document.querySelector(".violation-detail-scroll")).not.toBeNull();

  // 切到预览 Tab：自动加载批注 PDF
  fireEvent.click(screen.getByRole("tab", { name: "预览批注PDF" }));
  await waitFor(() => expect(downloadAnnotatedPdf).toHaveBeenCalledWith(12));
  expect(await screen.findByTestId("pdf-document")).toBeInTheDocument();
  // 连续滚动渲染：mock 文档 3 页则渲染 3 个页面画布
  expect(screen.getAllByTestId("pdf-page")).toHaveLength(3);
});

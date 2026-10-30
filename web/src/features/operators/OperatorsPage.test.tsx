// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test, vi } from "vitest";
import { listOperators } from "../../api/endpoints";
import type { Operator } from "../../api/endpoints";
import { OperatorsPage } from "./OperatorsPage";

vi.mock("../../api/endpoints", () => ({ listOperators: vi.fn() }));

function makeOperator(overrides: Partial<Operator>): Operator {
  return {
    id: 1,
    op_code: "section_exists",
    name: "章节必须存在",
    description: "检查文档是否包含要求的章节。",
    applicable_data_kind: ["section"],
    params_schema: { type: "object" },
    result_semantics: "hit_is_violation",
    executor: "app.operators.section_exists:SectionExists",
    model_profile: null,
    created_at: "",
    updated_at: "",
    ...overrides,
  } as Operator;
}

function renderPage() {
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>
        <OperatorsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("A1/A2: 卡片只展示业务信息，适用对象与结果口径为中文", async () => {
  vi.mocked(listOperators).mockResolvedValue({
    items: [
      makeOperator({}),
      makeOperator({
        id: 2,
        op_code: "list_for_each",
        name: "清单逐条核查",
        description:
          "适用于文档中逐条记录的清单（如物品清单、人员名单、记录明细等）。系统会逐条取出清单中的每条记录，对每条分别执行配置的检查要求；某一条不符合时，生成一条对应的违规结果，并标注该条目的序号。",
        applicable_data_kind: ["item_list"],
      }),
    ],
    total: 2,
    page: 1,
    page_size: 20,
  });

  renderPage();

  expect(await screen.findByText("章节必须存在")).toBeInTheDocument();
  expect(screen.getByText("检查文档是否包含要求的章节。")).toBeInTheDocument();
  expect(screen.getByText("章节")).toBeInTheDocument();
  expect(screen.getAllByText("发现即问题").length).toBeGreaterThan(0);
  // BL-098 A1/A2：item_list 展示通用叫法，清单算子文案说明用途
  expect(await screen.findByText("清单逐条核查")).toBeInTheDocument();
  expect(screen.getByText(/逐条取出清单中的每条记录/)).toBeInTheDocument();
  expect(screen.getByText("结构化清单")).toBeInTheDocument();
  expect(screen.queryByText("条目清单")).not.toBeInTheDocument();
  // A1: 不渲染参数 Schema JSON 与技术编码
  expect(screen.queryByText(/"type": "object"/)).not.toBeInTheDocument();
  expect(screen.queryByText("section_exists")).not.toBeInTheDocument();
  expect(
    screen.queryByText("app.operators.section_exists:SectionExists"),
  ).not.toBeInTheDocument();
});

test("BL-111 A3: 外部数据核验未实现时置灰并标注建设中", async () => {
  vi.mocked(listOperators).mockResolvedValue({
    items: [
      makeOperator({
        id: 2,
        op_code: "external_data_check",
        name: "外部数据核验",
        description: "查询外部登记数据并与文档信息比对，核验其真实性。",
        applicable_data_kind: ["field", "table", "item_list"],
      }),
      makeOperator({
        id: 3,
        op_code: "list_for_each",
        name: "清单逐条核查",
        description:
          "适用于文档中逐条记录的清单（如物品清单、人员名单、记录明细等）。",
        applicable_data_kind: ["item_list"],
      }),
    ],
    total: 2,
    page: 1,
    page_size: 20,
  });

  renderPage();

  expect(await screen.findByText("外部数据核验")).toBeInTheDocument();
  expect(screen.getByText("建设中")).toBeInTheDocument();
  const cards = [...document.querySelectorAll(".operator-card")];
  expect(
    cards.find((c) => c.textContent?.includes("外部数据核验"))?.className,
  ).toContain("is-building");
  // BL-051 / BL-098：清单逐条核查已实现，不置灰、无建设中徽标。
  const listCard = cards.find((c) => c.textContent?.includes("清单逐条核查"));
  expect(listCard?.className).not.toContain("is-building");
});

test("E2: 未知枚举值回退展示原始编码", async () => {
  vi.mocked(listOperators).mockResolvedValue({
    items: [
      makeOperator({
        applicable_data_kind: ["unknown_kind"],
        result_semantics: "weird_semantics",
      }),
    ],
    total: 1,
    page: 1,
    page_size: 20,
  });

  renderPage();

  expect(await screen.findByText("unknown_kind")).toBeInTheDocument();
  expect(screen.getByText("weird_semantics")).toBeInTheDocument();
});

test("E1: 算子接口失败时展示错误横幅", async () => {
  vi.mocked(listOperators).mockRejectedValue(new Error("boom"));

  renderPage();

  await waitFor(() => {
    expect(screen.getByText("算子读取失败")).toBeInTheDocument();
  });
});

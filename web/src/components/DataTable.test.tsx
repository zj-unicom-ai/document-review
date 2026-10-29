// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import { DataTable } from "./DataTable";

type Row = { id: number; name: string; actions: string };

const rows: Row[] = [{ id: 1, name: "根分类", actions: "" }];

describe("DataTable", () => {
  test("BL-094：支持列级对齐和固定列宽", () => {
    render(
      <DataTable
        columns={[
          { key: "id", title: "编号", align: "center", width: 150, render: (row: Row) => row.id },
          { key: "name", title: "名称", align: "left", width: 430, minWidth: 360, render: (row: Row) => row.name },
          { key: "actions", title: "操作", align: "center", width: 180, render: (row: Row) => row.actions },
        ]}
        rows={rows}
        rowKey={(row) => row.id}
      />,
    );

    expect(document.querySelector("table")).toHaveClass("column-fixed");
    expect(screen.getByRole("columnheader", { name: "编号" })).toHaveClass(
      "column-align-center",
    );
    expect(screen.getByRole("columnheader", { name: "名称" })).toHaveClass(
      "column-align-left",
    );
    expect(screen.getByRole("cell", { name: "根分类" })).toHaveClass("column-align-left");
  });
});

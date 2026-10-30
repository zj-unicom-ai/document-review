// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import type { ReactNode } from "react";

type DataTableAlign = "left" | "center" | "right";

export type DataTableColumn<T> = {
  key: string;
  title: ReactNode;
  render: (row: T) => ReactNode;
  align?: DataTableAlign;
  width?: number | string;
  minWidth?: number | string;
  headerClassName?: string;
};

function alignmentClass(align: DataTableAlign = "center") {
  return `column-align-${align}`;
}

function columnStyle<T>(column: DataTableColumn<T>) {
  return {
    width: column.width,
    minWidth: column.minWidth,
  };
}

function headerClassName<T>(column: DataTableColumn<T>) {
  return ["table-header", alignmentClass(column.align), column.headerClassName]
    .filter(Boolean)
    .join(" ");
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  empty = "暂无数据",
}: {
  columns: Array<DataTableColumn<T>>;
  rows: T[];
  rowKey: (row: T) => string | number;
  empty?: string;
}) {
  const hasColumnWidths = columns.some((column) => column.width || column.minWidth);

  return (
    <div className="table-wrap">
      <table className={`data-table ${hasColumnWidths ? "column-fixed" : ""}`}>
        <colgroup>
          {columns.map((column) => (
            <col key={column.key} style={columnStyle(column)} />
          ))}
        </colgroup>
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                className={headerClassName(column)}
                style={columnStyle(column)}
              >
                {column.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) => (
                <td key={column.key} className={alignmentClass(column.align)}>
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 ? <p className="empty-row">{empty}</p> : null}
    </div>
  );
}

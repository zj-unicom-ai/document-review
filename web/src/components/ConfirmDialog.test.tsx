// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";

describe("ConfirmDialog", () => {
  test("确认与取消分别回调且不使用浏览器确认", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    const { rerender } = render(
      <ConfirmDialog
        open
        title="删除模板"
        message="确定删除模板「模板 A」吗？"
        detail={["将删除 1 个模板"]}
        onConfirm={onConfirm}
        onClose={onClose}
      />,
    );

    expect(screen.getByRole("dialog", { name: "删除模板" })).toBeInTheDocument();
    expect(screen.getByText("确定删除模板「模板 A」吗？")).toBeInTheDocument();
    expect(screen.getByText("将删除 1 个模板")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "确认删除" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);

    rerender(
      <ConfirmDialog
        open
        title="退出登录"
        message="确定退出登录吗？"
        confirmLabel="退出"
        onConfirm={onConfirm}
        onClose={onClose}
      />,
    );
    await user.click(screen.getByRole("button", { name: "退出" }));
    expect(onConfirm).toHaveBeenCalledTimes(2);

    await user.click(screen.getByRole("button", { name: "取消" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

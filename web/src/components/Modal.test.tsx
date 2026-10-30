// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import globalCss from "../styles/global.css?raw";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { Modal } from "./Modal";

test("Modal 关闭按钮触发 onClose", async () => {
  const user = userEvent.setup();
  const onClose = vi.fn();
  render(
    <Modal title="新增分类" open onClose={onClose}>
      <p>表单内容</p>
    </Modal>,
  );

  await user.click(screen.getByRole("button", { name: "关闭" }));

  expect(onClose).toHaveBeenCalledTimes(1);
});

// fixed 定位若缺少 inset 基准，会停留在文档流原位置，导致按钮越界不可点。
test("Modal 遮罩声明完整视口定位基准", () => {
  const css = globalCss;
  const rule = css.match(/\.modal-backdrop\s*{([^}]*)}/);

  expect(rule?.[1]).toBeTruthy();
  expect(rule?.[1]).toMatch(/(^|;)\s*inset:\s*0(?:\s*;|$)/);
});

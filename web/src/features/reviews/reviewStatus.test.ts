// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { expect, test } from "vitest";
import { isTerminalReviewStatus } from "./reviewStatus";

test("审查非终态持续轮询，终态停止", () => {
  expect(isTerminalReviewStatus("executing")).toBe(false);
  expect(isTerminalReviewStatus("completed")).toBe(true);
  expect(isTerminalReviewStatus("failed")).toBe(true);
});

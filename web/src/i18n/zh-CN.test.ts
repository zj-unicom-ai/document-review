// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { expect, test } from "vitest";
import { ruleTypeLabel, statusLabel } from "./zh-CN";

// BL-103：状态与规则类型枚举统一翻译，未知值回退原始编码
test("状态枚举翻译为中文", () => {
  expect(statusLabel("completed")).toBe("已完成");
  expect(statusLabel("active")).toBe("启用");
  expect(statusLabel("inactive")).toBe("停用");
  expect(statusLabel("draft")).toBe("草稿");
  expect(statusLabel("retired")).toBe("已停用");
  expect(statusLabel("needs_review")).toBe("需人工复核");
  expect(statusLabel("no_service")).toBe("无法审查");
});

test("规则类型翻译：llm 大写展示，其余中文", () => {
  expect(ruleTypeLabel("llm")).toBe("LLM");
  expect(ruleTypeLabel("hybrid")).toBe("混合");
  expect(ruleTypeLabel("structured")).toBe("结构化");
});

test("未知枚举值回退原始编码", () => {
  expect(statusLabel("unknown_kind")).toBe("unknown_kind");
  expect(ruleTypeLabel("unknown_type")).toBe("unknown_type");
});

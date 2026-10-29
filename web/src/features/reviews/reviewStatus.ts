// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { statusLabel } from "../../i18n/zh-CN";

export function isTerminalReviewStatus(status: string) {
  return status === "completed" || status === "failed";
}

/** 审查状态 / 结论的中文展示；统一走全局状态映射，未知值回退原编码。 */
export function reviewStatusLabel(status: string) {
  return statusLabel(status);
}

// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

export const zhCN = {
  app: {
    title: "文档审查控制台",
    currentTenant: "当前租户",
    saveTenant: "保存租户",
  },
  errors: {
    requestFailed: "请求失败，请检查后端服务状态",
    tenantRequired: "请先选择租户",
    invalidJson: "JSON 格式不合法",
  },
} as const;

// 数据类型（data_kind）的通用中文叫法；未知值回退原始编码（BL-098 E1）
export const DATA_KIND_LABELS: Record<string, string> = {
  document: "全文",
  section: "章节",
  table: "表格",
  field: "字段",
  image_group: "照片",
  item_list: "结构化清单",
};

export function dataKindLabel(value: string): string {
  return DATA_KIND_LABELS[value] ?? value;
}

// 各类状态枚举的中文叫法；未知值回退原始编码。覆盖审查状态、审查结论、
// 租户 / 模板状态与规则执行状态（BL-103）。
export const STATUS_LABELS: Record<string, string> = {
  pending: "待处理",
  parsing: "解析中",
  profiling: "画像中",
  planning: "规划中",
  executing: "执行中",
  aggregating: "汇总中",
  running: "执行中",
  completed: "已完成",
  failed: "失败",
  pass: "通过",
  fail: "不通过",
  needs_review: "需人工复核",
  no_service: "无法审查",
  active: "启用",
  inactive: "停用",
  draft: "草稿",
  retired: "已停用",
  disabled: "已停用",
  enabled: "启用",
  success: "成功",
  fallback_annotated: "已兜底标注",
  skipped: "已跳过",
};

export function statusLabel(value: string): string {
  return STATUS_LABELS[value] ?? value;
}

// 规则类型的中文叫法；llm 按惯例展示大写 LLM。
export const RULE_TYPE_LABELS: Record<string, string> = {
  structured: "结构化",
  llm: "LLM",
  hybrid: "混合",
};

export function ruleTypeLabel(value: string): string {
  return RULE_TYPE_LABELS[value] ?? value;
}

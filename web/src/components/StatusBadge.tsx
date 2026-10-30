// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { statusLabel } from "../i18n/zh-CN";

const toneMap: Record<string, string> = {
  completed: "ok",
  pass: "ok",
  success: "ok",
  active: "ok",
  enabled: "ok",
  failed: "danger",
  fail: "danger",
  error: "danger",
  inactive: "muted",
  disabled: "muted",
  pending: "warning",
  parsing: "warning",
  profiling: "warning",
  planning: "warning",
  executing: "warning",
  aggregating: "warning",
  running: "warning",
};

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  return <span className={`status-badge tone-${toneMap[status] ?? "muted"}`}>{label ?? statusLabel(status)}</span>;
}

// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

export function parseJsonDraft<T = unknown>(draft: string): T {
  try {
    return JSON.parse(draft) as T;
  } catch (error) {
    throw new Error(`JSON 格式不合法：${error instanceof Error ? error.message : String(error)}`);
  }
}

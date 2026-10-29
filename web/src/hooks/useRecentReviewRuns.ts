// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

const storageKey = "document-review.recent-runs";

export function useRecentReviewRuns() {
  const read = () => {
    try {
      const value = JSON.parse(globalThis.localStorage.getItem(storageKey) ?? "[]") as number[];
      return Array.isArray(value) ? value.filter((item) => typeof item === "number").slice(0, 10) : [];
    } catch {
      return [];
    }
  };

  return {
    recent: read(),
    remember(id: number) {
      const next = [id, ...read().filter((item) => item !== id)].slice(0, 10);
      globalThis.localStorage.setItem(storageKey, JSON.stringify(next));
    },
  };
}

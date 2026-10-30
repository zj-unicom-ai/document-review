// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { setDefaultTenantId } from "../api/client";

const storageKey = "document-review.tenant-id";

type TenantContextValue = {
  tenantId: string;
  setTenantId: (tenantId: string) => void;
  requireTenant: (tenantId: string) => string;
};

const TenantContext = createContext<TenantContextValue | null>(null);

export function TenantProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [tenantId, setCurrentTenantId] = useState(() => {
    const saved = globalThis.localStorage.getItem(storageKey);
    const normalized = saved ? saved.trim() : "";
    // 首个子组件发起 Query 前必须完成默认租户头注入。
    setDefaultTenantId(normalized);
    return normalized;
  });

  useEffect(() => {
    setDefaultTenantId(tenantId);
  }, [tenantId]);

  const setTenantId = useCallback(
    (nextTenantId: string) => {
      const normalized = nextTenantId.trim();
      // 必须先更新 API 默认租户头，再清缓存；清缓存可能同步触发首轮重查。
      setDefaultTenantId(normalized);
      if (normalized) {
        globalThis.localStorage.setItem(storageKey, normalized);
      } else {
        globalThis.localStorage.removeItem(storageKey);
      }
      queryClient.clear();
      setCurrentTenantId(normalized);
    },
    [queryClient],
  );

  const value = useMemo<TenantContextValue>(
    () => ({
      tenantId,
      setTenantId,
      requireTenant(current: string) {
        const normalized = current.trim();
        if (!normalized) {
          throw new Error("请先选择租户");
        }
        return normalized;
      },
    }),
    [setTenantId, tenantId],
  );

  return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>;
}

export function useTenant() {
  const context = useContext(TenantContext);
  if (!context) {
    throw new Error("useTenant 必须在 TenantProvider 内使用");
  }
  return context;
}

// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "./AuthProvider";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { loading, user } = useAuth();
  const location = useLocation();

  if (loading) {
    return <section className="tenant-gate">正在检查登录状态...</section>;
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}

/** 菜单级路由守卫：前端只负责体验，API 仍独立执行同一权限判断。 */
export function RequirePermission({
  menuCode,
  children,
}: {
  menuCode: string;
  children: ReactNode;
}) {
  const { loading, user } = useAuth();

  if (loading) {
    return <section className="tenant-gate">正在检查权限...</section>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (!(user.menu_codes ?? []).includes(menuCode)) {
    return (
      <section className="permission-denied">
        <h2>无访问权限</h2>
        <p>当前角色未开通该菜单，请联系租户管理员调整权限。</p>
      </section>
    );
  }
  return children;
}

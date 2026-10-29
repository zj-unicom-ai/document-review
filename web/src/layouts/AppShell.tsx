// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { listTenants } from "../api/endpoints";
import { useAuth } from "../auth/AuthProvider";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { useTenant } from "../tenant/TenantProvider";

type MenuLeaf = { to: string; label: string; menuCode: string };
type MenuGroup = { label: string; children: MenuLeaf[] };
type MenuItem = MenuLeaf | MenuGroup;

function isGroup(item: MenuItem): item is MenuGroup {
  return "children" in item;
}

const menu: MenuItem[] = [
  { to: "/reviews", label: "文档审查", menuCode: "reviews" },
  { to: "/operators", label: "检查能力", menuCode: "operators" },
  {
    label: "规则管理",
    children: [
      { to: "/rules", label: "规则配置", menuCode: "rules" },
      { to: "/concepts", label: "概念管理", menuCode: "concepts" },
      { to: "/classifications", label: "规则分类", menuCode: "classifications" },
      { to: "/rule-sets", label: "规则集", menuCode: "rule_sets" },
    ],
  },
  {
    label: "系统管理",
    children: [
      { to: "/system/users", label: "用户管理", menuCode: "system_users" },
      { to: "/system/roles", label: "角色管理", menuCode: "system_roles" },
      { to: "/system/tenants", label: "租户管理", menuCode: "system_tenants" },
      { to: "/system/templates", label: "模板管理", menuCode: "system_templates" },
      { to: "/system/resources", label: "资源管理", menuCode: "system_resources" },
    ],
  },
];

/** 组内任一路径处于激活时默认展开该组。 */
function groupContainsActive(item: MenuGroup, pathname: string) {
  return item.children.some(
    (child) => pathname === child.to || pathname.startsWith(`${child.to}/`),
  );
}

function visibleItems(items: MenuItem[], allowedMenus: Set<string>): MenuItem[] {
  return items
    .map((item) => {
      if (!isGroup(item)) {
        return allowedMenus.has(item.menuCode) ? item : null;
      }
      const children = item.children.filter((child) => allowedMenus.has(child.menuCode));
      return children.length ? { ...item, children } : null;
    })
    .filter((item): item is MenuItem => item !== null);
}

export function AppShell() {
  const { user, logout } = useAuth();
  const { tenantId, setTenantId } = useTenant();
  const location = useLocation();
  const isSuperAdmin = user?.roles?.includes("super_admin") ?? false;
  const allowedMenus = useMemo(() => new Set(user?.menu_codes ?? []), [user]);
  const visibleMenu = useMemo(() => visibleItems(menu, allowedMenus), [allowedMenus]);
  const displayName = user?.display_name?.trim() || user?.username || "未登录";
  const [switching, setSwitching] = useState(false);
  const [logoutOpen, setLogoutOpen] = useState(false);
  const switchSelectRef = useRef<HTMLSelectElement | null>(null);

  // 普通租户用户不能沿用本地缓存的其他租户，登录身份是唯一事实来源。
  useEffect(() => {
    if (!user || isSuperAdmin) return;
    if (tenantId !== user.tenant_code) setTenantId(user.tenant_code);
  }, [isSuperAdmin, setTenantId, tenantId, user]);

  const [expanded, setExpanded] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(
      visibleMenu
        .filter(isGroup)
        .map((group) => [group.label, groupContainsActive(group, location.pathname)]),
    ),
  );

  // 直接访问 / 刷新到组内页面时同步默认展开
  useEffect(() => {
    setExpanded((current) => {
      const next = { ...current };
      for (const group of visibleMenu.filter(isGroup)) {
        if (groupContainsActive(group, location.pathname)) next[group.label] = true;
      }
      return next;
    });
  }, [location.pathname, visibleMenu]);

  const tenants = useQuery({
    queryKey: ["tenants", "switcher"],
    queryFn: () => listTenants({ pageSize: 200 }),
    enabled: isSuperAdmin && switching,
  });

  useEffect(() => {
    if (switching) switchSelectRef.current?.focus();
  }, [switching]);

  function handleTenantChange(next: string) {
    if (next && next !== tenantId) setTenantId(next);
    setSwitching(false);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">DR</span>
          <div>
            <strong>文档审查</strong>
            <div className="brand-tenant">
              {switching && isSuperAdmin ? (
                <select
                  ref={switchSelectRef}
                  className="brand-tenant-select"
                  aria-label="选择租户"
                  value={tenantId}
                  onChange={(event) => handleTenantChange(event.target.value)}
                  onBlur={() => setSwitching(false)}
                >
                  <option value="">
                    {tenants.isPending ? "租户加载中..." : "请选择租户"}
                  </option>
                  {(tenants.data?.items ?? []).map((tenant) => (
                    <option key={tenant.id} value={tenant.code}>
                      {tenant.name}（{tenant.code}）
                    </option>
                  ))}
                </select>
              ) : (
                <>
                  <small>当前租户：{tenantId || "未选择"}</small>
                  {isSuperAdmin ? (
                    <button
                      type="button"
                      className="brand-switch"
                      onClick={() => setSwitching(true)}
                    >
                      切换
                    </button>
                  ) : null}
                </>
              )}
            </div>
          </div>
        </div>
        <nav aria-label="主导航">
          {visibleMenu.map((item) =>
            isGroup(item) ? (
              <div className="nav-group" key={item.label}>
                <button
                  type="button"
                  className="nav-group-toggle"
                  aria-expanded={Boolean(expanded[item.label])}
                  onClick={() =>
                    setExpanded((current) => ({
                      ...current,
                      [item.label]: !current[item.label],
                    }))
                  }
                >
                  <span className="nav-caret" aria-hidden="true" />
                  {item.label}
                </button>
                {expanded[item.label] ? (
                  <div className="nav-children">
                    {item.children.map((child) => (
                      <NavLink key={child.to} to={child.to} end>
                        {child.label}
                      </NavLink>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : (
              <NavLink key={item.to} to={item.to} end>
                {item.label}
              </NavLink>
            ),
          )}
        </nav>
        <div className="session-card">
          <div className="session-row">
            <span className="session-avatar" aria-hidden="true">
              {displayName.slice(0, 1)}
            </span>
            <div className="session-meta">
              <strong>{displayName}</strong>
            </div>
            <button
              type="button"
              className="session-exit"
              aria-label="退出登录"
              title="退出登录"
              onClick={() => {
                // 二次确认，避免误触退出
                setLogoutOpen(true);
              }}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
            </button>
          </div>
        </div>
      </aside>
      <div className="shell-main">
        <main>
          <Outlet />
        </main>
      </div>
      <ConfirmDialog
        open={logoutOpen}
        title="退出登录"
        message="确定退出登录吗？"
        confirmLabel="退出"
        onConfirm={() => {
          setLogoutOpen(false);
          void logout();
        }}
        onClose={() => setLogoutOpen(false)}
      />
    </div>
  );
}

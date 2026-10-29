# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""菜单级 RBAC 的静态权限目录与固定角色编码。"""

from __future__ import annotations

from dataclasses import dataclass

SUPER_ADMIN_ROLE = "super_admin"
TENANT_ADMIN_ROLE = "tenant_admin"
MEMBER_ROLE = "member"


@dataclass(frozen=True)
class MenuPermission:
    """一个菜单码即一个后端 API 权限码。"""

    code: str
    name: str
    group: str
    assignable: bool = True
    # 平台页面菜单真实父级；None 表示一级菜单。
    parent: str | None = None


MENU_PERMISSIONS: tuple[MenuPermission, ...] = (
    MenuPermission("reviews", "文档审查", "业务"),
    MenuPermission("operators", "检查能力", "业务"),
    MenuPermission("rules", "规则配置", "规则管理", parent="规则管理"),
    MenuPermission("concepts", "概念管理", "规则管理", parent="规则管理"),
    MenuPermission("classifications", "规则分类", "规则管理", parent="规则管理"),
    MenuPermission("rule_sets", "规则集", "规则管理", parent="规则管理"),
    MenuPermission("system_templates", "模板管理", "系统管理", parent="系统管理"),
    MenuPermission("system_resources", "资源管理", "系统管理", parent="系统管理"),
    MenuPermission("system_users", "用户管理", "系统管理", assignable=False, parent="系统管理"),
    MenuPermission("system_roles", "角色管理", "系统管理", assignable=False, parent="系统管理"),
    MenuPermission("system_tenants", "租户管理", "平台管理", assignable=False),
)

ALL_MENU_CODES = {item.code for item in MENU_PERMISSIONS}
TENANT_ASSIGNABLE_MENUS = tuple(item for item in MENU_PERMISSIONS if item.assignable)
ADMIN_ONLY_MENUS = {
    "system_users",
    "system_roles",
}
PLATFORM_ONLY_MENUS = {"system_tenants"}


def is_valid_menu_code(code: str) -> bool:
    return code in ALL_MENU_CODES

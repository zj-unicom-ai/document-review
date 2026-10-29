// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  createRole,
  deleteRole,
  listMenuPermissions,
  listRoles,
  updateRole,
  type MenuPermission,
  type Role,
} from "../../api/endpoints";
import { Button } from "../../components/Button";
import { DataTable } from "../../components/DataTable";
import { Field, TextArea, TextInput } from "../../components/Field";
import { Modal } from "../../components/Modal";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/StatusBadge";
import { ErrorBanner } from "../../components/StateBlocks";

export function RolesPage() {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedMenus, setSelectedMenus] = useState<string[]>([]);
  const [formError, setFormError] = useState("");
  const [actionError, setActionError] = useState("");
  const [expandedGroups, setExpandedGroups] = useState<string[]>([]);

  const roles = useQuery({ queryKey: ["roles"], queryFn: () => listRoles({ pageSize: 200 }) });
  const permissions = useQuery({ queryKey: ["menu-permissions"], queryFn: listMenuPermissions });
  const menuTree = useMemo(() => {
    const groups = new Map<string, MenuPermission[]>();
    const nodes: Array<
      | { kind: "leaf"; item: MenuPermission }
      | { kind: "group"; name: string; items: MenuPermission[] }
    > = [];
    (permissions.data ?? [])
      .filter((item) => item.assignable)
      .forEach((item) => {
        const parent = item.parent ?? null;
        if (!parent) {
          nodes.push({ kind: "leaf", item });
          return;
        }
        let items = groups.get(parent);
        if (!items) {
          items = [];
          groups.set(parent, items);
          nodes.push({ kind: "group", name: parent, items });
        }
        items.push(item);
      });
    return nodes;
  }, [permissions.data]);

  function toggleMenuGroup(items: MenuPermission[]) {
    const codes = items.map((item) => item.code);
    const allSelected = codes.every((code) => selectedMenus.includes(code));
    setSelectedMenus((current) =>
      allSelected
        ? current.filter((code) => !codes.includes(code))
        : Array.from(new Set([...current, ...codes])),
    );
  }

  const create = useMutation({
    mutationFn: () =>
      createRole({
        code: code.trim(),
        name: name.trim(),
        description: description.trim(),
        menu_codes: selectedMenus,
      }),
    onSuccess: async () => {
      setFormOpen(false);
      resetForm();
      await queryClient.invalidateQueries({ queryKey: ["roles"] });
    },
    onError: (error) => setFormError(error instanceof Error ? error.message : String(error)),
  });

  const update = useMutation({
    mutationFn: () => {
      if (editingRole === null) {
        throw new Error("缺少待编辑角色");
      }
      return updateRole(
        editingRole.id,
        editingRole.code === "member"
          ? { menu_codes: selectedMenus }
          : {
              name: name.trim(),
              description: description.trim(),
              menu_codes: selectedMenus,
            },
      );
    },
    onSuccess: async () => {
      setFormOpen(false);
      resetForm();
      await queryClient.invalidateQueries({ queryKey: ["roles"] });
    },
    onError: (error) => setFormError(error instanceof Error ? error.message : String(error)),
  });

  const remove = useMutation({
    mutationFn: (id: number) => deleteRole(id),
    onSuccess: async () => {
      setActionError("");
      await queryClient.invalidateQueries({ queryKey: ["roles"] });
    },
    onError: (error) => setActionError(error instanceof Error ? error.message : String(error)),
  });

  function openEdit(role: Role) {
    setCode(role.code);
    setName(role.name);
    setDescription(role.description ?? "");
    setSelectedMenus(role.menu_codes ?? []);
    setEditingRole(role);
    setFormError("");
    setFormOpen(true);
  }

  function resetForm() {
    setCode("");
    setName("");
    setDescription("");
    setSelectedMenus([]);
    setEditingRole(null);
    setExpandedGroups([]);
    setFormError("");
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="SYSTEM"
        title="角色管理"
        description="创建租户自定义角色，并在表单内维护菜单权限。"
        actions={
          <Button
            variant="primary"
            onClick={() => {
              resetForm();
              setFormOpen(true);
            }}
          >
            新增角色
          </Button>
        }
      />
      <ErrorBanner error={roles.error} title="角色读取失败" />
      <ErrorBanner error={actionError} title="角色操作失败" />
      <DataTable
        columns={[
          { key: "name", title: "角色名称", render: (row) => row.name },
          { key: "code", title: "编码", render: (row) => row.code },
          { key: "type", title: "类型", render: (row) => (row.is_system ? "内置" : "自定义") },
          { key: "status", title: "状态", render: (row) => <StatusBadge status={row.status} /> },
          { key: "user_count", title: "用户数", render: (row) => row.user_count },
          {
            key: "actions",
            title: "操作",
            render: (row) => (
              <div className="table-actions">
                <Button
                  disabled={row.is_system && row.code !== "member"}
                  title={
                    row.is_system && row.code !== "member" ? "该内置角色不允许编辑" : undefined
                  }
                  onClick={() => openEdit(row)}
                >
                  编辑
                </Button>
                <Button
                  variant="danger"
                  disabled={row.is_system || remove.isPending}
                  title={row.is_system ? "内置角色不允许删除" : undefined}
                  onClick={() => remove.mutate(row.id)}
                >
                  删除
                </Button>
              </div>
            ),
          },
        ]}
        rows={roles.data?.items ?? []}
        rowKey={(row) => row.id}
        empty="暂无角色"
      />

      <Modal
        className="role-form-modal"
        title={editingRole === null ? "新增角色" : "编辑角色"}
        open={formOpen}
        onClose={() => setFormOpen(false)}
      >
        <form
          className="modal-form"
          onSubmit={(event) => {
            event.preventDefault();
            setFormError("");
            if (editingRole === null) {
              create.mutate();
            } else {
              update.mutate();
            }
          }}
        >
          <ErrorBanner error={formError} title="角色保存失败" />
          <div className="form-grid role-form-grid">
            <Field label="角色编码" required hint="仅字母、数字、下划线或中划线。">
              <TextInput
                value={code}
                disabled={editingRole !== null}
                onChange={(event) => setCode(event.target.value)}
              />
            </Field>
            <Field label="角色名称" required>
              <TextInput
                value={name}
                disabled={editingRole?.code === "member"}
                onChange={(event) => setName(event.target.value)}
              />
            </Field>
          </div>
          <Field label="描述">
            <TextArea
              className="text-area compact"
              value={description}
              disabled={editingRole?.code === "member"}
              onChange={(event) => setDescription(event.target.value)}
            />
          </Field>
          <p className="menu-permission-label">菜单权限</p>
          <div className="menu-permission-tree" role="group" aria-label="菜单权限">
            {menuTree.map((node) => {
              if (node.kind === "leaf") {
                return (
                  <label className="menu-tree-row" key={node.item.code}>
                    <input
                      type="checkbox"
                      checked={selectedMenus.includes(node.item.code)}
                      onChange={() =>
                        setSelectedMenus((current) =>
                          current.includes(node.item.code)
                            ? current.filter((menuCode) => menuCode !== node.item.code)
                            : [...current, node.item.code],
                        )
                      }
                    />
                    <span>{node.item.name}</span>
                  </label>
                );
              }

              const expanded = expandedGroups.includes(node.name);
              const selectedCount = node.items.filter((item) =>
                selectedMenus.includes(item.code),
              ).length;
              const allSelected = selectedCount === node.items.length;
              return (
                <div className="menu-tree-group" key={node.name}>
                  <div className="menu-tree-parent">
                    <input
                      type="checkbox"
                      aria-label={`全选：${node.name}`}
                      checked={allSelected}
                      ref={(checkbox) => {
                        if (checkbox) {
                          checkbox.indeterminate =
                            selectedCount > 0 && selectedCount < node.items.length;
                        }
                      }}
                      onChange={() => toggleMenuGroup(node.items)}
                    />
                    <button
                      type="button"
                      className="menu-tree-toggle"
                      aria-expanded={expanded}
                      aria-label={`${expanded ? "收起" : "展开"}：${node.name}`}
                      onClick={() =>
                        setExpandedGroups((current) =>
                          current.includes(node.name)
                            ? current.filter((group) => group !== node.name)
                            : [...current, node.name],
                        )
                      }
                    >
                      <span
                        className={`menu-tree-caret ${expanded ? "is-expanded" : ""}`}
                        aria-hidden="true"
                      />
                      <span>{node.name}</span>
                    </button>
                    <span className="menu-tree-count">
                      {selectedCount}/{node.items.length}
                    </span>
                  </div>
                  {expanded ? (
                    <div className="menu-tree-children">
                      {node.items.map((item) => (
                        <label className="menu-tree-child" key={item.code}>
                          <input
                            type="checkbox"
                            checked={selectedMenus.includes(item.code)}
                            onChange={() =>
                              setSelectedMenus((current) =>
                                current.includes(item.code)
                                  ? current.filter((menuCode) => menuCode !== item.code)
                                  : [...current, item.code],
                              )
                            }
                          />
                          <span>{item.name}</span>
                        </label>
                      ))}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
          <div className="form-actions">
            <Button type="button" onClick={() => setFormOpen(false)}>
              取消
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={
                !code.trim() ||
                !name.trim() ||
                (editingRole?.code === "member" && selectedMenus.length === 0) ||
                create.isPending ||
                update.isPending
              }
            >
              保存角色
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

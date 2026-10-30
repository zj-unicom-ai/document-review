// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  createUser,
  deleteUser,
  listRoles,
  listUsers,
  updateUser,
  type Role,
  type UserAccount,
} from "../../api/endpoints";
import { Button } from "../../components/Button";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { DataTable } from "../../components/DataTable";
import { Field, TextInput } from "../../components/Field";
import { Modal } from "../../components/Modal";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/StatusBadge";
import { ErrorBanner } from "../../components/StateBlocks";


type RoleMultiSelectProps = {
  roles: Role[];
  value: number[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onChange: (value: number[]) => void;
};

function RoleMultiSelect({ roles, value, open, onOpenChange, onChange }: RoleMultiSelectProps) {
  const selectedRoles = roles.filter((role) => value.includes(role.id));

  return (
    <div className="multi-select">
      <div className={`multi-select-trigger ${selectedRoles.length ? "has-value" : ""}`}>
        {selectedRoles.length > 0 ? (
          <div className="multi-select-chips">
            {selectedRoles.map((role) => (
              <span key={role.id} className="multi-select-chip">
                <span className="multi-select-chip-name">{role.name}</span>
                <button
                  type="button"
                  className="multi-select-chip-remove"
                  aria-label={`移除角色：${role.name}`}
                  onClick={() => onChange(value.filter((roleId) => roleId !== role.id))}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        ) : null}
        <button
          type="button"
          className={`multi-select-toggle ${selectedRoles.length ? "is-compact" : ""}`}
          aria-label="选择角色"
          aria-haspopup="listbox"
          aria-expanded={open}
          onClick={() => onOpenChange(!open)}
        >
          {selectedRoles.length === 0 ? (
            <span className="multi-select-value">请选择角色</span>
          ) : null}
          <span className={`multi-select-caret ${open ? "is-open" : ""}`} aria-hidden="true" />
        </button>
      </div>
      {open ? (
        <ul className="multi-select-panel" role="listbox" aria-label="可选角色" aria-multiselectable="true">
          {roles.map((role) => {
            const selected = value.includes(role.id);
            return (
              <li key={role.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className={`multi-select-option ${selected ? "is-selected" : ""}`}
                  onClick={() => {
                    onChange(
                      selected
                        ? value.filter((roleId) => roleId !== role.id)
                        : [...value, role.id],
                    );
                  }}
                >
                  <span>{role.name}</span>
                  <small>{role.code}</small>
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

export function UsersPage() {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editingUserId, setEditingUserId] = useState<number | null>(null);
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [selectedRoleIds, setSelectedRoleIds] = useState<number[]>([]);
  const [formError, setFormError] = useState("");
  const [actionError, setActionError] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<UserAccount | null>(null);
  const [roleSelectOpen, setRoleSelectOpen] = useState(false);

  const users = useQuery({ queryKey: ["users"], queryFn: () => listUsers({ pageSize: 200 }) });
  const roles = useQuery({ queryKey: ["roles", "user-form"], queryFn: () => listRoles({ pageSize: 200 }) });

  const create = useMutation({
    mutationFn: () =>
      createUser({
        username: username.trim(),
        display_name: displayName.trim() || null,
        password,
        role_ids: selectedRoleIds,
      }),
    onSuccess: async () => {
      setFormOpen(false);
      resetForm();
      await queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (error) => setFormError(error instanceof Error ? error.message : String(error)),
  });

  const update = useMutation({
    mutationFn: () => {
      if (editingUserId === null) {
        throw new Error("缺少待编辑用户");
      }
      return updateUser(editingUserId, {
        display_name: displayName.trim() || null,
        ...(password ? { password } : {}),
        role_ids: selectedRoleIds,
      });
    },
    onSuccess: async () => {
      setFormOpen(false);
      resetForm();
      await queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (error) => setFormError(error instanceof Error ? error.message : String(error)),
  });

  const remove = useMutation({
    mutationFn: (id: number) => deleteUser(id),
    onSuccess: async () => {
      setDeleteTarget(null);
      setActionError("");
      await queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (error) => setActionError(error instanceof Error ? error.message : String(error)),
  });

  const toggleStatus = useMutation({
    mutationFn: (user: { id: number; status: string }) =>
      updateUser(user.id, { status: user.status === "active" ? "inactive" : "active" }),
    onSuccess: async () => {
      setActionError("");
      await queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (error) => setActionError(error instanceof Error ? error.message : String(error)),
  });

  function resetForm() {
    setUsername("");
    setDisplayName("");
    setPassword("");
    setSelectedRoleIds([]);
    setEditingUserId(null);
    setRoleSelectOpen(false);
    setFormError("");
  }

  function openEdit(user: UserAccount) {
    setUsername(user.username);
    setDisplayName(user.display_name ?? "");
    setPassword("");
    setSelectedRoleIds((user.roles ?? []).map((role) => role.id));
    setEditingUserId(user.id);
    setRoleSelectOpen(false);
    setFormError("");
    setFormOpen(true);
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="SYSTEM"
        title="用户管理"
        description="维护租户成员、登录状态与角色绑定。"
        actions={
          <Button
            variant="primary"
            onClick={() => {
              resetForm();
              setFormOpen(true);
            }}
          >
            新增用户
          </Button>
        }
      />
      <ErrorBanner error={users.error} title="用户读取失败" />
      <ErrorBanner error={actionError} title="用户操作失败" />
      <DataTable
        columns={[
          { key: "username", title: "用户名", render: (row) => row.username },
          { key: "display_name", title: "显示名称", render: (row) => row.display_name ?? "-" },
          { key: "status", title: "状态", render: (row) => <StatusBadge status={row.status} /> },
          {
            key: "roles",
            title: "角色",
            render: (row) => (row.roles ?? []).map((role) => role.name).join("、") || "-",
          },
          {
            key: "actions",
            title: "操作",
            render: (row) => (
              <div className="table-actions">
                <Button onClick={() => openEdit(row)}>编辑</Button>
                <Button
                  variant={row.status === "active" ? "secondary" : "primary"}
                  disabled={toggleStatus.isPending}
                  onClick={() => toggleStatus.mutate(row)}
                >
                  {row.status === "active" ? "停用" : "启用"}
                </Button>
                <Button variant="danger" onClick={() => setDeleteTarget(row)}>
                  删除
                </Button>
              </div>
            ),
          },
        ]}
        rows={users.data?.items ?? []}
        rowKey={(row) => row.id}
        empty="暂无用户"
      />

      <Modal
        className="user-form-modal"
        title={editingUserId === null ? "新增用户" : "编辑用户"}
        open={formOpen}
        onClose={() => {
          setRoleSelectOpen(false);
          setFormOpen(false);
        }}
      >
        <form
          className="modal-form"
          onSubmit={(event) => {
            event.preventDefault();
            setFormError("");
            if (editingUserId === null) {
              create.mutate();
            } else {
              update.mutate();
            }
          }}
        >
          <ErrorBanner error={formError} title="用户保存失败" />
          <div className="form-grid user-form-grid">
            <Field label="用户名" required>
              <TextInput
                value={username}
                disabled={editingUserId !== null}
                onChange={(event) => setUsername(event.target.value)}
              />
            </Field>
            <Field label="显示名称">
              <TextInput
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
              />
            </Field>
            <div className="field-span">
              <Field label={editingUserId === null ? "初始密码" : "新密码"} required={editingUserId === null}>
                <TextInput
                  type="password"
                  value={password}
                  placeholder={
                    editingUserId === null
                      ? "至少 8 位，保存后请提醒用户修改。"
                      : "留空则不修改密码。"
                  }
                  onChange={(event) => setPassword(event.target.value)}
                />
              </Field>
            </div>
            <div className="field-span">
              <div className="field">
                <span className="field-label is-required">角色</span>
                <RoleMultiSelect
                  roles={roles.data?.items ?? []}
                  value={selectedRoleIds}
                  open={roleSelectOpen}
                  onOpenChange={setRoleSelectOpen}
                  onChange={setSelectedRoleIds}
                />
              </div>
            </div>
          </div>
          <div className="form-actions">
            <Button type="button" onClick={() => setFormOpen(false)}>
              取消
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={
                !username.trim() ||
                selectedRoleIds.length === 0 ||
                (editingUserId === null ? password.length < 8 : false) ||
                create.isPending ||
                update.isPending
              }
            >
              保存用户
            </Button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={deleteTarget !== null}
        title="删除用户"
        message={`确定删除用户 ${deleteTarget?.username ?? ""} 吗？删除后该账号不能再登录。`}
        confirmLabel="确认删除"
        pending={remove.isPending}
        onConfirm={() => {
          if (deleteTarget) remove.mutate(deleteTarget.id);
        }}
        onClose={() => setDeleteTarget(null)}
      />
    </div>
  );
}

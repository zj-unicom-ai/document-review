// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { createTenant, listTenants, updateTenant } from "../../api/endpoints";
import { Button } from "../../components/Button";
import { DataTable } from "../../components/DataTable";
import { Field, TextArea, TextInput } from "../../components/Field";
import { Modal } from "../../components/Modal";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/StatusBadge";
import { ErrorBanner } from "../../components/StateBlocks";

export function TenantsPage() {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [contact, setContact] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  const tenants = useQuery({ queryKey: ["tenants"], queryFn: () => listTenants({ pageSize: 200 }) });

  const create = useMutation({
    mutationFn: () =>
      createTenant({
        code: code.trim(),
        name: name.trim(),
        contact,
        note,
      }),
    onSuccess: async () => {
      setFormOpen(false);
      setCode("");
      setName("");
      setContact("");
      setNote("");
      setError("");
      await queryClient.invalidateQueries({ queryKey: ["tenants"] });
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : String(mutationError)),
  });

  function openForm() {
    setCode("");
    setName("");
    setContact("");
    setNote("");
    setError("");
    setFormOpen(true);
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="SYSTEM"
        title="租户管理"
        description="开通租户并维护状态。"
        actions={
          <Button variant="primary" onClick={openForm}>
            新增租户
          </Button>
        }
      />
      <ErrorBanner error={tenants.error} title="租户读取失败" />
      <DataTable
        columns={[
          { key: "code", title: "编码", render: (row) => row.code },
          { key: "name", title: "名称", render: (row) => row.name },
          { key: "status", title: "状态", render: (row) => <StatusBadge status={row.status} /> },
          {
            key: "actions",
            title: "操作",
            render: (row) =>
              row.code === "superadmin" ? (
                <Button disabled title="系统保留租户不能停用">
                  保留租户
                </Button>
              ) : (
                <Button
                  onClick={async () => {
                    await updateTenant(row.id, { status: row.status === "active" ? "inactive" : "active" });
                    await queryClient.invalidateQueries({ queryKey: ["tenants"] });
                  }}
                >
                  {row.status === "active" ? "停用" : "启用"}
                </Button>
              ),
          },
        ]}
        rows={tenants.data?.items ?? []}
        rowKey={(row) => row.id}
        empty="暂无租户"
      />

      <Modal title="新增租户" open={formOpen} onClose={() => setFormOpen(false)}>
        <form
          className="modal-form"
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate();
          }}
        >
          <ErrorBanner error={error} title="租户保存失败" />
          <div className="form-grid">
            <Field label="租户编码">
              <TextInput value={code} onChange={(event) => setCode(event.target.value)} />
            </Field>
            <Field label="租户名称">
              <TextInput value={name} onChange={(event) => setName(event.target.value)} />
            </Field>
            <Field label="联系人">
              <TextInput value={contact} onChange={(event) => setContact(event.target.value)} />
            </Field>
          </div>
          <Field label="备注">
            <TextArea
              className="text-area compact"
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
          </Field>
          <div className="form-actions">
            <Button type="button" onClick={() => setFormOpen(false)}>
              取消
            </Button>
            <Button type="submit" variant="primary" disabled={!code.trim() || !name.trim() || create.isPending}>
              保存租户
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

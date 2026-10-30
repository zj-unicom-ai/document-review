// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  createConcept,
  deleteConcept,
  listConcepts,
  updateConcept,
  type Concept,
} from "../../api/endpoints";
import { Button } from "../../components/Button";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { DataTable } from "../../components/DataTable";
import { Modal } from "../../components/Modal";
import { Field, Select, TextArea, TextInput } from "../../components/Field";
import { PageHeader } from "../../components/PageHeader";
import { ErrorBanner } from "../../components/StateBlocks";
import { dataKindLabel } from "../../i18n/zh-CN";
import { useTenant } from "../../tenant/TenantProvider";

const dataKinds = ["document", "section", "table", "field", "image_group", "item_list"];

type FormState = {
  id?: number;
  concept_code: string;
  concept_name: string;
  description: string;
  aliases: string;
  data_kind: string;
};

const emptyForm: FormState = {
  concept_code: "",
  concept_name: "",
  description: "",
  aliases: "",
  data_kind: "field",
};

export function ConceptsPage() {
  const queryClient = useQueryClient();
  const { tenantId } = useTenant();
  const [search, setSearch] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [formError, setFormError] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [pendingDelete, setPendingDelete] = useState<Concept | null>(null);

  const concepts = useQuery({
    queryKey: ["concepts", search],
    // 概念总量已超默认页大小，列表取全量避免静默截断。
    queryFn: () => listConcepts({ q: search, pageSize: 200 }),
  });

  const mutation = useMutation({
    mutationFn: async () => {
      const payload = {
        concept_code: form.concept_code.trim(),
        concept_name: form.concept_name.trim(),
        description: form.description,
        aliases: form.aliases.split(",").map((item) => item.trim()).filter(Boolean),
        data_kind: form.data_kind,
        source: "tenant_custom",
      };
      if (form.id) {
        return updateConcept(form.id, {
          concept_name: payload.concept_name,
          description: payload.description,
          aliases: payload.aliases,
          data_kind: payload.data_kind,
        });
      }
      return createConcept(payload);
    },
    onSuccess: async () => {
      setFormOpen(false);
      setForm(emptyForm);
      setFormError("");
      await queryClient.invalidateQueries({ queryKey: ["concepts"] });
    },
    onError: (error) => setFormError(error instanceof Error ? error.message : String(error)),
  });

  const columns = useMemo(
    () => [
      { key: "code", title: "编码", render: (row: Concept) => row.concept_code },
      { key: "name", title: "名称", render: (row: Concept) => row.concept_name },
      { key: "kind", title: "数据类型", render: (row: Concept) => dataKindLabel(row.data_kind) },
      { key: "aliases", title: "同义词", render: (row: Concept) => row.aliases.join("、") || "-" },
      {
        key: "actions",
        title: "操作",
        render: (row: Concept) => (
          <div className="row-actions">
            <Button
              onClick={() => {
                setForm({
                  id: row.id,
                  concept_code: row.concept_code,
                  concept_name: row.concept_name,
                  description: row.description ?? "",
                  aliases: row.aliases.join(", "),
                  data_kind: row.data_kind,
                });
                setFormOpen(true);
              }}
            >
              编辑
            </Button>
            {row.tenant_id === tenantId && row.source === "tenant_custom" ? (
              <Button
                variant="danger"
                onClick={() => setPendingDelete(row)}
              >
                删除
              </Button>
            ) : (
              <Button disabled title="平台数据只读">
                平台数据只读
              </Button>
            )}
          </div>
        ),
      },
    ],
    [tenantId],
  );

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="CONCEPTS"
        title="概念管理"
        description="概念是规则与文档结构之间的语义锚点。"
        actions={
          <>
            <TextInput
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="搜索编码 / 名称"
              aria-label="搜索概念"
            />
            <Button
              variant="primary"
              onClick={() => {
                setForm(emptyForm);
                setFormOpen(true);
              }}
            >
              新增概念
            </Button>
          </>
        }
      />
      <ErrorBanner error={concepts.error} title="概念读取失败" />
      <ErrorBanner error={deleteError} title="概念删除失败" />
      <DataTable columns={columns} rows={concepts.data?.items ?? []} rowKey={(row) => row.id} empty="暂无概念" />

      <Modal
        title={form.id ? "编辑概念" : "新增概念"}
        open={formOpen}
        onClose={() => setFormOpen(false)}
      >
        <form
          className="modal-form"
          onSubmit={(event) => {
            event.preventDefault();
            mutation.mutate();
          }}
        >
          <ErrorBanner error={formError} />
          <div className="form-grid">
            <Field label="概念编码">
              <TextInput
                value={form.concept_code}
                disabled={Boolean(form.id)}
                onChange={(event) => setForm({ ...form, concept_code: event.target.value })}
              />
            </Field>
            <Field label="概念名称">
              <TextInput
                value={form.concept_name}
                onChange={(event) => setForm({ ...form, concept_name: event.target.value })}
              />
            </Field>
            <Field label="数据类型">
              <Select value={form.data_kind} onChange={(event) => setForm({ ...form, data_kind: event.target.value })}>
                {dataKinds.map((kind) => (
                  <option key={kind} value={kind}>
                    {dataKindLabel(kind)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="同义词（逗号分隔）">
              <TextInput value={form.aliases} onChange={(event) => setForm({ ...form, aliases: event.target.value })} />
            </Field>
          </div>
          <Field label="描述">
            <TextArea
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
            />
          </Field>
          <div className="form-actions">
            <Button type="button" onClick={() => setFormOpen(false)}>
              取消
            </Button>
            <Button type="submit" variant="primary" disabled={mutation.isPending}>
              保存概念
            </Button>
          </div>
        </form>
      </Modal>
      <ConfirmDialog
        open={pendingDelete !== null}
        title="删除概念"
        message={`确定删除概念「${pendingDelete?.concept_name ?? ""}」吗？`}
        pending={false}
        onConfirm={async () => {
          if (!pendingDelete) return;
          try {
            await deleteConcept(pendingDelete.id);
            setDeleteError("");
            await queryClient.invalidateQueries({ queryKey: ["concepts"] });
          } catch (error) {
            setDeleteError(error instanceof Error ? error.message : String(error));
          } finally {
            setPendingDelete(null);
          }
        }}
        onClose={() => setPendingDelete(null)}
      />
    </div>
  );
}

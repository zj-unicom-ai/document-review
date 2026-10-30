// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  createClassification,
  deleteClassification,
  listClassifications,
  previewClassificationDelete,
  updateClassification,
  type Classification,
} from "../../api/endpoints";
import { Button } from "../../components/Button";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { DataTable } from "../../components/DataTable";
import { Modal } from "../../components/Modal";
import { Field, Select, TextArea, TextInput } from "../../components/Field";
import { PageHeader } from "../../components/PageHeader";
import { ErrorBanner } from "../../components/StateBlocks";

// 级别值只服务于表单交互，提交时换算成后端契约要求的 parent_id / level。
type ClassificationLevel = "root" | "child";

type ClassificationPreview = Awaited<ReturnType<typeof previewClassificationDelete>>;

type PendingClassificationDelete = {
  row: Classification;
  preview: ClassificationPreview | null;
  stage: "confirm" | "reconfirm";
};

function isRootClassification(row: Classification) {
  return row.parent_id === null;
}

function sortClassifications(rows: Classification[]) {
  return [...rows].sort(
    (left, right) => left.sort_order - right.sort_order || left.classify_id - right.classify_id,
  );
}

function flattenClassificationTree(rows: Classification[], expandedParentIds: ReadonlySet<number>) {
  const roots = sortClassifications(rows.filter(isRootClassification));
  const childrenByParent = new Map<number, Classification[]>();
  rows
    .filter((row): row is Classification & { parent_id: number } => row.parent_id !== null)
    .forEach((row) => {
      const children = childrenByParent.get(row.parent_id) ?? [];
      children.push(row);
      childrenByParent.set(row.parent_id, children);
    });

  // 默认折叠：只有用户明确展开的父分类才让子分类进入表格行。
  return roots.flatMap((root) => [
    { row: root, parent: null as Classification | null },
    ...(expandedParentIds.has(root.id)
      ? sortClassifications(childrenByParent.get(root.id) ?? []).map((row) => ({
          row,
          parent: root,
        }))
      : []),
  ]);
}

export function ClassificationsPage() {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [level, setLevel] = useState<ClassificationLevel>("root");
  const [parentId, setParentId] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [classifyId, setClassifyId] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [sortOrder, setSortOrder] = useState("0");
  const [saveError, setSaveError] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [pendingDelete, setPendingDelete] = useState<PendingClassificationDelete | null>(null);
  const [expandedParentIds, setExpandedParentIds] = useState<ReadonlySet<number>>(new Set());

  const classifications = useQuery({
    queryKey: ["classifications", ""],
    queryFn: () => listClassifications({ pageSize: 200 }),
  });

  const classificationRows = classifications.data?.items ?? [];
  const displayRows = flattenClassificationTree(classificationRows, expandedParentIds);
  const rootOptions = classificationRows.filter(isRootClassification);

  const mutation = useMutation({
    mutationFn: async () => {
      const base = {
        classify_id: Number(classifyId),
        parent_id: level === "child" ? Number(parentId) : null,
        name: name.trim(),
        description,
        sort_order: Number(sortOrder || 0),
      };
      if (editingId !== null) {
        return updateClassification(editingId, base);
      }
      return createClassification({
        ...base,
        level: level === "child" ? 2 : 1,
      });
    },
    onSuccess: async (saved) => {
      const savedParentId = saved.parent_id;
      if (savedParentId !== null && savedParentId !== undefined) {
        setExpandedParentIds((current) => new Set(current).add(savedParentId));
      }
      setFormOpen(false);
      setEditingId(null);
      setLevel("root");
      setParentId("");
      setClassifyId("");
      setName("");
      setDescription("");
      setSortOrder("0");
      setSaveError("");
      await queryClient.invalidateQueries({ queryKey: ["classifications"] });
    },
    onError: (error) => setSaveError(error instanceof Error ? error.message : String(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (row: Classification) => deleteClassification(row.id),
    onSuccess: async () => {
      setDeleteError("");
      await queryClient.invalidateQueries({ queryKey: ["classifications"] });
    },
    onError: (error) => setDeleteError(error instanceof Error ? error.message : String(error)),
  });

  function toggleExpanded(parentId: number) {
    setExpandedParentIds((current) => {
      const next = new Set(current);
      if (next.has(parentId)) {
        next.delete(parentId);
      } else {
        next.add(parentId);
      }
      return next;
    });
  }

  function openCreateForm() {
    setEditingId(null);
    setLevel("root");
    setParentId("");
    setClassifyId("");
    setName("");
    setDescription("");
    setSortOrder("0");
    setSaveError("");
    setFormOpen(true);
  }

  function openEditForm(row: Classification) {
    setEditingId(row.id);
    setLevel(row.parent_id === null ? "root" : "child");
    setParentId(row.parent_id === null ? "" : String(row.parent_id));
    setClassifyId(String(row.classify_id));
    setName(row.name);
    setDescription(row.description ?? "");
    setSortOrder(String(row.sort_order));
    setSaveError("");
    setFormOpen(true);
  }

  async function requestDelete(row: Classification) {
    try {
      setPendingDelete({ row, preview: null, stage: "confirm" });
      const preview = await previewClassificationDelete(row.id);
      setPendingDelete({
        row,
        preview,
        stage: "confirm",
      });
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="CLASSIFICATIONS"
        title="业务分类管理"
        description="维护规则输出的业务分类骨架。"
        actions={
          <Button variant="primary" onClick={openCreateForm}>
            新增分类
          </Button>
        }
      />
      <ErrorBanner error={classifications.error} title="分类读取失败" />
      <ErrorBanner error={deleteError} title="分类删除失败" />
      <div className="classification-table-shell">
        <DataTable
          columns={[
            {
              key: "id",
              title: "自然编号",
              align: "center",
              width: "12%",
              render: (row) => row.classify_id,
            },
            {
              key: "name",
              title: "名称",
              align: "left",
            headerClassName: "classification-name-header",
              width: "32%",
              render: (row) => {
                if (!isRootClassification(row)) {
                  return (
                    <div className="classification-name-cell">
                      <span className="classification-child-name">
                        <span>{row.name}</span>
                      </span>
                    </div>
                  );
                }
                const childCount = classificationRows.filter((item) => item.parent_id === row.id).length;
                const expanded = expandedParentIds.has(row.id);
                return (
                  <div className="classification-name-cell">
                    <span className="classification-root-name">
                      {childCount > 0 ? (
                        <Button
                          className="classification-toggle"
                          aria-label={expanded ? `收起 ${row.name} 的子分类` : `展开 ${row.name} 的子分类`}
                          onClick={() => toggleExpanded(row.id)}
                        >
                          {expanded ? "−" : "+"}
                        </Button>
                      ) : null}
                      <span>{row.name}</span>
                    </span>
                  </div>
                );
              },
            },
            {
              key: "level",
              title: "层级",
              align: "center",
              width: "18%",
              render: (row) => (isRootClassification(row) ? "根分类" : "子分类"),
            },
            {
              key: "parent",
              title: "父级分类",
              align: "center",
              width: "20%",
              render: (row) =>
                classificationRows.find((candidate) => candidate.id === row.parent_id)?.name ?? "-",
            },
            {
              key: "actions",
              title: "操作",
              align: "center",
              width: "18%",
              render: (row) =>
                <div className="row-actions">
                  <Button onClick={() => openEditForm(row)}>编辑</Button>
                  <Button variant="danger" onClick={() => void requestDelete(row)}>
                    删除
                  </Button>
                </div>
            },
          ]}
          rows={displayRows.map((item) => item.row)}
          rowKey={(row) => row.id}
          empty="暂无分类"
        />
      </div>

      <Modal title={editingId === null ? "新增分类" : "编辑分类"} open={formOpen} onClose={() => setFormOpen(false)}>
        <form
          className="modal-form"
          onSubmit={(event) => {
            event.preventDefault();
            mutation.mutate();
          }}
        >
          <ErrorBanner error={saveError} title="分类保存失败" />
          <div className="form-grid">
            <Field label="分类级别">
              <Select
                value={level}
                aria-label="分类级别"
                onChange={(event) => {
                  setLevel(event.target.value as ClassificationLevel);
                  setParentId("");
                }}
              >
                <option value="root">根级别</option>
                <option value="child">子级别</option>
              </Select>
            </Field>
            {level === "child" ? (
              <Field label="父级分类">
                <Select
                  value={parentId}
                  aria-label="父级分类"
                  onChange={(event) => setParentId(event.target.value)}
                >
                  <option value="">请选择根分类</option>
                  {rootOptions
                    .filter((row) => row.id !== editingId)
                    .map((row) => (
                    <option key={row.id} value={row.id}>
                      {row.classify_id}｜{row.name}
                    </option>
                  ))}
                </Select>
              </Field>
            ) : null}
            <Field label="分类编号">
              <TextInput
                value={classifyId}
                onChange={(event) => setClassifyId(event.target.value)}
                inputMode="numeric"
              />
            </Field>
            <Field label="分类名称">
              <TextInput value={name} onChange={(event) => setName(event.target.value)} />
            </Field>
            <Field label="排序">
              <TextInput
                value={sortOrder}
                onChange={(event) => setSortOrder(event.target.value)}
                inputMode="numeric"
              />
            </Field>
          </div>
          <Field label="描述">
            <TextArea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </Field>
          <div className="form-actions">
            <Button type="button" onClick={() => setFormOpen(false)}>
              取消
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={
                !classifyId.trim() ||
                !name.trim() ||
                (level === "child" && !parentId) ||
                mutation.isPending
              }
            >
              保存分类
            </Button>
          </div>
        </form>
      </Modal>
      <ConfirmDialog
        open={pendingDelete !== null}
        title="删除业务分类"
        message={
          pendingDelete?.preview
            ? pendingDelete.stage === "reconfirm"
              ? "请再次确认：删除后可在规则编辑页重新选择业务分类。确定删除吗？"
              : `确定删除分类「${pendingDelete.row.name}」吗？`
            : "正在读取删除影响..."
        }
        detail={
          pendingDelete?.preview
            ? [
                `将删除 ${pendingDelete.preview.classification_count} 个分类（含 ${pendingDelete.preview.child_count} 个子分类）`,
                `${pendingDelete.preview.rule_count} 条规则将解除分类关联并变为未分类`,
                "规则不会删除",
              ]
            : []
        }
        confirmLabel={pendingDelete?.stage === "reconfirm" ? "再次确认删除" : "确认删除"}
        pending={pendingDelete !== null && pendingDelete.preview === null}
        onConfirm={() => {
          if (!pendingDelete?.preview) return;
          if (pendingDelete.preview.rule_count > 0 && pendingDelete.stage === "confirm") {
            setPendingDelete({ ...pendingDelete, stage: "reconfirm" });
            return;
          }
          setDeleteError("");
          deleteMutation.mutate(pendingDelete.row, {
            onSettled: () => setPendingDelete(null),
          });
        }}
        onClose={() => setPendingDelete(null)}
      />
    </div>
  );
}

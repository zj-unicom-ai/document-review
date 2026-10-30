// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  createRuleSet,
  deleteRuleSet,
  getRuleSet,
  getRuleSetTemplateCompatibility,
  listRuleSets,
  listRules,
  replaceRuleSetItems,
  type RuleSet,
  type RuleSetItemIn,
} from "../../api/endpoints";
import { Button } from "../../components/Button";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { DataTable } from "../../components/DataTable";
import { Modal } from "../../components/Modal";
import { Field, Select, TextInput } from "../../components/Field";
import { PageHeader } from "../../components/PageHeader";
import { ErrorBanner } from "../../components/StateBlocks";
import { useTenant } from "../../tenant/TenantProvider";

type DraftItem = {
  rule_id: number;
  execution_order: string;
  enabled: boolean;
  paramsOverride: Record<string, unknown>;
};

const compatibilityStatusLabels: Record<string, string> = {
  compatible: "兼容",
  partial: "部分兼容",
  missing_binding: "存在缺失绑定",
  no_template: "无 active 模板",
};

const compatibilityActionLabels: Record<string, string> = {
  reused: "可复用",
  weak_binding: "弱绑定",
  missing_binding: "需处理",
  not_required: "非必需",
};

export function RuleSetsPage() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draftItems, setDraftItems] = useState<DraftItem[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [formError, setFormError] = useState("");
  const [pendingDelete, setPendingDelete] = useState<RuleSet | null>(null);
  const { tenantId } = useTenant();

  const rules = useQuery({ queryKey: ["rules", ""], queryFn: () => listRules({ pageSize: 200 }) });
  const ruleSets = useQuery({
    queryKey: ["rule-sets"],
    queryFn: async () => {
      // 当前列表接口不返回 items，用详情接口补齐，避免已保存规则项在刷新后丢失。
      const page = await listRuleSets({ pageSize: 100 });
      const items = await Promise.all(page.items.map((item) => getRuleSet(item.id)));
      return { ...page, items };
    },
  });
  const editing = ruleSets.data?.items.find((item) => item.id === selectedId);
  const compatibility = useQuery({
    queryKey: ["rule-sets", editing?.id ?? 0, "template-compatibility"],
    queryFn: () => getRuleSetTemplateCompatibility(editing!.id),
    enabled: editing !== undefined,
    retry: false,
  });

  useEffect(() => {
    if (!editing) {
      setDraftItems([]);
      return;
    }
    setDraftItems(
      editing.items.map((item) => ({
        rule_id: item.rule_id,
        execution_order: String(item.execution_order),
        enabled: item.enabled,
        paramsOverride: item.params_override ?? {},
      })),
    );
  }, [editing]);

  const createMutation = useMutation({
    mutationFn: () =>
      createRuleSet({
        name: newName.trim(),
        is_standard_pack: false,
        description: null,
        items: [],
      }),
    onSuccess: async () => {
      setCreateOpen(false);
      setNewName("");
      await queryClient.invalidateQueries({ queryKey: ["rule-sets"] });
    },
    onError: (error) => setFormError(error instanceof Error ? error.message : String(error)),
  });

  const saveItems = useMutation({
    mutationFn: async () => {
      const items: RuleSetItemIn[] = draftItems.map((item) => ({
        rule_id: item.rule_id,
        execution_order: Number(item.execution_order || 0),
        enabled: item.enabled,
        params_override: item.paramsOverride,
      }));
      if (!editing) {
        throw new Error("请先选择规则集");
      }
      return replaceRuleSetItems(editing.id, { items });
    },
    onSuccess: async () => {
      setFormError("");
      await queryClient.invalidateQueries({ queryKey: ["rule-sets"] });
    },
    onError: (error) => setFormError(error instanceof Error ? error.message : String(error)),
  });

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="RULE SETS"
        title="规则集管理"
        description="把规则组成可执行包，维护规则、顺序与启停。"
        actions={
          <Button
            variant="primary"
            onClick={() => {
              setNewName("");
              setFormError("");
              setCreateOpen(true);
            }}
          >
            创建规则集
          </Button>
        }
      />
      <ErrorBanner error={ruleSets.error} title="规则集读取失败" />
      <DataTable
        columns={[
          { key: "name", title: "名称", render: (row) => row.name },
          { key: "count", title: "规则数", render: (row) => row.items.length },
          {
            key: "actions",
            title: "操作",
            render: (row) => (
              <div className="row-actions">
                <Button onClick={() => setSelectedId(row.id)}>编辑</Button>
                {row.tenant_id === tenantId ? (
                  <Button
                    variant="danger"
                    onClick={() => setPendingDelete(row)}
                  >
                    删除规则集
                  </Button>
                ) : (
                  <Button disabled title="平台数据只读">
                    平台数据只读
                  </Button>
                )}
              </div>
            ),
          },
        ]}
        rows={ruleSets.data?.items ?? []}
        rowKey={(row) => row.id}
        empty="暂无规则集"
      />

      <Modal title="创建规则集" open={createOpen} onClose={() => setCreateOpen(false)}>
        <form
          className="modal-form"
          onSubmit={(event) => {
            event.preventDefault();
            createMutation.mutate();
          }}
        >
          <ErrorBanner error={formError} title="规则集保存失败" />
          <Field label="规则集名称">
            <TextInput
              value={newName}
              onChange={(event) => setNewName(event.target.value)}
              placeholder="例如：文档审查包"
            />
          </Field>
          <div className="form-actions">
            <Button type="button" onClick={() => setCreateOpen(false)}>
              取消
            </Button>
            <Button type="submit" variant="primary" disabled={!newName.trim() || createMutation.isPending}>
              保存规则集
            </Button>
          </div>
        </form>
      </Modal>
      <ConfirmDialog
        open={pendingDelete !== null}
        title="删除规则集"
        message={`确定删除规则集「${pendingDelete?.name ?? ""}」吗？`}
        onConfirm={async () => {
          if (!pendingDelete) return;
          try {
            await deleteRuleSet(pendingDelete.id);
            if (selectedId === pendingDelete.id) setSelectedId(null);
            await queryClient.invalidateQueries({ queryKey: ["rule-sets"] });
          } catch (error) {
            setFormError(error instanceof Error ? error.message : String(error));
          } finally {
            setPendingDelete(null);
          }
        }}
        onClose={() => setPendingDelete(null)}
      />

      <Modal
        title={`编辑规则集：${editing?.name ?? ""}`}
        open={editing !== undefined}
        onClose={() => setSelectedId(null)}
      >
        <div className="modal-form">
          <ErrorBanner error={formError} title="规则项保存失败" />
          {draftItems.map((item, index) => (
            <div className="rule-set-item" key={`${item.rule_id}-${index}`}>
              <Field label="规则">
                <Select
                  value={item.rule_id}
                  onChange={(event) => {
                    const next = [...draftItems];
                    next[index] = { ...item, rule_id: Number(event.target.value) };
                    setDraftItems(next);
                  }}
                >
                  {(rules.data?.items ?? []).map((rule) => (
                    <option key={rule.id} value={rule.id}>
                      {rule.rule_code}｜{rule.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="执行顺序">
                <TextInput
                  value={item.execution_order}
                  onChange={(event) => {
                    const next = [...draftItems];
                    next[index] = { ...item, execution_order: event.target.value };
                    setDraftItems(next);
                  }}
                />
              </Field>
              <button
                type="button"
                className="switch"
                role="switch"
                aria-checked={item.enabled}
                onClick={() => {
                  const next = [...draftItems];
                  next[index] = { ...item, enabled: !item.enabled };
                  setDraftItems(next);
                }}
              >
                <span className="switch-track" aria-hidden="true">
                  <span className="switch-thumb" />
                </span>
                <span>启用</span>
              </button>
              <Button
                type="button"
                variant="danger"
                onClick={() => setDraftItems(draftItems.filter((_, currentIndex) => currentIndex !== index))}
              >
                移除规则
              </Button>
            </div>
          ))}
          <div className="form-actions">
            <Button
              type="button"
              onClick={() => {
                const firstRule = rules.data?.items[0];
                if (firstRule) {
                  setDraftItems([
                    ...draftItems,
                    {
                      rule_id: firstRule.id,
                      execution_order: String(draftItems.length + 1),
                      enabled: true,
                      paramsOverride: {},
                    },
                  ]);
                }
              }}
            >
              添加规则
            </Button>
            <Button
              type="button"
              variant="primary"
              onClick={() => saveItems.mutate()}
              disabled={saveItems.isPending}
            >
              保存规则项
            </Button>
          </div>
          <section className="trial-result" aria-label="模板兼容性评估">
            <h4>模板兼容性评估</h4>
            <ErrorBanner
              error={compatibility.error}
              title="模板兼容性读取失败"
            />
            {(compatibility.data ?? []).map((report) => (
              <article key={report.template_id ?? "no-template"}>
                <strong>{report.template_name ?? "无 active 模板"}</strong>
                <span>
                  {compatibilityStatusLabels[report.status] ?? report.status} · 稳定绑定{" "}
                  {report.exact_count} · 弱绑定 {report.weak_count} · 缺失{" "}
                  {report.missing_count}
                </span>
                <ul>
                  {report.rules.map((rule) => (
                    <li key={`${report.template_id ?? "no-template"}-${rule.rule_id}`}>
                      <strong>{rule.rule_name}</strong>
                      <span>
                        {compatibilityActionLabels[rule.action] ?? rule.action} · 概念{" "}
                        {rule.concept_code || "-"}
                      </span>
                      <span>{rule.message}</span>
                    </li>
                  ))}
                </ul>
              </article>
            ))}
          </section>
        </div>
      </Modal>
    </div>
  );
}

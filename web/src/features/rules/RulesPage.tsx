// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  deleteRule,
  disableRule,
  enableRule,
  listClassifications,
  listConcepts,
  listOperators,
  listRules,
  type Rule,
} from "../../api/endpoints";
import { ruleTypeLabel } from "../../i18n/zh-CN";
import { Button } from "../../components/Button";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { DataTable } from "../../components/DataTable";
import { TextInput } from "../../components/Field";
import { PageHeader } from "../../components/PageHeader";
import { EmptyState, ErrorBanner } from "../../components/StateBlocks";
import { capabilityNamesForRule, conceptForRule } from "./capabilities";
import { RuleEditor } from "./RuleEditor";
import { useTenant } from "../../tenant/TenantProvider";

/** 中文 / 英文统一按字符数截断，完整内容仍通过 title 提示保留。 */
function truncateText(value: string, max = 10) {
  return value.length > max ? `${value.slice(0, max)}...` : value;
}

export function RulesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [editingRule, setEditingRule] = useState<Rule | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [pendingDelete, setPendingDelete] = useState<Rule | null>(null);
  const { tenantId } = useTenant();

  // 概念总量已超默认页大小（共享库 24 条），下拉必须取全量，避免静默截断。
  const concepts = useQuery({
    queryKey: ["concepts", ""],
    queryFn: () => listConcepts({ pageSize: 200 }),
  });
  const classifications = useQuery({
    queryKey: ["classifications", ""],
    // 分类用于两节下拉与回填，取全量避免分页截断（对齐 BL-054 口径）。
    queryFn: () => listClassifications({ pageSize: 200 }),
  });
  const operators = useQuery({
    queryKey: ["operators", "rule-authoring"],
    queryFn: () => listOperators({ pageSize: 200 }),
  });
  const rules = useQuery({
    queryKey: ["rules", search],
    queryFn: () => listRules({ q: search }),
  });

  const columns = useMemo(
    () => [
      { key: "code", title: "规则代码", render: (row: Rule) => row.rule_code },
      { key: "name", title: "名称", render: (row: Rule) => {
        const value = row.name;
        return <span className="text-truncate" title={value}>{truncateText(value)}</span>;
      } },
      {
        key: "object",
        title: "检查对象",
        render: (row: Rule) => {
          const value =
            conceptForRule(row, concepts.data?.items ?? [])?.concept_name ?? "未知检查对象";
          return <span className="text-truncate" title={value}>{truncateText(value)}</span>;
        },
      },
      {
        key: "capability",
        title: "检查能力",
        render: (row: Rule) => {
          const names = capabilityNamesForRule(row, operators.data?.items ?? []);
          return names.join("、") || "未知检查能力";
        },
      },
      { key: "type", title: "类型", render: (row: Rule) => ruleTypeLabel(row.rule_type) },
      { key: "severity", title: "级别", render: (row: Rule) => row.severity_default },
      { key: "status", title: "状态", render: (row: Rule) => (row.enabled ? "启用" : "停用") },
      {
        key: "actions",
        title: "操作",
        render: (row: Rule) => (
          <div className="row-actions">
            <Button
              onClick={() => {
                setEditingRule(row);
                setEditorOpen(true);
              }}
            >
              编辑
            </Button>
            <Button
              onClick={async () => {
                if (row.enabled) {
                  await disableRule(row.id);
                } else {
                  await enableRule(row.id);
                }
                await queryClient.invalidateQueries({ queryKey: ["rules"] });
              }}
            >
              {row.enabled ? "停用" : "启用"}
            </Button>
            {row.tenant_id === tenantId ? (
              <Button
                variant="danger"
                onClick={() => setPendingDelete(row)}
              >
                删除
              </Button>
            ) : null}
          </div>
        ),
      },
    ],
    [concepts.data?.items, operators.data?.items, queryClient, tenantId],
  );

  async function refreshAfterSave() {
    setEditingRule(null);
    setEditorOpen(false);
    await queryClient.invalidateQueries({ queryKey: ["rules"] });
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="RULES"
        title="规则配置"
        description="按检查对象和业务目标配置规则，系统自动生成执行定义。"
        actions={
          <>
            <TextInput
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="搜索规则"
              aria-label="搜索规则"
            />
            <Button
              variant="primary"
              onClick={() => {
                setEditingRule(null);
                setEditorOpen(true);
              }}
            >
              新增规则
            </Button>
          </>
        }
      />
      <ErrorBanner error={rules.error} title="规则读取失败" />
      <ErrorBanner error={deleteError} title="规则删除失败" />
      <ErrorBanner error={operators.error} title="检查能力读取失败" />
      <DataTable columns={columns} rows={rules.data?.items ?? []} rowKey={(row) => row.id} empty="暂无规则" />

      <RuleEditor
        key={editingRule?.id ?? "new"}
        open={editingRule !== null || editorOpen}
        concepts={concepts.data?.items ?? []}
        operators={operators.data?.items ?? []}
        classifications={classifications.data?.items ?? []}
        initialRule={editingRule}
        onCancel={() => {
          setEditingRule(null);
          setEditorOpen(false);
        }}
        onSaved={refreshAfterSave}
      />

      <ConfirmDialog
        open={pendingDelete !== null}
        title="删除规则"
        message={`确定删除规则「${pendingDelete?.name ?? ""}」吗？`}
        onConfirm={async () => {
          if (!pendingDelete) return;
          try {
            await deleteRule(pendingDelete.id);
            setDeleteError("");
            await queryClient.invalidateQueries({ queryKey: ["rules"] });
          } catch (error) {
            setDeleteError(error instanceof Error ? error.message : String(error));
          } finally {
            setPendingDelete(null);
          }
        }}
        onClose={() => setPendingDelete(null)}
      />

      {!editingRule && !editorOpen && (rules.data?.items.length ?? 0) === 0 ? (
        <EmptyState
          title="从业务目标开始建立规则"
          description="选择检查对象和检查目标，系统会自动匹配可用检查能力并生成 DSL。"
        />
      ) : null}
    </div>
  );
}

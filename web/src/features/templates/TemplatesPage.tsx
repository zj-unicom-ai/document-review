// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import {
  createTemplateFromProfile,
  deleteTemplate,
  listConcepts,
  listRuleSets,
  listRules,
  listTemplates,
  trialTemplate,
  type Concept,
  type DocumentTemplate,
  type Rule,
  type TemplateTrialResult,
} from "../../api/endpoints";
import { Button } from "../../components/Button";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { DataTable } from "../../components/DataTable";
import { Field, Select, TextInput } from "../../components/Field";
import { Modal } from "../../components/Modal";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/StatusBadge";
import { ErrorBanner } from "../../components/StateBlocks";
import { dataKindLabel } from "../../i18n/zh-CN";

function canCreateFromSample(result: TemplateTrialResult) {
  const hasConditions = (result.suggested_detect_conditions ?? []).length > 0;
  const hasBinding = (result.bindings ?? []).some((binding) => {
    const targets = binding.targets;
    return String(binding.status ?? "") === "bound" && Array.isArray(targets) && targets.length > 0;
  });
  return hasConditions && hasBinding;
}

type ConceptBinding = NonNullable<DocumentTemplate["concept_bindings"]>[number];

function describeCondition(condition: Record<string, unknown>) {
  const type = String(condition.type ?? "");
  if (type === "section_title_regex") {
    return `章节标题匹配：${String(condition.pattern ?? "")}`;
  }
  if (type === "md_contains") {
    return `全文包含关键词：${String(condition.keyword ?? "")}`;
  }
  if (type === "table_field_contains") {
    return `表格字段匹配：${String(condition.field ?? "")}`;
  }
  return `识别条件类型：${type || "未知"}`;
}

function bindingStatusLabel(status: unknown) {
  const value = String(status ?? "");
  if (value === "bound") return "已绑定";
  if (value === "not_found") return "未找到";
  if (value === "ambiguous") return "位置不确定";
  return value || "未知";
}

function targetKindLabel(kind: unknown) {
  const value = String(kind ?? "");
  return dataKindLabel(value) || "未知";
}

function formatLocatorValue(value: unknown) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).join("、");
  }
  return String(value ?? "");
}

function describeLocator(target: Record<string, unknown>): string[] {
  const record = (target.locator ?? {}) as Record<string, unknown>;
  const labels: Record<string, string> = {
    section_title_regex: "章节标题",
    anchor_keywords: "表格关键词",
    field_aliases: "字段别名",
    image_keywords: "图片关键词",
    after_section: "后置章节",
    stop_keywords: "截止关键词",
  };
  const preciseParts = Object.entries(record)
    .filter(([key, value]) => labels[key] && formatLocatorValue(value).trim())
    .map(([key, value]) => `${labels[key]}=${formatLocatorValue(value)}`);
  if (!preciseParts.length) {
    return ["定位方式：页级定位", "精确条件：未识别到章节标题 / 表格关键词"];
  }
  const parts = Object.entries(record)
    .filter(([key]) => labels[key])
    .map(([key, value]) => `${labels[key]}=${formatLocatorValue(value)}`);
  return [`定位条件：${parts.join("；")}`];
}

function describeTarget(target: Record<string, unknown>) {
  const page =
    target.page_idx !== undefined && target.page_idx !== null
      ? `第 ${Number(target.page_idx) + 1} 页${String(target.kind ?? "") === "section" ? "章节内容" : "内容"}`
      : target.page_idx_hint !== undefined && target.page_idx_hint !== null
        ? `第 ${Number(target.page_idx_hint) + 1} 页提示`
        : "页码未定位";
  const confidenceValue = Number(target.confidence ?? 0);
  const confidence = Number.isFinite(confidenceValue) ? Math.round(confidenceValue * 100) : 0;
  return `${targetKindLabel(target.kind)} · ${page} · 置信度 ${confidence}%`;
}

function confirmedByLabel(value: unknown) {
  const source = String(value ?? "");
  const labels: Record<string, string> = {
    template: "模板",
    llm: "LLM",
    human: "人工",
  };
  return labels[source] ?? (source || "未知");
}

function formatDateTime(value: string) {
  return value ? value.replace("T", " ").slice(0, 19) : "-";
}

function conceptTitle(conceptCode: string, concepts: Concept[]) {
  const concept = concepts.find((item) => item.concept_code === conceptCode);
  return concept
    ? `${concept.concept_name}（编码：${conceptCode}）`
    : `未知概念（编码：${conceptCode}）`;
}

function referencedRulesLabel(conceptCode: string, rules: Rule[]) {
  const names = rules
    .filter((rule) => {
      if (!rule.enabled) return false;
      const anchor = rule.definition?.anchor;
      return Boolean(anchor && typeof anchor === "object" && "concept" in anchor);
    })
    .filter((rule) => String((rule.definition?.anchor as Record<string, unknown>).concept ?? "") === conceptCode)
    .map((rule) => rule.name);
  return names.length
    ? `引用该位置的规则：${names.join("、")}`
    : "当前启用的规则未引用该位置";
}

export function TemplatesPage() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [sampleFile, setSampleFile] = useState<File | null>(null);
  const [ruleSetId, setRuleSetId] = useState("");
  const [templateName, setTemplateName] = useState("");
  const [trialResult, setTrialResult] = useState<TemplateTrialResult | null>(null);
  const [trialError, setTrialError] = useState("");
  const [createError, setCreateError] = useState("");
  const [success, setSuccess] = useState("");
  const [detailTemplate, setDetailTemplate] = useState<DocumentTemplate | null>(null);
  const [pendingDelete, setPendingDelete] = useState<DocumentTemplate | null>(null);
  const [deleteError, setDeleteError] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const templates = useQuery({ queryKey: ["templates"], queryFn: () => listTemplates({ pageSize: 100 }) });
  const ruleSets = useQuery({
    queryKey: ["rule-sets", "template-create"],
    queryFn: () => listRuleSets({ pageSize: 100 }),
  });
  const concepts = useQuery({
    queryKey: ["concepts", "template-detail"],
    queryFn: () => listConcepts({ pageSize: 200 }),
    enabled: detailTemplate !== null,
  });
  const rules = useQuery({
    queryKey: ["rules", "template-detail"],
    queryFn: () => listRules({ pageSize: 200 }),
    enabled: detailTemplate !== null,
  });

  const trial = useMutation({
    mutationFn: () =>
      trialTemplate(sampleFile as File, Number(ruleSetId)),
    onMutate: () => clearTrialResult(),
    onSuccess: (result) => {
      setTrialResult(result);
      setTrialError("");
    },
    onError: (mutationError) => {
      setTrialError(mutationError instanceof Error ? mutationError.message : String(mutationError));
    },
  });

  const createFromProfile = useMutation({
    mutationFn: () => {
      if (!trialResult) {
        throw new Error("请先完成样例试跑");
      }
      return createTemplateFromProfile(trialResult.profile_id, {
        name: templateName.trim(),
        description: null,
        detect_conditions: trialResult.suggested_detect_conditions ?? [],
      });
    },
    onSuccess: async () => {
      closeCreateModal();
      setSuccess("模板生成成功，已启用。");
      await queryClient.invalidateQueries({ queryKey: ["templates"] });
    },
    onError: (mutationError) => {
      setCreateError(mutationError instanceof Error ? mutationError.message : String(mutationError));
    },
  });

  const deleteTemplateMutation = useMutation({
    mutationFn: (row: DocumentTemplate) => deleteTemplate(row.id),
    onSuccess: async (_, row) => {
      setPendingDelete(null);
      setDeleteError("");
      setSuccess(`模板「${row.name}」已删除。`);
      await queryClient.invalidateQueries({ queryKey: ["templates"] });
    },
    onError: (mutationError) => {
      setDeleteError(mutationError instanceof Error ? mutationError.message : String(mutationError));
    },
  });

  function clearTrialResult() {
    setTrialResult(null);
    setTrialError("");
    setTemplateName("");
    setCreateError("");
  }

  function closeCreateModal() {
    setCreateOpen(false);
    setSampleFile(null);
    setRuleSetId("");
    clearTrialResult();
    setSuccess("");
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  const readyToCreate = trialResult !== null && canCreateFromSample(trialResult);

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="SYSTEM"
        title="模板管理"
        description="上传标准样例，系统自动生成模板识别条件与概念绑定。"
        actions={
          <Button variant="primary" onClick={() => setCreateOpen(true)}>
            新建模板
          </Button>
        }
      />
      <ErrorBanner error={templates.error} title="模板读取失败" />
      <ErrorBanner error={ruleSets.error} title="规则集读取失败" />
      <ErrorBanner error={deleteError} title="模板删除失败" />
      <DataTable
        columns={[
          { key: "name", title: "名称", render: (row) => row.name },
          { key: "status", title: "状态", render: (row) => <StatusBadge status={row.status} /> },
          { key: "bindings", title: "绑定数", render: (row) => (row.concept_bindings ?? []).length },
          {
            key: "actions",
            title: "操作",
            render: (row) => (
              <div className="row-actions">
                <Button type="button" onClick={() => setDetailTemplate(row)}>
                  详情
                </Button>
                <Button type="button" variant="danger" onClick={() => setPendingDelete(row)}>
                  删除
                </Button>
              </div>
            ),
          },
        ]}
        rows={templates.data?.items ?? []}
        rowKey={(row) => row.id}
        empty="暂无模板"
      />
      {success ? <p className="capability-note">{success}</p> : null}

      <Modal title="新建模板" open={createOpen} onClose={closeCreateModal}>
        <form
          className="modal-form"
          onSubmit={(event) => {
            event.preventDefault();
            createFromProfile.mutate();
          }}
        >
          <div className="form-grid">
            <Field label="模板文件">
              <input
                className="file-input"
                type="file"
                accept=".pdf,application/pdf"
                aria-label="模板文件"
                ref={fileInputRef}
                onChange={(event) => {
                  setSampleFile(event.target.files?.[0] ?? null);
                  clearTrialResult();
                }}
              />
            </Field>
            <Field label="规则集">
              <Select
                value={ruleSetId}
                onChange={(event) => {
                  setRuleSetId(event.target.value);
                  clearTrialResult();
                }}
              >
                <option value="">请选择规则集</option>
                {(ruleSets.data?.items ?? []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <div className="form-actions">
            <Button
              type="button"
              variant="primary"
              disabled={!sampleFile || !ruleSetId || trial.isPending}
              onClick={() => trial.mutate()}
            >
              {trial.isPending ? "创建中..." : "模板创建"}
            </Button>
          </div>
          <p className="capability-note">模板文件仅用于画像生成，不正式审查</p>
          <ErrorBanner error={trialError} title="样例试跑失败" />

          {trialResult ? (
            <section className="trial-result" aria-label="模板试跑结果">
              <header>
                <strong>{trialResult.doc_summary || "画像生成完成"}</strong>
                <span>{trialResult.discovery_method}</span>
              </header>
              <p>{trialResult.rule_set_selection_reason}</p>
              <h4>系统自动绑定</h4>
              <ul>
                {(trialResult.bindings ?? []).map((binding, index) => (
                  <li key={`${String(binding.concept_code ?? "")}-${index}`}>
                    <strong>{String(binding.concept_code ?? "")}</strong>
                    <span>
                      {String(binding.status ?? "unknown")} ·{" "}
                      {Array.isArray(binding.targets) ? binding.targets.length : 0} 个目标
                    </span>
                  </li>
                ))}
              </ul>
              <h4>规则命中预览</h4>
              {(trialResult.rule_preview ?? []).length ? (
                <ul>
                  {(trialResult.rule_preview ?? []).map((item) => (
                    <li key={`${item.rule_id}-${item.rule_code}`}>
                      <strong>{item.rule_name}</strong>
                      <span>
                        {item.status} · {(item.violations ?? []).length} 条违规
                      </span>
                      {(item.violations ?? []).map((violation) => (
                        <p key={`${violation.rule_id}-${violation.title}`}>{violation.title}</p>
                      ))}
                    </li>
                  ))}
                </ul>
              ) : (
                <p>未执行规则预览。</p>
              )}
            </section>
          ) : null}

          {trialResult && !readyToCreate ? (
            <p className="capability-note">
              当前样例结构不足以生成模板，请更换一份更完整的标准样例。
            </p>
          ) : null}
          {readyToCreate ? (
            <div className="form-grid">
              <Field label="模板名称">
                <TextInput
                  value={templateName}
                  onChange={(event) => setTemplateName(event.target.value)}
                  placeholder="例如：通用报告模板"
                />
              </Field>
              <div className="form-actions">
                <Button type="submit" variant="primary" disabled={!templateName.trim() || createFromProfile.isPending}>
                  生成并启用模板
                </Button>
              </div>
            </div>
          ) : null}
          <ErrorBanner error={createError} title="模板生成失败" />
        </form>
      </Modal>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="删除模板"
        message={`确定删除模板「${pendingDelete?.name ?? ""}」吗？`}
        detail={["删除后审查将不再自动命中该模板识别条件与概念绑定。"]}
        pending={deleteTemplateMutation.isPending}
        onConfirm={() => pendingDelete && deleteTemplateMutation.mutate(pendingDelete)}
        onClose={() => setPendingDelete(null)}
      />

      <Modal
        title={`模板详情：${detailTemplate?.name ?? ""}`}
        open={detailTemplate !== null}
        onClose={() => setDetailTemplate(null)}
      >
        {detailTemplate ? (
          <div className="modal-form">
            <section className="template-detail-overview" aria-label="模板基础信息">
              <div>
                <small>状态</small>
                <StatusBadge status={detailTemplate.status} />
              </div>
              <div>
                <small>来源画像</small>
                <strong>{detailTemplate.source_profile_id ?? "-"}</strong>
              </div>
              <div>
                <small>创建时间</small>
                <strong>{formatDateTime(detailTemplate.created_at)}</strong>
              </div>
              <div>
                <small>更新时间</small>
                <strong>{formatDateTime(detailTemplate.updated_at)}</strong>
              </div>
            </section>

            <section className="trial-result" aria-label="模板识别条件">
              <h4>模板识别条件</h4>
              {(detailTemplate.detect_conditions ?? []).length ? (
                <ul>
                  {(detailTemplate.detect_conditions ?? []).map((condition, index) => (
                    <li key={`${String(condition.type ?? "")}-${index}`}>
                      <span>{describeCondition(condition)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>暂无识别条件</p>
              )}
            </section>

            <section className="trial-result" aria-label="画像绑定详情">
              <p className="capability-note">
                这里展示的是模板的概念位置绑定，不是规则集绑定。规则集里的规则通过概念编码引用这些位置。
              </p>
              <h4>概念位置绑定</h4>
              {(detailTemplate.concept_bindings ?? []).length ? (
                <ul>
                  {(detailTemplate.concept_bindings ?? []).map(
                    (binding: ConceptBinding, bindingIndex: number) => {
                      const targets = Array.isArray(binding.targets) ? binding.targets : [];
                      const conceptCode = String(binding.concept_code ?? "");
                      return (
                        <li key={`${conceptCode}-${bindingIndex}`}>
                          <strong>{conceptTitle(conceptCode, concepts.data?.items ?? [])}</strong>
                          <span>
                            {bindingStatusLabel(binding.status)} · {targets.length} 个目标
                          </span>
                          <span>
                            {referencedRulesLabel(conceptCode, rules.data?.items ?? [])}
                          </span>
                          <ul>
                            {targets.map((target, targetIndex) => (
                              <li key={`${String(target.kind ?? "")}-${targetIndex}`}>
                                <span>{describeTarget(target)}</span>
                                {describeLocator(target).map((text) => (
                                  <span key={text}>{text}</span>
                                ))}
                                <span>确认来源：{confirmedByLabel(target.confirmed_by)}</span>
                              </li>
                            ))}
                          </ul>
                        </li>
                      );
                    },
                  )}
                </ul>
              ) : (
                <p>暂无概念绑定</p>
              )}
            </section>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}

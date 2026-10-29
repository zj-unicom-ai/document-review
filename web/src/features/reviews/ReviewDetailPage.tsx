// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  downloadAnnotatedPdf,
  getReview,
  getReviewPlan,
  listClassifications,
  type Classification,
} from "../../api/endpoints";
import { Button } from "../../components/Button";
import { PdfPreview } from "../../components/PdfPreview";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/StatusBadge";
import { ErrorBanner } from "../../components/StateBlocks";
import { isTerminalReviewStatus, reviewStatusLabel } from "./reviewStatus";

type DetailTab = "violations" | "preview";

type ReviewViolation = {
  rule_id: string;
  classify_id: number;
  title: string;
  severity: string;
  content: string;
  page_idx: number;
};

type CategoryNode = {
  /** 规则分类表主键 id；violation.classify_id 外键指向该 id。 */
  classifyId: number | null;
  name: string;
  children: CategoryNode[];
};

function sortClassifications(rows: Classification[]) {
  return [...rows].sort(
    (left, right) => left.sort_order - right.sort_order || left.classify_id - right.classify_id,
  );
}

function buildCategoryTree(
  rows: Classification[],
  violations: ReviewViolation[],
): CategoryNode[] {
  const rootRows = rows.filter((row) => row.parent_id === null);
  const childRows = rows.filter((row) => row.parent_id !== null);
  const roots: CategoryNode[] = sortClassifications(rootRows).map((row) => ({
    classifyId: row.id,
    name: row.name,
    children: [],
  }));
  const rootById = new Map(
    rootRows.map(
      (row) => [row.id, roots.find((node) => node.classifyId === row.id)] as const,
    ),
  );

  for (const row of sortClassifications(childRows)) {
    const parentId = row.parent_id;
    if (parentId === null || parentId === undefined) continue;
    rootById.get(parentId)?.children.push({
      classifyId: row.id,
      name: row.name,
      children: [],
    });
  }

  const knownClassifyIds = new Set(rows.map((row) => row.id));
  const uncategorized = violations.filter(
    (violation) => !knownClassifyIds.has(violation.classify_id),
  );
  if (uncategorized.length) {
    roots.push({ classifyId: null, name: "未分类", children: [] });
  }
  return roots;
}

function collectCategoryViolations(node: CategoryNode, violations: ReviewViolation[]) {
  const classifyIds = new Set<number | null>([node.classifyId]);
  for (const child of node.children) {
    for (const id of collectCategoryClassifyIds(child)) classifyIds.add(id);
  }
  return violations.filter((violation) => classifyIds.has(violation.classify_id));
}

function collectCategoryClassifyIds(node: CategoryNode): Array<number | null> {
  return [node.classifyId, ...node.children.flatMap((child) => collectCategoryClassifyIds(child))];
}

function findCategoryNode(
  nodes: CategoryNode[],
  classifyId: number | null,
): CategoryNode | null {
  for (const node of nodes) {
    if (node.classifyId === classifyId) return node;
    const child = findCategoryNode(node.children, classifyId);
    if (child) return child;
  }
  return null;
}

function StatusIcon({ failed }: { failed: boolean }) {
  return (
    <span className={`status-icon ${failed ? "status-failed" : "status-passed"}`} aria-hidden="true">
      {failed ? "×" : "✓"}
    </span>
  );
}

export function ReviewDetailPage() {
  const params = useParams();
  const reviewId = Number(params.reviewId);
  const [tab, setTab] = useState<DetailTab>("violations");
  const [selectedClassifyId, setSelectedClassifyId] = useState<number | null>(null);
  const [expandedRootIds, setExpandedRootIds] = useState<ReadonlySet<number>>(new Set());

  const review = useQuery({
    queryKey: ["reviews", reviewId],
    queryFn: () => getReview(reviewId),
    refetchInterval: (query) => (isTerminalReviewStatus(query.state.data?.status ?? "") ? false : 1800),
  });

  const plan = useQuery({
    queryKey: ["reviews", reviewId, "plan"],
    queryFn: () => getReviewPlan(reviewId),
    enabled: Number.isFinite(reviewId) && reviewId > 0,
  });

  const classifications = useQuery({
    queryKey: ["classifications", ""],
    queryFn: () => listClassifications({ pageSize: 200 }),
  });

  const preview = useMutation({
    // pdf.js 直接消费 Blob，不再经浏览器内置查看器
    mutationFn: () => downloadAnnotatedPdf(reviewId),
  });

  function switchTab(next: DetailTab) {
    setTab(next);
    // 切到预览时自动加载批注 PDF，省一次点击
    if (next === "preview" && !preview.data && !preview.isPending) {
      preview.mutate();
    }
  }

  const run = review.data;
  const violations = run?.violations ?? [];
  const categoryTree = useMemo(
    () => {
      return buildCategoryTree(classifications.data?.items ?? [], violations);
    },
    [classifications.data?.items, violations],
  );
  const selectedCategory =
    selectedClassifyId === null
      ? (categoryTree[0] ?? null)
      : findCategoryNode(categoryTree, selectedClassifyId);
  const selectedViolations = selectedCategory
    ? collectCategoryViolations(selectedCategory, violations)
    : [];
  const selectedFailed = selectedViolations.length > 0;

  return (
    <div className="page-stack review-detail">
      <PageHeader
        title={run?.file_name ?? `审查 ${reviewId}`}
        actions={
          <>
            <div className="header-stats">
              <span className="header-stat">
                <small>结果</small>
                <strong className={run?.result === "fail" ? "stat-danger" : ""}>
                  {run?.result ? reviewStatusLabel(run.result) : "-"}
                </strong>
              </span>
              <span className="header-stat">
                <small>违规</small>
                <strong className={(run?.violations?.length ?? 0) > 0 ? "stat-danger" : ""}>
                  {run?.violations?.length ?? 0}
                </strong>
              </span>
              <span className="header-stat">
                <small>规则</small>
                <strong>{plan.data?.items.length ?? run?.rule_plan?.length ?? 0}</strong>
              </span>
            </div>
            {run ? (
              <StatusBadge status={run.status} label={reviewStatusLabel(run.status)} />
            ) : null}
            <Button
              variant="primary"
              disabled={!run?.annotated_pdf_path || preview.isPending}
              onClick={() => {
                if (!preview.data) preview.mutate();
                switchTab("preview");
              }}
            >
              下载批注 PDF
            </Button>
          </>
        }
      />
      <ErrorBanner error={review.error} title="审查读取失败" />
      <ErrorBanner error={run?.error} title="审查失败" />
      <ErrorBanner error={classifications.error} title="规则分类读取失败；已按执行计划兜底展示" />
      <div className="tab-bar" role="tablist" aria-label="审查内容">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "violations"}
          className={`tab-button ${tab === "violations" ? "active" : ""}`}
          onClick={() => switchTab("violations")}
        >
          违规项详情
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "preview"}
          className={`tab-button ${tab === "preview" ? "active" : ""}`}
          onClick={() => switchTab("preview")}
        >
          预览批注PDF
        </button>
      </div>

      {tab === "violations" ? (
        <section className="panel violation-workspace" aria-label="违规分类与详情">
          <aside className="classification-panel" aria-label="审核规则分类">
            <h3>审核规则</h3>
            <ErrorBanner error={classifications.error} title="规则分类读取失败" />
            {classifications.isPending && categoryTree.length === 0 ? (
              <p className="category-empty">规则分类加载中...</p>
            ) : categoryTree.length === 0 ? (
              <p className="category-empty">暂无业务分类</p>
            ) : (
              <ul className="category-tree">
                {categoryTree.map((root) => {
                  const expanded = expandedRootIds.has(root.classifyId ?? -1);
                  return (
                    <li key={root.classifyId ?? root.name}>
                      <div className="category-root">
                        <button
                          type="button"
                          className={
                            selectedCategory?.classifyId === root.classifyId
                              ? "category-root-name active"
                              : "category-root-name"
                          }
                          onClick={() => setSelectedClassifyId(root.classifyId)}
                        >
                          {root.name}
                        </button>
                        {root.children.length ? (
                          <button
                            type="button"
                            className={`category-caret ${expanded ? "expanded" : ""}`}
                            aria-expanded={expanded}
                            aria-label={expanded ? `收起 ${root.name}` : `展开 ${root.name}`}
                            onClick={() =>
                              setExpandedRootIds((current) => {
                                const key = root.classifyId ?? -1;
                                const next = new Set(current);
                                if (next.has(key)) next.delete(key);
                                else next.add(key);
                                return next;
                              })
                            }
                          >
                            <span className="nav-caret" aria-hidden="true" />
                          </button>
                        ) : null}
                      </div>
                      {expanded ? (
                        <ul>
                          {root.children.map((child) => {
                            const failed =
                              collectCategoryViolations(child, violations).length > 0;
                            return (
                              <li key={child.classifyId ?? child.name}>
                                <button
                                  type="button"
                                  className={
                                    selectedCategory?.classifyId === child.classifyId
                                      ? "category-child-name active"
                                      : "category-child-name"
                                  }
                                  onClick={() => setSelectedClassifyId(child.classifyId)}
                                >
                                  <StatusIcon failed={failed} />
                                  <span>{child.name}</span>
                                </button>
                              </li>
                            );
                          })}
                        </ul>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            )}
          </aside>

          <div className="violation-detail-panel" aria-label="审核解释">
            {selectedCategory ? (
              <>
                <header className="violation-detail-header">
                  <h3>{selectedCategory.name}</h3>
                  <p className={selectedFailed ? "result-danger" : "result-passed"}>
                    <StatusIcon failed={selectedFailed} />
                    {selectedFailed ? "审核不合格" : "审核合格"}
                  </p>
                </header>
                <div className="violation-detail-scroll">
                  {selectedViolations.length ? (
                    <div className="violation-list">
                      {selectedViolations.map((violation, index) => (
                        <article
                          key={`${violation.rule_id}-${index}`}
                          className="violation-card"
                        >
                          <header>
                            <strong>{violation.title}</strong>
                            <span>{violation.rule_id}</span>
                          </header>
                          <p>{violation.content}</p>
                          <dl>
                            <div>
                              <dt>页码</dt>
                              <dd>{violation.page_idx + 1}</dd>
                            </div>
                            <div>
                              <dt>级别</dt>
                              <dd>{violation.severity}</dd>
                            </div>
                          </dl>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p className="category-empty">该分类未发现问题。</p>
                  )}
                </div>
              </>
            ) : (
              <p>
                {classifications.isPending
                  ? "规则分类加载中..."
                  : classifications.error
                    ? "规则分类读取失败，请重试"
                    : "暂无业务分类"}
              </p>
            )}
          </div>
        </section>
      ) : (
        <section className="panel pdf-panel">
          {!run?.annotated_pdf_path ? (
            <p>该审查尚未生成批注 PDF</p>
          ) : preview.data ? (
            <PdfPreview blob={preview.data} />
          ) : (
            <p>{preview.isPending ? "批注 PDF 加载中..." : "批注 PDF 加载失败，请重试"}</p>
          )}
          <ErrorBanner error={preview.error} title="批注 PDF 加载失败" />
        </section>
      )}
    </div>
  );
}

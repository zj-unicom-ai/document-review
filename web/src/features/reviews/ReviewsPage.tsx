// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  createReview,
  deleteReview,
  listReviews,
  listRuleSets,
} from "../../api/endpoints";
import { Button } from "../../components/Button";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Field, Select } from "../../components/Field";
import { StatusBadge } from "../../components/StatusBadge";
import { ErrorBanner } from "../../components/StateBlocks";

const PAGE_SIZE = 10;

export function ReviewsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [ruleSetId, setRuleSetId] = useState("");
  const [validationError, setValidationError] = useState("");
  const [page, setPage] = useState(1);
  const [pendingDelete, setPendingDelete] = useState<{ id: number; file_name: string } | null>(
    null,
  );

  const ruleSets = useQuery({
    queryKey: ["rule-sets", "review"],
    queryFn: () => listRuleSets({ pageSize: 100 }),
  });

  // 进入页面默认选中第一个规则集，减少一步操作；用户手动清空后不覆盖
  useEffect(() => {
    if (ruleSetId) return;
    const first = ruleSets.data?.items?.[0];
    if (first) setRuleSetId(String(first.id));
  }, [ruleSetId, ruleSets.data]);

  const history = useQuery({
    queryKey: ["reviews", "list", page],
    queryFn: () => listReviews({ page, pageSize: PAGE_SIZE }),
  });

  const mutation = useMutation({
    mutationFn: () => createReview(file as File, Number(ruleSetId) || undefined),
    onSuccess: (run) => {
      setFile(null);
      void queryClient.invalidateQueries({ queryKey: ["reviews", "list"] });
      navigate(`/reviews/${run.id}`);
    },
  });

  const remove = useMutation({
    mutationFn: (id: number) => deleteReview(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reviews", "list"] });
    },
  });

  const total = history.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="page-stack">
      <form
        className="upload-layout"
        onSubmit={(event) => {
          event.preventDefault();
          setValidationError("");
          if (!ruleSetId) {
            setValidationError("请先选择规则集");
            return;
          }
          if (!file) {
            setValidationError("请上传需要审查的PDF文档");
            return;
          }
          mutation.mutate();
        }}
      >
        <Field label="选中规则集">
          <Select
            value={ruleSetId}
            onChange={(event) => setRuleSetId(event.target.value)}
            aria-label="选中规则集"
          >
            <option value="">请选择</option>
            {(ruleSets.data?.items ?? []).map((ruleSet) => (
              <option key={ruleSet.id} value={ruleSet.id}>
                {ruleSet.name}
              </option>
            ))}
          </Select>
        </Field>
        <label className="upload-hero">
          <input
            type="file"
            accept="application/pdf"
            aria-label="上传 PDF"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          {file ? (
            <span>
              <strong>{file.name}</strong>
              <small>已选择文件，点击可重新选择</small>
            </span>
          ) : (
            <span>
              <strong>上传 PDF</strong>
              <small>请上传需要审查的PDF文档</small>
            </span>
          )}
        </label>
        <Button type="submit" variant="primary" disabled={mutation.isPending}>
          开始审查
        </Button>
      </form>
      <ErrorBanner error={validationError || mutation.error} title="审查提交失败" />

      <section className="panel">
        <ErrorBanner error={history.error} title="历史审查读取失败" />
        <ErrorBanner error={remove.error} title="删除失败" />
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>文件名称</th>
                <th>规则集</th>
                <th>提交时间</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {(history.data?.items ?? []).map((run) => (
                <tr key={run.id}>
                  <td title={run.file_name}>{run.file_name}</td>
                  <td>{run.rule_set_name ?? "-"}</td>
                  <td>{run.created_at?.replace("T", " ").slice(0, 19) ?? "-"}</td>
                  <td>
                    <StatusBadge status={run.status} />
                  </td>
                  <td>
                    <div className="row-actions">
                      <Button onClick={() => navigate(`/reviews/${run.id}`)}>详情</Button>
                      <Button
                        variant="danger"
                        disabled={remove.isPending}
                        onClick={() => setPendingDelete(run)}
                      >
                        删除
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
              {!history.isPending && (history.data?.items ?? []).length === 0 ? (
                <tr>
                  <td colSpan={5}>暂无审查记录</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
        <div className="pager" aria-label="历史审查分页">
          <Button
            disabled={page <= 1 || history.isFetching}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
          >
            上一页
          </Button>
          <span>
            第 {page} / {totalPages} 页（共 {total} 条）
          </span>
          <Button
            disabled={page >= totalPages || history.isFetching}
            onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
          >
            下一页
          </Button>
        </div>
      </section>
      <ConfirmDialog
        open={pendingDelete !== null}
        title="删除审查记录"
        message={`确定删除审查记录「${pendingDelete?.file_name ?? ""}」吗？`}
        pending={remove.isPending}
        onConfirm={() => {
          if (!pendingDelete) return;
          remove.mutate(pendingDelete.id, {
            onSettled: () => setPendingDelete(null),
          });
        }}
        onClose={() => setPendingDelete(null)}
      />
    </div>
  );
}

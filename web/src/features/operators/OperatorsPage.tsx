// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { useQuery } from "@tanstack/react-query";
import { listOperators } from "../../api/endpoints";
import { PageHeader } from "../../components/PageHeader";
import { ErrorBanner } from "../../components/StateBlocks";
import { dataKindLabel } from "../../i18n/zh-CN";

// 结果口径的业务叫法；未知值回退展示原始编码（BL-048 E2）
const RESULT_SEMANTICS_LABELS: Record<string, string> = {
  hit_is_violation: "发现即问题",
  hit_is_pass: "全部符合才通过",
};

// 尚未落地的算子：置灰展示并标注建设中，不隐藏（BL-048 A3）
// 清单逐项迭代的执行语义在 executor 已实现，不属于建设中（BL-051）。
const BUILDING_OP_CODES = new Set([
  "external_data_check",
  "external_db_check",
  "resource_lookup",
  "image_duplicate_check",
]);

function toLabel(value: string, labels: Record<string, string>) {
  return labels[value] ?? value;
}

export function OperatorsPage() {
  const operators = useQuery({
    queryKey: ["operators"],
    queryFn: () => listOperators({ pageSize: 200 }),
  });

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="CAPABILITIES"
        title="检查能力目录"
        description="系统支持的文档检查能力；灰色卡片为建设中能力，暂不可用于规则配置。"
      />
      <ErrorBanner error={operators.error} title="算子读取失败" />
      <div className="operator-grid">
        {(operators.data?.items ?? []).map((operator) => {
          const building = BUILDING_OP_CODES.has(operator.op_code);
          return (
            <article
              key={operator.id}
              className={building ? "operator-card is-building" : "operator-card"}
            >
              <header>
                <strong>{operator.name}</strong>
                {building ? <span className="operator-building-badge">建设中</span> : null}
              </header>
              <p>{operator.description ?? "暂无描述"}</p>
              <dl>
                <div>
                  <dt>适用对象</dt>
                  <dd>
                    {operator.applicable_data_kind
                      .map((kind) => dataKindLabel(kind))
                      .join("、")}
                  </dd>
                </div>
                <div>
                  <dt>结果口径</dt>
                  <dd>{toLabel(operator.result_semantics, RESULT_SEMANTICS_LABELS)}</dd>
                </div>
              </dl>
            </article>
          );
        })}
      </div>
    </div>
  );
}

// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { useEffect, useMemo, useRef, useState } from "react";
import type { Classification } from "../../api/endpoints";

function bySortOrder(a: Classification, b: Classification) {
  return (a.sort_order ?? a.classify_id) - (b.sort_order ?? b.classify_id) || a.classify_id - b.classify_id;
}

/** 业务分类选择：单下拉内层级展示，一级带小三角点开二级（BL-060 交互）。 */
export function ClassifySelect({
  classifications,
  value,
  onChange,
}: {
  classifications: Classification[];
  value: number | null;
  onChange: (classifyId: number | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const [expandedRootId, setExpandedRootId] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    function onDocMouseDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocMouseDown);
    return () => document.removeEventListener("mousedown", onDocMouseDown);
  }, [open]);

  const roots = useMemo(
    () => classifications.filter((item) => item.level === 1).sort(bySortOrder),
    [classifications],
  );
  const childrenOf = (rootId: number) =>
    classifications
      .filter((item) => item.level === 2 && item.parent_id === rootId)
      .sort(bySortOrder);
  const selected = classifications.find((item) => item.id === value) ?? null;

  function togglePanel() {
    const next = !open;
    setOpen(next);
    // 展开时若当前选中的是二级，自动展开其所属一级，保持上下文可见。
    if (next && selected?.level === 2 && selected.parent_id != null) {
      setExpandedRootId(selected.parent_id);
    }
  }

  function pick(classifyId: number | null) {
    onChange(classifyId);
    setOpen(false);
  }

  return (
    <div className="classify-select" ref={containerRef}>
      <button
        type="button"
        className="classify-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="业务分类"
        onClick={togglePanel}
      >
        <span>{selected ? selected.name : "不分类"}</span>
        <span className="classify-trigger-arrow" aria-hidden>
          ▾
        </span>
      </button>
      {open ? (
        <div className="classify-panel" role="listbox" aria-label="业务分类选项">
          <button
            type="button"
            role="option"
            aria-selected={value === null}
            className={"classify-row" + (value === null ? " is-selected" : "")}
            onClick={() => pick(null)}
          >
            不分类
          </button>
          {roots.map((root) => {
            const children = childrenOf(root.id);
            // 无明细的一级直接可选；含明细的一级点击只展开 / 折叠二级。
            if (children.length === 0) {
              return (
                <button
                  key={root.id}
                  type="button"
                  role="option"
                  aria-selected={value === root.id}
                  className={"classify-row" + (value === root.id ? " is-selected" : "")}
                  onClick={() => pick(root.id)}
                >
                  <span>{root.name}</span>
                </button>
              );
            }
            const expanded = expandedRootId === root.id;
            return (
              <div key={root.id} className="classify-group">
                <button
                  type="button"
                  className="classify-row has-children"
                  aria-expanded={expanded}
                  onClick={() => setExpandedRootId(expanded ? null : root.id)}
                >
                  <span>{root.name}</span>
                  <span className={"classify-caret" + (expanded ? " is-open" : "")} aria-hidden>
                    ▸
                  </span>
                </button>
                {expanded
                  ? children.map((child) => (
                      <button
                        key={child.id}
                        type="button"
                        role="option"
                        aria-selected={value === child.id}
                        className={
                          "classify-row level-2" + (value === child.id ? " is-selected" : "")
                        }
                        onClick={() => pick(child.id)}
                      >
                        <span>{child.name}</span>
                      </button>
                    ))
                  : null}
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

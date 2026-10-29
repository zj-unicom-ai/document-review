// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import type { ReactNode } from "react";

// 页面级录入表单使用的屏幕居中模态框，避免误用右侧抽屉交互。
export function Modal({
  title,
  open,
  onClose,
  children,
  footer,
  className = "",
}: {
  title: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}) {
  if (!open) {
    return null;
  }
  return (
    <div className="modal-backdrop">
      <section
        className={`modal ${className}`.trim()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <header>
          <h3>{title}</h3>
          <button type="button" className="modal-close" onClick={onClose} aria-label="关闭">
            ×
          </button>
        </header>
        <div className="modal-body">{children}</div>
        {footer ? <footer className="modal-footer">{footer}</footer> : null}
      </section>
    </div>
  );
}

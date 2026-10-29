// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { Button } from "./Button";
import { Modal } from "./Modal";

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  message: string;
  detail?: string[];
  confirmLabel?: string;
  cancelLabel?: string;
  pending?: boolean;
  onConfirm: () => void;
  onClose: () => void;
};

// 危险操作的统一应用内确认弹窗；替代浏览器原生 confirm。
export function ConfirmDialog({
  open,
  title,
  message,
  detail = [],
  confirmLabel = "确认删除",
  cancelLabel = "取消",
  pending = false,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  return (
    <Modal title={title} open={open} onClose={onClose} className="confirm-modal">
      <div className="confirm-body">
        <p>{message}</p>
        {detail.length ? (
          <ul>
            {detail.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : null}
      </div>
      <div className="modal-form">
        <div className="form-actions">
          <Button type="button" onClick={onClose} disabled={pending}>
            {cancelLabel}
          </Button>
          <Button type="button" variant="danger" disabled={pending} onClick={onConfirm}>
            {pending ? "处理中..." : confirmLabel}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

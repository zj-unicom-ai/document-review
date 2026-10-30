// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

export function CapabilityPlaceholder({ title, reason }: { title: string; reason: string }) {
  return (
    <section className="capability-placeholder">
      <strong>{title}</strong>
      <p>{reason}</p>
    </section>
  );
}

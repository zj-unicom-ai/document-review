// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <section className="empty-state">
      <strong>{title}</strong>
      {description ? <p>{description}</p> : null}
    </section>
  );
}

export function ErrorBanner({ error, title = "操作失败" }: { error: unknown; title?: string }) {
  if (!error) {
    return null;
  }
  const message = error instanceof Error ? error.message : String(error);
  return (
    <section className="error-banner" role="alert">
      <strong>{title}</strong>
      <span>{message}</span>
    </section>
  );
}

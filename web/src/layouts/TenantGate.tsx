// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { Outlet } from "react-router-dom";
import { useTenant } from "../tenant/TenantProvider";

export function TenantGate() {
  const { tenantId } = useTenant();

  if (!tenantId) {
    return (
      <section className="tenant-gate">
        <strong>请先选择租户</strong>
        <p>在顶部输入租户 ID 并保存后，才能访问租户数据。</p>
      </section>
    );
  }

  return <Outlet />;
}

// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "../layouts/AppShell";
import { TenantGate } from "../layouts/TenantGate";
import { TenantProvider } from "../tenant/TenantProvider";
import { AuthProvider } from "../auth/AuthProvider";
import { RequireAuth, RequirePermission } from "../auth/RequireAuth";
import { LoginPage } from "../auth/LoginPage";
import { ConceptsPage } from "../features/concepts/ConceptsPage";
import { ClassificationsPage } from "../features/classifications/ClassificationsPage";
import { RulesPage } from "../features/rules/RulesPage";
import { RuleSetsPage } from "../features/ruleSets/RuleSetsPage";
import { OperatorsPage } from "../features/operators/OperatorsPage";
import { ReviewsPage } from "../features/reviews/ReviewsPage";
import { ReviewDetailPage } from "../features/reviews/ReviewDetailPage";
import { TenantsPage } from "../features/tenants/TenantsPage";
import { TemplatesPage } from "../features/templates/TemplatesPage";
import { ExternalResourcesPage } from "../features/externalResources/ExternalResourcesPage";
import { RolesPage } from "../features/roles/RolesPage";
import { UsersPage } from "../features/users/UsersPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <TenantProvider>
          <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          >
            <Route index element={<Navigate to="/reviews" replace />} />
            <Route element={<TenantGate />}>
              <Route path="rules" element={<RequirePermission menuCode="rules"><RulesPage /></RequirePermission>} />
              <Route path="concepts" element={<RequirePermission menuCode="concepts"><ConceptsPage /></RequirePermission>} />
              <Route path="classifications" element={<RequirePermission menuCode="classifications"><ClassificationsPage /></RequirePermission>} />
              <Route path="rule-sets" element={<RequirePermission menuCode="rule_sets"><RuleSetsPage /></RequirePermission>} />
              <Route path="operators" element={<RequirePermission menuCode="operators"><OperatorsPage /></RequirePermission>} />
              <Route path="reviews" element={<RequirePermission menuCode="reviews"><ReviewsPage /></RequirePermission>} />
              <Route path="reviews/:reviewId" element={<RequirePermission menuCode="reviews"><ReviewDetailPage /></RequirePermission>} />
              <Route path="system/users" element={<RequirePermission menuCode="system_users"><UsersPage /></RequirePermission>} />
              <Route path="system/roles" element={<RequirePermission menuCode="system_roles"><RolesPage /></RequirePermission>} />
              <Route path="system/templates" element={<RequirePermission menuCode="system_templates"><TemplatesPage /></RequirePermission>} />
              <Route path="system/resources" element={<RequirePermission menuCode="system_resources"><ExternalResourcesPage /></RequirePermission>} />
            </Route>
            <Route path="system/tenants" element={<RequirePermission menuCode="system_tenants"><TenantsPage /></RequirePermission>} />
          </Route>
        </Routes>
        </TenantProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

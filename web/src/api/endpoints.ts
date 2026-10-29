// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { apiClient } from "./client";
import type { Entity, PageResult } from "../types/entities";

export type Concept = Entity<"ConceptOut">;
export type ConceptCreate = Entity<"ConceptCreate">;
export type ConceptUpdate = Entity<"ConceptUpdate">;
export type Classification = Entity<"ClassificationOut">;
export type ClassificationCreate = Entity<"ClassificationCreate">;
export type Rule = Entity<"RuleOut">;
export type RuleCreate = Entity<"RuleCreate">;
export type RuleTrialResult = Entity<"RuleTrialResponse">;
export type RuleSet = Entity<"RuleSetOut">;
export type RuleSetCreate = Entity<"RuleSetCreate">;
export type RuleSetItemIn = Entity<"RuleSetItemIn">;
export type RuleSetTemplateCompatibility = Entity<"RuleSetTemplateCompatibilityOut">;
export type Operator = Entity<"OperatorOut">;
export type ReviewRun = Entity<"ReviewRunDetail">;
export type Tenant = Entity<"TenantOut">;
export type DocumentTemplate = Entity<"DocumentTemplateOut">;
export type DocumentTemplateFromProfileCreate = Entity<"DocumentTemplateFromProfileCreate">;
export type TemplateTrialResult = Entity<"TemplateTrialResponse">;
export type ExternalResource = Entity<"ExternalResourceOut">;
export type AuthUser = Entity<"AuthUserOut">;
export type AuthLoginRequest = Entity<"AuthLoginRequest">;
export type UserAccount = Entity<"UserOut">;
export type UserCreate = Entity<"UserCreate">;
export type UserUpdate = Entity<"UserUpdate">;
export type Role = Entity<"RoleOut">;
export type RoleCreate = Entity<"RoleCreate">;
export type RoleUpdate = Entity<"RoleUpdate">;
export type MenuPermission = Entity<"MenuPermissionOut">;

export type ListQuery = {
  page?: number;
  pageSize?: number;
  q?: string;
};

function queryString(query: ListQuery = {}) {
  const params = new URLSearchParams({
    page: String(query.page ?? 1),
    page_size: String(query.pageSize ?? 20),
  });
  if (query.q?.trim()) {
    params.set("q", query.q.trim());
  }
  return params.toString();
}

export function login(payload: AuthLoginRequest) {
  return apiClient.post<AuthUser>("/api/v1/auth/login", payload);
}

export function getAuthMe() {
  return apiClient.get<AuthUser>("/api/v1/auth/me");
}

export function logout() {
  return apiClient.post<void>("/api/v1/auth/logout");
}

export function listConcepts(query: ListQuery = {}) {
  return apiClient.get<PageResult<Concept>>(`/api/v1/concepts?${queryString(query)}`);
}

export function createConcept(payload: ConceptCreate) {
  return apiClient.post<Concept>("/api/v1/concepts", payload);
}

export function updateConcept(id: number, payload: ConceptUpdate) {
  return apiClient.patch<Concept>(`/api/v1/concepts/${id}`, payload);
}

export function deleteConcept(id: number) {
  return apiClient.delete<void>(`/api/v1/concepts/${id}`);
}

export function listClassifications(query: ListQuery = {}) {
  return apiClient.get<PageResult<Classification>>(`/api/v1/classifications?${queryString(query)}`);
}

export function previewClassificationDelete(id: number) {
  return apiClient.get<Entity<"ClassificationDeletePreview">>(
    `/api/v1/classifications/${id}/delete-preview`,
  );
}

export function createClassification(payload: ClassificationCreate) {
  return apiClient.post<Classification>("/api/v1/classifications", payload);
}

export function updateClassification(
  id: number,
  payload: Entity<"ClassificationUpdate">,
) {
  return apiClient.patch<Classification>(`/api/v1/classifications/${id}`, payload);
}

export function deleteClassification(id: number) {
  return apiClient.delete<void>(`/api/v1/classifications/${id}`);
}

export function listRules(query: ListQuery = {}) {
  return apiClient.get<PageResult<Rule>>(`/api/v1/rules?${queryString(query)}`);
}

export function createRule(payload: RuleCreate) {
  return apiClient.post<Rule>("/api/v1/rules", payload);
}

export function updateRule(id: number, payload: Entity<"RuleUpdate">) {
  return apiClient.patch<Rule>(`/api/v1/rules/${id}`, payload);
}

export function enableRule(id: number) {
  return apiClient.post<Entity<"RuleEnableResponse">>(`/api/v1/rules/${id}/enable`);
}

export function disableRule(id: number) {
  return apiClient.post<Entity<"RuleEnableResponse">>(`/api/v1/rules/${id}/disable`);
}

export function deleteRule(id: number) {
  return apiClient.delete<void>(`/api/v1/rules/${id}`);
}

export function listRuleSets(query: ListQuery = {}) {
  return apiClient.get<PageResult<RuleSet>>(`/api/v1/rule-sets?${queryString(query)}`);
}

export function getRuleSet(id: number) {
  return apiClient.get<RuleSet>(`/api/v1/rule-sets/${id}`);
}

export function createRuleSet(payload: RuleSetCreate) {
  return apiClient.post<RuleSet>("/api/v1/rule-sets", payload);
}

export function updateRuleSet(id: number, payload: Entity<"RuleSetUpdate">) {
  return apiClient.patch<RuleSet>(`/api/v1/rule-sets/${id}`, payload);
}

export function replaceRuleSetItems(id: number, payload: { items: RuleSetItemIn[] }) {
  return apiClient.put<RuleSet>(`/api/v1/rule-sets/${id}/items`, payload);
}

export function getRuleSetTemplateCompatibility(id: number) {
  return apiClient.get<RuleSetTemplateCompatibility[]>(
    `/api/v1/rule-sets/${id}/template-compatibility`,
  );
}

export function deleteRuleSet(id: number) {
  return apiClient.delete<void>(`/api/v1/rule-sets/${id}`);
}

export function listOperators(query: ListQuery = {}) {
  return apiClient.get<PageResult<Operator>>(`/api/v1/operators?${queryString(query)}`);
}

export function createReview(file: File, ruleSetId?: number) {
  const form = new FormData();
  form.append("file", file);
  if (ruleSetId) {
    form.append("rule_set_id", String(ruleSetId));
  }
  return apiClient.upload<Entity<"ReviewRunOut">>("/api/v1/reviews", form);
}

export function listReviews(query: ListQuery = {}) {
  return apiClient.get<
    PageResult<Entity<"ReviewRunOut"> & { rule_set_name?: string | null }>
  >(`/api/v1/reviews?${queryString(query)}`);
}

export function deleteReview(id: number) {
  return apiClient.delete(`/api/v1/reviews/${id}`);
}

export function getReview(id: number) {
  return apiClient.get<ReviewRun>(`/api/v1/reviews/${id}`);
}

export function getReviewPlan(id: number) {
  return apiClient.get<{ items: Array<Record<string, unknown>> }>(`/api/v1/reviews/${id}/plan`);
}

export function getRuleExecutionTrace(reviewId: number, ruleId: number) {
  return apiClient.get<Record<string, unknown>>(`/api/v1/reviews/${reviewId}/rules/${ruleId}/trace`);
}

export function downloadAnnotatedPdf(reviewId: number) {
  return apiClient.blob(`/api/v1/reviews/${reviewId}/annotated-pdf`);
}

export function listUsers(query: ListQuery = {}) {
  return apiClient.get<PageResult<UserAccount>>(`/api/v1/users?${queryString(query)}`);
}

export function createUser(payload: UserCreate) {
  return apiClient.post<UserAccount>("/api/v1/users", payload);
}

export function updateUser(id: number, payload: UserUpdate) {
  return apiClient.patch<UserAccount>(`/api/v1/users/${id}`, payload);
}

export function deleteUser(id: number) {
  return apiClient.delete<void>(`/api/v1/users/${id}`);
}

export function listRoles(query: ListQuery = {}) {
  return apiClient.get<PageResult<Role>>(`/api/v1/roles?${queryString(query)}`);
}

export function createRole(payload: RoleCreate) {
  return apiClient.post<Role>("/api/v1/roles", payload);
}

export function updateRole(id: number, payload: RoleUpdate) {
  return apiClient.patch<Role>(`/api/v1/roles/${id}`, payload);
}

export function deleteRole(id: number) {
  return apiClient.delete<void>(`/api/v1/roles/${id}`);
}

export function listMenuPermissions() {
  return apiClient.get<MenuPermission[]>("/api/v1/menu-permissions");
}

export function listTenants(query: ListQuery = {}) {
  return apiClient.get<PageResult<Tenant>>(`/api/v1/tenants?${queryString(query)}`);
}

export function createTenant(payload: Entity<"TenantCreate">) {
  return apiClient.post<Tenant>("/api/v1/tenants", payload);
}

export function updateTenant(id: number, payload: Entity<"TenantUpdate">) {
  return apiClient.patch<Tenant>(`/api/v1/tenants/${id}`, payload);
}

export function listTemplates(query: ListQuery = {}) {
  return apiClient.get<PageResult<DocumentTemplate>>(`/api/v1/templates?${queryString(query)}`);
}

export function createTemplate(payload: Entity<"DocumentTemplateCreate">) {
  return apiClient.post<DocumentTemplate>("/api/v1/templates", payload);
}

export function updateTemplate(id: number, payload: Entity<"DocumentTemplateUpdate">) {
  return apiClient.patch<DocumentTemplate>(`/api/v1/templates/${id}`, payload);
}

export function deleteTemplate(id: number) {
  return apiClient.delete<void>(`/api/v1/templates/${id}`);
}

export function trialTemplate(file: File, ruleSetId?: number) {
  const form = new FormData();
  form.append("file", file);
  if (ruleSetId) {
    form.append("rule_set_id", String(ruleSetId));
  }
  return apiClient.upload<TemplateTrialResult>("/api/v1/templates/trial", form);
}

export function createTemplateFromProfile(
  profileId: number,
  payload: DocumentTemplateFromProfileCreate,
) {
  return apiClient.post<DocumentTemplate>(
    `/api/v1/templates/from-profile/${profileId}`,
    payload,
  );
}

export function listExternalResources(query: ListQuery = {}) {
  return apiClient.get<PageResult<ExternalResource>>(`/api/v1/external-resources?${queryString(query)}`);
}

export function createExternalResource(payload: Entity<"ExternalResourceCreate">) {
  return apiClient.post<ExternalResource>("/api/v1/external-resources", payload);
}

export function updateExternalResource(id: number, payload: Entity<"ExternalResourceUpdate">) {
  return apiClient.patch<ExternalResource>(`/api/v1/external-resources/${id}`, payload);
}

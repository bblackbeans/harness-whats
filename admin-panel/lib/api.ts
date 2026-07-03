import { getApiBase } from "./api-base";

const API_BASE = getApiBase();

export type Tenant = {
  id: string;
  name: string;
  language: string;
  active: boolean;
  settings: {
    routing?: {
      chatwoot_account_ids?: number[];
      chatwoot_inbox_ids?: number[];
      chatwoot_bot_token_set?: boolean;
      chatwoot_bot_token_preview?: string;
    };
    model?: { name?: string; temperature?: number; llm_model_id?: number | null };
    context?: Record<string, number>;
    rag?: Record<string, unknown>;
    handoff?: Record<string, unknown>;
  };
  prompts: Record<string, string>;
};

export type LlmModel = {
  id: number;
  provider_id: number;
  model_id: string;
  display_name: string;
  cost_per_1m_input: number;
  cost_per_1m_output: number;
};

export type KnowledgeFile = { name: string; size: number; updated_at: number };

function authHeaders(json = true): HeadersInit {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const headers: HeadersInit = {};
  if (json) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function request<T>(path: string, options: RequestInit = {}, authRedirect = true): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers: { ...authHeaders(), ...options.headers } });
  if (res.status === 401 && typeof window !== "undefined" && authRedirect) {
    localStorage.removeItem("access_token");
    window.location.href = "/login";
    throw new Error("Não autenticado");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `Erro ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export async function login(email: string, password: string) {
  return request<{ access_token: string; refresh_token: string }>(
    "/admin/api/auth/login",
    {
      method: "POST",
      body: JSON.stringify({ email, password }),
    },
    false
  );
}

export async function listTenants(): Promise<Tenant[]> {
  return request("/admin/api/tenants");
}

export async function getTenant(id: string): Promise<Tenant> {
  return request(`/admin/api/tenants/${id}`);
}

export type TenantCreatePayload = {
  id: string;
  name: string;
  language?: string;
  active?: boolean;
  settings?: Record<string, unknown>;
  prompts?: Record<string, string>;
  portal_user?: { email: string; password: string; name?: string };
};

export async function createTenant(data: TenantCreatePayload): Promise<Tenant> {
  return request("/admin/api/tenants", { method: "POST", body: JSON.stringify(data) });
}

export async function updateTenant(id: string, data: unknown): Promise<Tenant> {
  return request(`/admin/api/tenants/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function toggleTenantActive(id: string, active: boolean): Promise<Tenant> {
  return request(`/admin/api/tenants/${id}/active?active=${active}`, { method: "PATCH" });
}

export async function listLlmModels(): Promise<LlmModel[]> {
  return request("/admin/api/llm/models");
}

export async function getTenantModels(tenantId: string) {
  return request<Array<{ id: number; model_id: string; display_name: string; is_default: boolean }>>(
    `/admin/api/tenants/${tenantId}/models`
  );
}

export async function setTenantModels(tenantId: string, modelIds: number[], defaultModelId: number | null) {
  return request(`/admin/api/tenants/${tenantId}/models`, {
    method: "PUT",
    body: JSON.stringify({ model_ids: modelIds, default_model_id: defaultModelId }),
  });
}

export async function listKnowledge(tenantId: string): Promise<{ files: KnowledgeFile[] }> {
  return request(`/admin/api/tenants/${tenantId}/knowledge`);
}

export async function uploadKnowledge(tenantId: string, file: File) {
  const token = localStorage.getItem("access_token");
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/admin/api/tenants/${tenantId}/knowledge`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) throw new Error("Falha no upload");
  return res.json();
}

export async function deleteKnowledge(tenantId: string, filename: string) {
  return request(`/admin/api/tenants/${tenantId}/knowledge/${encodeURIComponent(filename)}`, { method: "DELETE" });
}

export async function reindexKnowledge(tenantId: string) {
  return request(`/admin/api/tenants/${tenantId}/knowledge/reindex`, { method: "POST" });
}

export async function usageSummary() {
  return request<
    Array<{
      tenant_id: string;
      calls: number;
      tokens_total: number;
      cost_estimate: number;
    }>
  >("/admin/api/usage/summary");
}

export async function usageDaily(tenantId?: string, days = 30) {
  const q = new URLSearchParams({ days: String(days) });
  if (tenantId) q.set("tenant_id", tenantId);
  return request<Array<{ date: string; calls: number; cost_estimate: number }>>(
    `/admin/api/usage/daily?${q}`
  );
}

export async function usageByModel(tenantId?: string) {
  const q = tenantId ? `?tenant_id=${tenantId}` : "";
  return request<Array<{ model_ref: string; calls: number; tokens_total: number; cost_estimate: number }>>(
    `/admin/api/usage/by-model${q}`
  );
}

export async function getTenantUsage(tenantId: string) {
  return request<{
    usage: { calls: number; tokens_total: number; cost_estimate: number };
    limits: {
      plan?: { name: string; slug: string };
      exceeded: boolean;
      mode: string;
      limits: Record<string, unknown>;
    };
  }>(`/admin/api/tenants/${tenantId}/usage`);
}

export type Plan = {
  id: number;
  slug: string;
  name: string;
  description: string;
  limits: Record<string, unknown>;
  active: boolean;
};

export async function listPlans(): Promise<Plan[]> {
  return request("/admin/api/plans");
}

export async function createPlan(data: {
  slug: string;
  name: string;
  description?: string;
  limits?: Record<string, unknown>;
}) {
  return request("/admin/api/plans", { method: "POST", body: JSON.stringify(data) });
}

export async function assignTenantPlan(tenantId: string, planId: number) {
  return request(`/admin/api/tenants/${tenantId}/plan`, {
    method: "PUT",
    body: JSON.stringify({ plan_id: planId }),
  });
}

export async function getTenantPlan(tenantId: string) {
  return request<{ plan: Plan | null; limits: Record<string, unknown> }>(`/admin/api/tenants/${tenantId}/plan`);
}

export async function listAudit(limit = 20) {
  return request<Array<{ action: string; tenant_id: string | null; admin_email: string; created_at: string }>>(
    `/admin/api/audit?limit=${limit}`
  );
}

export type OpsLogEvent = {
  ts: string;
  delivery_id: string;
  message_id: string;
  conversation_id: number;
  status: string;
  detail: string;
  tenant_id: string;
  tenant_name?: string;
  account_id: number | null;
  inbox_id: number | null;
  direction: "inbound" | "outbound" | "system";
  label: string;
};

export async function listOpsLogs(page = 1, pageSize = 20, tenantId?: string) {
  const q = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (tenantId) q.set("tenant_id", tenantId);
  return request<{
    events: OpsLogEvent[];
    total: number;
    page: number;
    page_size: number;
    pages: number;
  }>(`/admin/api/ops/logs?${q}`);
}

export async function createLlmProvider(name: string, apiKey: string) {
  return request("/admin/api/llm/providers", {
    method: "POST",
    body: JSON.stringify({ name, provider_type: "openai", api_key: apiKey }),
  });
}

export async function createLlmModel(data: {
  provider_id: number;
  model_id: string;
  display_name: string;
  cost_per_1m_input?: number;
  cost_per_1m_output?: number;
}) {
  return request("/admin/api/llm/models", { method: "POST", body: JSON.stringify(data) });
}

export async function updateLlmProvider(
  id: number,
  data: { name?: string; api_key?: string; active?: boolean }
) {
  return request(`/admin/api/llm/providers/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function updateLlmModel(
  id: number,
  data: {
    provider_id?: number;
    display_name?: string;
    model_id?: string;
    cost_per_1m_input?: number;
    cost_per_1m_output?: number;
    temperature_default?: number;
  }
) {
  return request(`/admin/api/llm/models/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function listLlmProviders() {
  return request<
    Array<{ id: number; name: string; provider_type: string; active: boolean; api_key_preview: string }>
  >("/admin/api/llm/providers");
}

export async function listTenantUsers(tenantId: string) {
  return request<Array<{ id: number; email: string; name: string; active: boolean }>>(
    `/admin/api/tenants/${tenantId}/users`
  );
}

export async function createTenantUser(tenantId: string, data: { email: string; password: string; name?: string }) {
  return request(`/admin/api/tenants/${tenantId}/users`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export type ModelChangeRequest = {
  id: number;
  tenant_id: string;
  requested_by: string;
  requested_model_id: number;
  reason: string;
  status: string;
  created_at: string;
};

export async function listModelChangeRequests(status?: string) {
  const q = status ? `?status=${status}` : "";
  return request<ModelChangeRequest[]>(`/admin/api/model-requests${q}`);
}

export async function approveModelChangeRequest(id: number) {
  return request(`/admin/api/model-requests/${id}/approve`, { method: "POST" });
}

export async function rejectModelChangeRequest(id: number) {
  return request(`/admin/api/model-requests/${id}/reject`, { method: "POST" });
}

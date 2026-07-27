import { getApiBase } from "./api-base";
import type { Contact, CustomField, HttpTool, InboundWebhook, SendableFile } from "./crm-types";
export type { Contact, CustomField, HttpTool, InboundWebhook, SendableFile } from "./crm-types";
import type { AgentToolBinding, AgentToolItem, FlowItem, FlowRun, TenantAgent } from "./flow-types";
export type { AgentToolBinding, AgentToolItem, FlowItem, FlowRun, TenantAgent } from "./flow-types";

const API_BASE = getApiBase();

export type PortalMe = {
  email: string;
  name: string;
  tenant: {
    id: string;
    name: string;
    settings?: { model?: { name?: string } };
  };
};

function portalHeaders(json = true): HeadersInit {
  const token = typeof window !== "undefined" ? localStorage.getItem("portal_access_token") : null;
  const headers: HeadersInit = {};
  if (json) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function portalRequest<T>(path: string, options: RequestInit = {}, authRedirect = true): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...portalHeaders(), ...options.headers },
  });
  if (res.status === 401 && typeof window !== "undefined" && authRedirect) {
    localStorage.removeItem("portal_access_token");
    window.location.href = "/portal/login";
    throw new Error(
      "Acesso não encontrado. Peça ao administrador para criar seu usuário no painel de clientes."
    );
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    if (res.status === 401) {
      throw new Error(
        "Acesso não encontrado. Peça ao administrador para criar seu usuário no painel de clientes."
      );
    }
    throw new Error(typeof body.detail === "string" ? body.detail : `Erro ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export async function portalLogin(email: string, password: string) {
  return portalRequest<{ access_token: string; tenant_id: string }>(
    "/portal/api/auth/login",
    {
      method: "POST",
      body: JSON.stringify({ email, password }),
    },
    false
  );
}

export async function portalMe() {
  return portalRequest<PortalMe>("/portal/api/me");
}

export async function portalUsage() {
  return portalRequest<{
    usage: { calls: number; tokens_total: number; cost_estimate: number };
    limits: {
      plan?: { name: string; slug: string };
      exceeded: boolean;
      mode: string;
      limits: Record<string, unknown>;
    };
  }>("/portal/api/usage");
}

export async function portalGetPrompts() {
  return portalRequest<Record<string, string>>("/portal/api/prompts");
}

export async function portalUpdatePrompt(name: string, content: string) {
  return portalRequest(`/portal/api/prompts/${name}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
}

export async function portalListKnowledge() {
  return portalRequest<{ files: Array<{ name: string; size: number }> }>("/portal/api/knowledge");
}

export async function portalUploadKnowledge(file: File) {
  const token = localStorage.getItem("portal_access_token");
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/portal/api/knowledge`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) throw new Error("Falha no upload");
  return res.json();
}

export async function portalDeleteKnowledge(filename: string) {
  return portalRequest(`/portal/api/knowledge/${encodeURIComponent(filename)}`, { method: "DELETE" });
}

export async function portalReindexKnowledge() {
  return portalRequest("/portal/api/knowledge/reindex", { method: "POST" });
}

export type ProblemaFeedbackPayload = {
  titulo: string;
  descricao: string;
  passos?: string;
  correlation_id?: string;
  contexto?: Record<string, unknown>;
};

export async function portalReportProblem(payload: ProblemaFeedbackPayload) {
  return portalRequest<{ id: string; correlation_id: string }>("/portal/api/problemas/feedback", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// --- CRM ---

const CRM = "/portal/api/crm";

export async function portalListFields() {
  return portalRequest<{ fields: CustomField[] }>(`${CRM}/fields`);
}

export async function portalCreateField(data: {
  key: string;
  label: string;
  field_type?: string;
  required?: boolean;
}) {
  return portalRequest<CustomField>(`${CRM}/fields`, { method: "POST", body: JSON.stringify(data) });
}

export async function portalUpdateField(
  id: number,
  data: Partial<{ label: string; field_type: string; required: boolean }>
) {
  return portalRequest<CustomField>(`${CRM}/fields/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function portalDeleteField(id: number) {
  return portalRequest(`${CRM}/fields/${id}`, { method: "DELETE" });
}

export async function portalListContacts(q = "") {
  const qs = q ? `?q=${encodeURIComponent(q)}` : "";
  return portalRequest<{ contacts: Contact[] }>(`${CRM}/contacts${qs}`);
}

export async function portalGetContact(id: number) {
  return portalRequest<Contact>(`${CRM}/contacts/${id}`);
}

export async function portalCreateContact(data: {
  phone: string;
  name?: string;
  email?: string;
  fields?: Record<string, unknown>;
}) {
  return portalRequest<Contact>(`${CRM}/contacts`, { method: "POST", body: JSON.stringify(data) });
}

export async function portalUpdateContact(
  id: number,
  data: Partial<{ name: string; email: string; phone: string; fields: Record<string, unknown> }>
) {
  return portalRequest<Contact>(`${CRM}/contacts/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function portalDeleteContact(id: number) {
  return portalRequest(`${CRM}/contacts/${id}`, { method: "DELETE" });
}

export async function portalListWebhooks() {
  return portalRequest<{ webhooks: InboundWebhook[] }>(`${CRM}/webhooks`);
}

export async function portalCreateWebhook(data: {
  name: string;
  slug?: string;
  field_mapping?: Record<string, string>;
  start_conversation?: boolean;
  initial_message?: string;
}) {
  return portalRequest<InboundWebhook>(`${CRM}/webhooks`, { method: "POST", body: JSON.stringify(data) });
}

export async function portalUpdateWebhook(
  id: number,
  data: Partial<{
    name: string;
    field_mapping: Record<string, string>;
    start_conversation: boolean;
    initial_message: string;
    active: boolean;
  }>
) {
  return portalRequest<InboundWebhook>(`${CRM}/webhooks/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function portalRegenWebhookSecret(id: number) {
  return portalRequest<InboundWebhook>(`${CRM}/webhooks/${id}/regenerate-secret`, { method: "POST" });
}

export async function portalDeleteWebhook(id: number) {
  return portalRequest(`${CRM}/webhooks/${id}`, { method: "DELETE" });
}

export async function portalListHttpTools() {
  return portalRequest<{ tools: HttpTool[] }>(`${CRM}/http-tools`);
}

export async function portalCreateHttpTool(data: Partial<HttpTool> & { name: string; url: string }) {
  return portalRequest<HttpTool>(`${CRM}/http-tools`, { method: "POST", body: JSON.stringify(data) });
}

export async function portalUpdateHttpTool(id: number, data: Partial<HttpTool>) {
  return portalRequest<HttpTool>(`${CRM}/http-tools/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function portalDeleteHttpTool(id: number) {
  return portalRequest(`${CRM}/http-tools/${id}`, { method: "DELETE" });
}

export async function portalListSendableFiles() {
  return portalRequest<{ files: SendableFile[] }>(`${CRM}/files`);
}

export async function portalUploadSendableFile(file: File, description = "") {
  const token = localStorage.getItem("portal_access_token");
  const form = new FormData();
  form.append("file", file);
  form.append("description", description);
  const res = await fetch(`${API_BASE}${CRM}/files`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : "Falha no upload");
  }
  return res.json() as Promise<SendableFile>;
}

export async function portalUpdateSendableFile(id: number, description: string) {
  return portalRequest<SendableFile>(`${CRM}/files/${id}`, {
    method: "PUT",
    body: JSON.stringify({ description }),
  });
}

export async function portalDeleteSendableFile(id: number) {
  return portalRequest(`${CRM}/files/${id}`, { method: "DELETE" });
}

// --- Agents / Flows ---

export async function portalListAgents(role?: string) {
  const q = role ? `?role=${encodeURIComponent(role)}` : "";
  return portalRequest<{ agents: TenantAgent[] }>(`/portal/api/agents${q}`);
}

export async function portalGetOrchestrator() {
  return portalRequest<TenantAgent>("/portal/api/orchestrator");
}

export async function portalUpdateOrchestrator(data: Partial<TenantAgent>) {
  return portalRequest<TenantAgent>("/portal/api/orchestrator", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function portalCreateAgent(data: Partial<TenantAgent> & { name: string }) {
  return portalRequest<TenantAgent>("/portal/api/agents", {
    method: "POST",
    body: JSON.stringify({ ...data, role: data.role || "specialist" }),
  });
}

export async function portalUpdateAgent(id: number, data: Partial<TenantAgent>) {
  return portalRequest<TenantAgent>(`/portal/api/agents/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function portalDeleteAgent(id: number) {
  return portalRequest(`/portal/api/agents/${id}`, { method: "DELETE" });
}

export async function portalGetAgentTools(id: number) {
  return portalRequest<{ bindings: AgentToolBinding[] }>(`/portal/api/agents/${id}/tools`);
}

export async function portalSetAgentTools(id: number, bindings: AgentToolBinding[]) {
  return portalRequest<{ bindings: AgentToolBinding[] }>(`/portal/api/agents/${id}/tools`, {
    method: "PUT",
    body: JSON.stringify({ bindings }),
  });
}

export async function portalListAgentTools(agentId?: number) {
  const q = agentId ? `?agent_id=${agentId}` : "";
  return portalRequest<{ tools: AgentToolItem[] }>(`/portal/api/tools${q}`);
}

export async function portalGetAgentTool(id: number) {
  return portalRequest<AgentToolItem>(`/portal/api/tools/${id}`);
}

export async function portalCreateAgentTool(
  data: Partial<AgentToolItem> & { agent_id: number; name: string }
) {
  return portalRequest<AgentToolItem>("/portal/api/tools", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function portalUpdateAgentTool(id: number, data: Partial<AgentToolItem>) {
  return portalRequest<AgentToolItem>(`/portal/api/tools/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function portalDeleteAgentTool(id: number) {
  return portalRequest(`/portal/api/tools/${id}`, { method: "DELETE" });
}

export async function portalListFlows(agentId?: number) {
  const q = agentId ? `?agent_id=${agentId}` : "";
  return portalRequest<{ flows: FlowItem[] }>(`/portal/api/flows${q}`);
}

export async function portalGetFlow(id: number) {
  return portalRequest<FlowItem>(`/portal/api/flows/${id}`);
}

export async function portalCreateFlow(data: {
  name: string;
  agent_id?: number;
  description?: string;
  base_prompt?: string;
}) {
  return portalRequest<FlowItem>("/portal/api/flows", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function portalUpdateFlow(id: number, data: Partial<FlowItem>) {
  return portalRequest<FlowItem>(`/portal/api/flows/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function portalPublishFlow(id: number) {
  return portalRequest<FlowItem>(`/portal/api/flows/${id}/publish`, { method: "POST" });
}

export async function portalDeleteFlow(id: number) {
  return portalRequest(`/portal/api/flows/${id}`, { method: "DELETE" });
}

export async function portalImportFlow(file: File, agentId?: number, name = "") {
  const token = localStorage.getItem("portal_access_token");
  const form = new FormData();
  form.append("file", file);
  if (agentId) form.append("agent_id", String(agentId));
  if (name) form.append("name", name);
  const res = await fetch(`${API_BASE}/portal/api/flows/import`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : "Falha na importação");
  }
  return res.json() as Promise<FlowItem>;
}

export async function portalRecompileFlow(id: number) {
  return portalRequest<FlowItem>(`/portal/api/flows/${id}/recompile`, { method: "POST" });
}

export async function portalListFlowRuns(flowId?: number) {
  const q = flowId ? `?flow_id=${flowId}` : "";
  return portalRequest<{ runs: FlowRun[] }>(`/portal/api/flow-runs${q}`);
}

export async function portalGetFlowRun(id: number) {
  return portalRequest<FlowRun>(`/portal/api/flow-runs/${id}`);
}

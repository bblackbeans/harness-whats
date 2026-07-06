import { getApiBase } from "./api-base";

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

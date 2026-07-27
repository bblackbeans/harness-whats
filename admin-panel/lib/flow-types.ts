export type TenantAgent = {
  id: number;
  name: string;
  description: string;
  system_prompt: string;
  role: "orchestrator" | "specialist" | string;
  is_default: boolean;
  active: boolean;
};

export type AgentToolBinding = {
  id?: number;
  tool_kind: string;
  tool_ref: string;
};

export type AgentToolItem = {
  id: number;
  agent_id: number;
  name: string;
  slug: string;
  kind: string;
  rules: string;
  method: string;
  url: string;
  headers: Record<string, string>;
  body_template: string;
  auth_header: string;
  file_ids: number[];
  active: boolean;
};

export type FlowItem = {
  id: number;
  agent_id: number;
  name: string;
  description: string;
  base_prompt: string;
  status: "draft" | "published" | string;
  is_default: boolean;
  source_filename: string;
  import_summary: {
    titulo?: string;
    etapas_resumo?: string[];
    campos_detectados?: string[];
    integracoes_detectadas?: string[];
    handoff?: boolean;
    observacoes?: string;
  };
  roteiro: Record<string, unknown>;
  checklist: Array<{ id?: string; titulo?: string } | string>;
  source_raw?: string;
};

export type FlowRun = {
  id: number;
  flow_id: number;
  conversation_id: number;
  phone: string;
  checklist_state: Record<string, string>;
  current_step_id: string;
  variables: Record<string, unknown>;
  tools_log: unknown[];
  status: string;
  started_at?: string | null;
  updated_at?: string | null;
};

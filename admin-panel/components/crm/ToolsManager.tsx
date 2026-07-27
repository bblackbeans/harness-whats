"use client";

import { FormEvent, useEffect, useState } from "react";
import type { AgentToolItem } from "@/lib/flow-types";
import type { TenantAgent } from "@/lib/flow-types";
import type { SendableFile } from "@/lib/crm-types";
import { Modal } from "@/components/Modal";

type Props = {
  loadAgents: () => Promise<{ agents: TenantAgent[] }>;
  loadTools: (agentId?: number) => Promise<{ tools: AgentToolItem[] }>;
  getTool: (id: number) => Promise<AgentToolItem>;
  createTool: (data: Partial<AgentToolItem> & { agent_id: number; name: string }) => Promise<AgentToolItem>;
  updateTool: (id: number, data: Partial<AgentToolItem>) => Promise<AgentToolItem>;
  deleteTool: (id: number) => Promise<unknown>;
  loadFiles: () => Promise<{ files: SendableFile[] }>;
};

const KINDS = [
  { value: "instruction", label: "Instrução / regra" },
  { value: "http", label: "HTTP / integração" },
  { value: "save_field", label: "Salvar campo" },
  { value: "send_file", label: "Enviar arquivo" },
  { value: "handoff", label: "Transferir humano" },
  { value: "transfer_agent", label: "Transferir agente" },
];

const emptyForm = {
  name: "",
  slug: "",
  kind: "instruction",
  rules: "",
  method: "POST",
  url: "",
  body_template: "",
  auth_header: "",
  file_ids: [] as number[],
  active: true,
};

export function ToolsManager(props: Props) {
  const [agents, setAgents] = useState<TenantAgent[]>([]);
  const [tools, setTools] = useState<AgentToolItem[]>([]);
  const [files, setFiles] = useState<SendableFile[]>([]);
  const [agentFilter, setAgentFilter] = useState<number | "">("");
  const [selected, setSelected] = useState<AgentToolItem | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [createName, setCreateName] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  async function refresh(agentId?: number | "") {
    const aid = agentId === "" || agentId === undefined ? undefined : Number(agentId);
    const [a, t, f] = await Promise.all([
      props.loadAgents(),
      props.loadTools(aid),
      props.loadFiles(),
    ]);
    setAgents((a.agents || []).filter((x) => x.role !== "orchestrator"));
    setTools(t.tools || []);
    setFiles(f.files || []);
  }

  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, []);

  async function selectTool(id: number) {
    setError("");
    setSuccess("");
    const tool = await props.getTool(id);
    setSelected(tool);
    setForm({
      name: tool.name,
      slug: tool.slug,
      kind: tool.kind,
      rules: tool.rules || "",
      method: tool.method || "POST",
      url: tool.url || "",
      body_template: tool.body_template || "",
      auth_header: tool.auth_header || "",
      file_ids: Array.isArray(tool.file_ids) ? tool.file_ids.map(Number) : [],
      active: tool.active,
    });
  }

  function toggleFile(id: number) {
    setForm((prev) => {
      const has = prev.file_ids.includes(id);
      return {
        ...prev,
        file_ids: has ? prev.file_ids.filter((x) => x !== id) : [...prev.file_ids, id],
      };
    });
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    const agentId = agentFilter || agents[0]?.id;
    if (!agentId) {
      setError("Selecione um agente antes de criar a tool.");
      return;
    }
    const created = await props.createTool({
      agent_id: Number(agentId),
      name: createName,
      kind: "instruction",
      rules: "Descreva quando e como usar esta ferramenta.",
    });
    setCreateName("");
    await refresh(agentFilter);
    await selectTool(created.id);
    setSuccess("Tool criada. Edite as regras e salve.");
  }

  async function onSave(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const payload = {
        ...form,
        agent_id: selected.agent_id,
        file_ids: form.kind === "send_file" ? form.file_ids : [],
      };
      const updated = await props.updateTool(selected.id, payload);
      setSelected(updated);
      await refresh(agentFilter);
      setSuccess("Tool salva.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  }

  const agentName = (id: number) => agents.find((a) => a.id === id)?.name || `Agente #${id}`;

  return (
    <div className="space-y-6">
      <Modal
        open={deleteOpen}
        title="Remover tool"
        message={selected ? `Remover "${selected.name}"?` : "Remover esta tool?"}
        confirmLabel="Remover"
        danger
        onConfirm={async () => {
          if (!selected) return;
          await props.deleteTool(selected.id);
          setSelected(null);
          setDeleteOpen(false);
          await refresh(agentFilter);
        }}
        onCancel={() => setDeleteOpen(false)}
      />

      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      {success && <p className="text-sm text-green-700 dark:text-green-300">{success}</p>}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <select
          className="input-field"
          value={agentFilter}
          onChange={(e) => {
            const v = e.target.value ? Number(e.target.value) : "";
            setAgentFilter(v);
            setSelected(null);
            refresh(v).catch((err) => setError(err.message));
          }}
        >
          <option value="">Todos os agentes</option>
          {agents.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
              {a.is_default ? " (padrão)" : ""}
            </option>
          ))}
        </select>
      </div>

      <form onSubmit={onCreate} className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-white p-4 sm:flex-row dark:border-gray-800 dark:bg-gray-900">
        <input
          className="input-field flex-1"
          placeholder="Nome da tool (ex.: Consultar ERP, Salvar empreendimento)"
          value={createName}
          onChange={(e) => setCreateName(e.target.value)}
          required
        />
        <button type="submit" className="btn-primary">
          Criar tool
        </button>
      </form>
      <p className="text-xs text-gray-500 dark:text-gray-400">
        Selecione o agente no filtro (ou o primeiro da lista) e crie a tool com regras e, se precisar,
        endpoint HTTP. O agente decide quando usá-la na conversa.
      </p>

      <div className="grid gap-4 lg:grid-cols-2">
        <ul className="max-h-[560px] overflow-auto divide-y divide-gray-100 rounded-lg border border-gray-200 bg-white dark:divide-gray-800 dark:border-gray-800 dark:bg-gray-900">
          {tools.length === 0 && <li className="p-4 text-sm text-gray-500 dark:text-gray-400">Nenhuma tool.</li>}
          {tools.map((t) => (
            <li key={t.id}>
              <button
                type="button"
                className={`w-full px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-800 ${selected?.id === t.id ? "bg-brand-50 dark:bg-brand-600/20" : ""}`}
                onClick={() => selectTool(t.id).catch((e) => setError(e.message))}
              >
                <p className="font-medium text-gray-900 dark:text-gray-100">{t.name}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {agentName(t.agent_id)} · {t.kind}
                  {!t.active ? " · inativa" : ""}
                  {t.slug ? ` · ${t.slug}` : ""}
                  {t.kind === "send_file" && Array.isArray(t.file_ids) && t.file_ids.length > 0
                    ? ` · ${t.file_ids.length} arquivo(s)`
                    : ""}
                </p>
              </button>
            </li>
          ))}
        </ul>

        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
          {!selected ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">Selecione uma tool para editar regras e endpoint.</p>
          ) : (
            <form onSubmit={onSave} className="space-y-3">
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-semibold text-gray-900 dark:text-gray-100">Editar tool</h3>
                <button type="button" className="text-sm text-red-600 dark:text-red-400" onClick={() => setDeleteOpen(true)}>
                  Remover
                </button>
              </div>

              <label className="block text-sm">
                Agente
                <select
                  className="input-field mt-1 w-full"
                  value={selected.agent_id}
                  onChange={(e) =>
                    setSelected({ ...selected, agent_id: Number(e.target.value) })
                  }
                >
                  {agents.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block text-sm">
                Nome
                <input
                  className="input-field mt-1 w-full"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  required
                />
              </label>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block text-sm">
                  Tipo
                  <select
                    className="input-field mt-1 w-full"
                    value={form.kind}
                    onChange={(e) => setForm({ ...form, kind: e.target.value })}
                  >
                    {KINDS.map((k) => (
                      <option key={k.value} value={k.value}>
                        {k.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-sm">
                  Slug (id interno)
                  <input
                    className="input-field mt-1 w-full font-mono text-xs"
                    value={form.slug}
                    onChange={(e) => setForm({ ...form, slug: e.target.value })}
                  />
                </label>
              </div>

              <label className="block text-sm">
                Regras — o que fazer e quando usar
                <textarea
                  className="input-field mt-1 min-h-[140px] w-full text-sm"
                  value={form.rules}
                  onChange={(e) => setForm({ ...form, rules: e.target.value })}
                  placeholder="Ex.: Quando o cliente perguntar status do boleto, chame esta API com o CPF do contato e explique o resultado."
                  required
                />
              </label>

              {form.kind === "http" && (
                <div className="space-y-3 rounded-lg border border-dashed border-gray-200 p-3 dark:border-gray-800">
                  <p className="text-xs font-medium text-gray-700 dark:text-gray-300">Endpoint de integração</p>
                  <div className="grid gap-3 sm:grid-cols-4">
                    <label className="block text-sm sm:col-span-1">
                      Método
                      <select
                        className="input-field mt-1 w-full"
                        value={form.method}
                        onChange={(e) => setForm({ ...form, method: e.target.value })}
                      >
                        {["GET", "POST", "PUT", "PATCH", "DELETE"].map((m) => (
                          <option key={m} value={m}>
                            {m}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="block text-sm sm:col-span-3">
                      URL
                      <input
                        className="input-field mt-1 w-full font-mono text-xs"
                        value={form.url}
                        onChange={(e) => setForm({ ...form, url: e.target.value })}
                        placeholder="https://api.exemplo.com/v1/..."
                        required={form.kind === "http"}
                      />
                    </label>
                  </div>
                  <label className="block text-sm">
                    Auth header (opcional)
                    <input
                      className="input-field mt-1 w-full font-mono text-xs"
                      value={form.auth_header}
                      onChange={(e) => setForm({ ...form, auth_header: e.target.value })}
                      placeholder="Bearer {{token}}"
                    />
                  </label>
                  <label className="block text-sm">
                    Body template (opcional, usa {"{{vars}}"} do contato)
                    <textarea
                      className="input-field mt-1 min-h-[80px] w-full font-mono text-xs"
                      value={form.body_template}
                      onChange={(e) => setForm({ ...form, body_template: e.target.value })}
                      placeholder='{"cpf":"{{cpf}}","phone":"{{phone}}"}'
                    />
                  </label>
                </div>
              )}

              {form.kind === "send_file" && (
                <div className="space-y-2 rounded-lg border border-dashed border-gray-200 p-3 dark:border-gray-800">
                  <p className="text-xs font-medium text-gray-700 dark:text-gray-300">
                    Arquivos permitidos (1 ou mais)
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Se nenhum estiver marcado, o agente pode enviar qualquer arquivo da biblioteca.
                    Com seleção, só esses arquivos entram no prompt e na allowlist.
                  </p>
                  {files.length === 0 ? (
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Nenhum arquivo na biblioteca. Envie em Arquivos primeiro.
                    </p>
                  ) : (
                    <ul className="max-h-48 space-y-1 overflow-auto">
                      {files.map((f) => (
                        <li key={f.id}>
                          <label className="flex cursor-pointer items-start gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-gray-50 dark:hover:bg-gray-800">
                            <input
                              type="checkbox"
                              className="mt-0.5"
                              checked={form.file_ids.includes(f.id)}
                              onChange={() => toggleFile(f.id)}
                            />
                            <span>
                              <span className="font-medium text-gray-900 dark:text-gray-100">
                                {f.original_name}
                              </span>
                              {f.description ? (
                                <span className="block text-xs text-gray-500 dark:text-gray-400">
                                  {f.description}
                                </span>
                              ) : null}
                            </span>
                          </label>
                        </li>
                      ))}
                    </ul>
                  )}
                  {form.file_ids.length > 0 && (
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {form.file_ids.length} arquivo(s) selecionado(s)
                    </p>
                  )}
                </div>
              )}

              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.active}
                  onChange={(e) => setForm({ ...form, active: e.target.checked })}
                />
                Tool ativa
              </label>

              <button type="submit" className="btn-primary" disabled={saving}>
                {saving ? "Salvando…" : "Salvar tool"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

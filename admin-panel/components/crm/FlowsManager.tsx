"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import type { FlowItem, FlowRun, TenantAgent } from "@/lib/flow-types";
import { Modal } from "@/components/Modal";
import {
  buildRoteiroPayload,
  FlowStepsEditor,
  stepsFromRoteiro,
  type FlowStepDraft,
} from "@/components/crm/FlowStepsEditor";

type Props = {
  loadAgents: () => Promise<{ agents: TenantAgent[] }>;
  loadFlows: (agentId?: number) => Promise<{ flows: FlowItem[] }>;
  getFlow: (id: number) => Promise<FlowItem>;
  createFlow: (data: { name: string; agent_id?: number; description?: string }) => Promise<FlowItem>;
  publishFlow: (id: number) => Promise<FlowItem>;
  deleteFlow: (id: number) => Promise<unknown>;
  importFlow: (file: File, agentId?: number) => Promise<FlowItem>;
  recompileFlow: (id: number) => Promise<FlowItem>;
  updateFlow: (id: number, data: Partial<FlowItem>) => Promise<FlowItem>;
  loadRuns: (flowId?: number) => Promise<{ runs: FlowRun[] }>;
};

function metaFromFlow(flow: FlowItem) {
  const roteiro = (flow.roteiro || {}) as Record<string, unknown>;
  return {
    objetivo: String(roteiro.objetivo || ""),
    basePrompt: flow.base_prompt || "",
    handoffQuando: String(roteiro.handoff_quando || ""),
    encerramento: String(roteiro.encerramento || ""),
  };
}

export function FlowsManager(props: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [agents, setAgents] = useState<TenantAgent[]>([]);
  const [flows, setFlows] = useState<FlowItem[]>([]);
  const [selected, setSelected] = useState<FlowItem | null>(null);
  const [runs, setRuns] = useState<FlowRun[]>([]);
  const [agentFilter, setAgentFilter] = useState<number | "">("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const [savingSteps, setSavingSteps] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const [draftSteps, setDraftSteps] = useState<FlowStepDraft[]>([]);
  const [objetivo, setObjetivo] = useState("");
  const [basePrompt, setBasePrompt] = useState("");
  const [handoffQuando, setHandoffQuando] = useState("");
  const [encerramento, setEncerramento] = useState("");

  async function refresh(agentId?: number | "") {
    const aid = agentId === "" || agentId === undefined ? undefined : Number(agentId);
    const [a, f] = await Promise.all([props.loadAgents(), props.loadFlows(aid)]);
    setAgents(a.agents || []);
    setFlows(f.flows || []);
  }

  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, []);

  function loadEditorFromFlow(flow: FlowItem) {
    setDraftSteps(stepsFromRoteiro(flow.roteiro as Record<string, unknown>));
    const meta = metaFromFlow(flow);
    setObjetivo(meta.objetivo);
    setBasePrompt(meta.basePrompt);
    setHandoffQuando(meta.handoffQuando);
    setEncerramento(meta.encerramento);
  }

  async function selectFlow(id: number) {
    setError("");
    setSuccess("");
    const [flow, runData] = await Promise.all([props.getFlow(id), props.loadRuns(id)]);
    setSelected(flow);
    setRuns(runData.runs || []);
    loadEditorFromFlow(flow);
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    const defaultAgent = agents.find((a) => a.is_default) || agents[0];
    const created = await props.createFlow({
      name,
      agent_id: agentFilter ? Number(agentFilter) : defaultAgent?.id,
    });
    setName("");
    await refresh(agentFilter);
    await selectFlow(created.id);
    setSuccess("Rascunho criado. Adicione as etapas abaixo e salve.");
  }

  async function onImport(file: File) {
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const flow = await props.importFlow(
        file,
        agentFilter ? Number(agentFilter) : agents.find((a) => a.is_default)?.id
      );
      await refresh(agentFilter);
      await selectFlow(flow.id);
      setSuccess("Flow importado. Revise as etapas e publique quando estiver pronto.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro na importação");
    } finally {
      setBusy(false);
    }
  }

  async function confirmDeleteFlow() {
    if (!selected) return;
    setDeleting(true);
    setError("");
    try {
      await props.deleteFlow(selected.id);
      setSelected(null);
      setDeleteOpen(false);
      await refresh(agentFilter);
      setSuccess("Flow removido.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao remover Flow");
    } finally {
      setDeleting(false);
    }
  }

  async function saveSteps(): Promise<boolean> {
    if (!selected) return false;
    setSavingSteps(true);
    setError("");
    setSuccess("");
    try {
      const payload = buildRoteiroPayload(
        draftSteps,
        { objetivo, handoffQuando, encerramento },
        selected.roteiro as Record<string, unknown>
      );
      const updated = await props.updateFlow(selected.id, {
        base_prompt: basePrompt,
        roteiro: payload.roteiro,
        checklist: payload.checklist,
        import_summary: payload.import_summary,
      });
      setSelected(updated);
      loadEditorFromFlow(updated);
      await refresh(agentFilter);
      setSuccess("Etapas salvas. Publique o Flow para usar nas conversas.");
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar etapas");
      return false;
    } finally {
      setSavingSteps(false);
    }
  }

  const summary = selected?.import_summary || {};
  const checklist = selected?.checklist || [];

  const looksLikeAutomationImport =
    draftSteps.length > 0 &&
    draftSteps.every((s) => {
      const t = s.titulo.toLowerCase();
      return (
        t.includes("json") ||
        t.includes("finish") ||
        t.includes("webhook") ||
        t.includes("satisfaction") ||
        t.includes("pesquisa") ||
        t.includes("http") ||
        s.tools === "http_request" ||
        s.tools === "handoff"
      );
    }) &&
    draftSteps.some((s) => /json|finish|webhook|satisfaction|pesquisa/i.test(s.titulo));

  return (
    <div className="space-y-6">
      <Modal
        open={deleteOpen}
        title="Remover Flow"
        message={
          selected
            ? `Tem certeza que deseja remover "${selected.name}"? Esta ação não pode ser desfeita.`
            : "Tem certeza que deseja remover este Flow?"
        }
        confirmLabel={deleting ? "Removendo…" : "Remover"}
        cancelLabel="Cancelar"
        danger
        onConfirm={() => {
          if (!deleting) confirmDeleteFlow();
        }}
        onCancel={() => {
          if (!deleting) setDeleteOpen(false);
        }}
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
        <input
          ref={fileRef}
          type="file"
          accept=".flow,.json,.txt"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onImport(f);
            e.target.value = "";
          }}
        />
        <button type="button" className="btn-primary" disabled={busy} onClick={() => fileRef.current?.click()}>
          {busy ? "Importando…" : "Importar .flow / .json"}
        </button>
      </div>

      <form onSubmit={onCreate} className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-white p-4 sm:flex-row dark:border-gray-800 dark:bg-gray-900">
        <input
          className="input-field flex-1"
          placeholder="Nome do Flow (criar em branco)"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <button type="submit" className="btn-secondary">
          Criar rascunho
        </button>
      </form>
      <p className="text-xs text-gray-500 dark:text-gray-400">
        Um agente pode ter vários Flows, mas cada conversa usa <strong>apenas um</strong>: o marcado
        como Default (publicado), ou um override por webhook/<code>dispatch</code>. Depois de criar,
        selecione o Flow e use o <strong>Editor de etapas</strong> (ou importe um arquivo).
      </p>

      <div className="grid gap-4 lg:grid-cols-2">
        <ul className="max-h-[520px] overflow-auto divide-y divide-gray-100 rounded-lg border border-gray-200 bg-white dark:divide-gray-800 dark:border-gray-800 dark:bg-gray-900">
          {flows.length === 0 && <li className="p-4 text-sm text-gray-500 dark:text-gray-400">Nenhum Flow.</li>}
          {flows.map((f) => (
            <li key={f.id}>
              <button
                type="button"
                className={`w-full px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-800 ${selected?.id === f.id ? "bg-brand-50 dark:bg-brand-600/20" : ""}`}
                onClick={() => selectFlow(f.id).catch((e) => setError(e.message))}
              >
                <p className="font-medium text-gray-900 dark:text-gray-100">{f.name}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {f.status}
                  {f.is_default ? " · default" : ""}
                  {f.source_filename ? ` · ${f.source_filename}` : ""}
                  {(f.checklist || []).length > 0 ? ` · ${(f.checklist || []).length} etapa(s)` : " · sem etapas"}
                </p>
              </button>
            </li>
          ))}
        </ul>

        <div className="max-h-[720px] space-y-4 overflow-auto rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
          {!selected ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">Selecione um Flow para editar etapas, checklist e runs.</p>
          ) : (
            <>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100">{selected.name}</h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Status: {selected.status}
                    {selected.is_default ? " · padrão do agente" : ""}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {selected.status !== "published" && (
                    <button
                      type="button"
                      className="btn-primary text-sm"
                      onClick={async () => {
                        if (draftSteps.length === 0) {
                          setError("Adicione pelo menos uma etapa antes de publicar.");
                          return;
                        }
                        const ok = await saveSteps();
                        if (!ok) return;
                        const f = await props.publishFlow(selected.id);
                        setSelected(f);
                        loadEditorFromFlow(f);
                        await refresh(agentFilter);
                        setSuccess("Flow publicado.");
                      }}
                    >
                      Publicar
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn-secondary text-sm"
                    onClick={async () => {
                      const f = await props.updateFlow(selected.id, { is_default: true });
                      setSelected(f);
                      await refresh(agentFilter);
                    }}
                  >
                    Default
                  </button>
                  {selected.source_raw ? (
                    <button
                      type="button"
                      className="btn-secondary text-sm"
                      onClick={async () => {
                        setBusy(true);
                        try {
                          const f = await props.recompileFlow(selected.id);
                          setSelected(f);
                          loadEditorFromFlow(f);
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      Recompilar
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="text-sm text-red-600 dark:text-red-400"
                    onClick={() => setDeleteOpen(true)}
                  >
                    Remover
                  </button>
                </div>
              </div>

              {looksLikeAutomationImport && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                  Este import parece um fluxo de <strong>automação HyperFlow</strong> (webhook, APIs,
                  pesquisa), não um roteiro de conversa. O Harness usa o Flow como checklist para a IA
                  conversar — revise/reescreva as etapas (perguntas, campos, handoff) ou use como
                  referência e monte o roteiro no editor.
                </div>
              )}

              <FlowStepsEditor
                steps={draftSteps}
                objetivo={objetivo}
                basePrompt={basePrompt}
                handoffQuando={handoffQuando}
                encerramento={encerramento}
                saving={savingSteps}
                onChangeSteps={setDraftSteps}
                onChangeMeta={(meta) => {
                  setObjetivo(meta.objetivo);
                  setBasePrompt(meta.basePrompt);
                  setHandoffQuando(meta.handoffQuando);
                  setEncerramento(meta.encerramento);
                }}
                onSave={saveSteps}
              />

              {summary.etapas_resumo && summary.etapas_resumo.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-gray-900 dark:text-gray-100">Resumo</h4>
                  <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-gray-700 dark:text-gray-300">
                    {summary.etapas_resumo.map((line) => (
                      <li key={line}>{line.replace(/^\d+\.\s*/, "")}</li>
                    ))}
                  </ol>
                </div>
              )}

              <div>
                <h4 className="text-sm font-medium text-gray-900 dark:text-gray-100">Checklist (preview)</h4>
                <ul className="mt-2 space-y-1 text-sm text-gray-700 dark:text-gray-300">
                  {checklist.length === 0 && draftSteps.length === 0 && (
                    <li className="text-gray-400 dark:text-gray-500">Vazio — adicione etapas e salve.</li>
                  )}
                  {(checklist.length > 0 ? checklist : draftSteps.map((s) => ({ id: s.id, titulo: s.titulo }))).map(
                    (item, idx) => {
                      const titulo =
                        typeof item === "string" ? item : item.titulo || item.id || `item-${idx}`;
                      const id = typeof item === "string" ? item : item.id;
                      return (
                        <li key={`${id}-${idx}`}>
                          □ {titulo}
                          {id ? <span className="text-xs text-gray-400 dark:text-gray-500"> ({id})</span> : null}
                        </li>
                      );
                    }
                  )}
                </ul>
              </div>

              <div>
                <h4 className="text-sm font-medium text-gray-900 dark:text-gray-100">Execuções recentes</h4>
                <ul className="mt-2 max-h-40 overflow-auto divide-y divide-gray-100 text-sm dark:divide-gray-800">
                  {runs.length === 0 && <li className="py-2 text-gray-400 dark:text-gray-500">Nenhuma run ainda.</li>}
                  {runs.map((r) => (
                    <li key={r.id} className="py-2">
                      <p className="font-medium">
                        Conv #{r.conversation_id} · {r.status}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {r.phone || "sem telefone"} · etapa {r.current_step_id || "—"}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

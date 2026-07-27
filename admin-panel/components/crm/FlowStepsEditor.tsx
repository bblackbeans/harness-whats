"use client";

import { FormEvent, useEffect, useState } from "react";

export type FlowStepDraft = {
  id: string;
  titulo: string;
  obrigatoria: boolean;
  campos: string;
  validacao: string;
  tools: string;
};

type Props = {
  steps: FlowStepDraft[];
  objetivo: string;
  basePrompt: string;
  handoffQuando: string;
  encerramento: string;
  saving?: boolean;
  onChangeSteps: (steps: FlowStepDraft[]) => void;
  onChangeMeta: (meta: {
    objetivo: string;
    basePrompt: string;
    handoffQuando: string;
    encerramento: string;
  }) => void;
  onSave: () => Promise<void | boolean>;
};

const VALIDATION_OPTIONS = [
  { value: "", label: "Nenhuma" },
  { value: "texto_nao_vazio", label: "Texto obrigatório" },
  { value: "email", label: "Email" },
  { value: "cpf", label: "CPF" },
  { value: "numero", label: "Número" },
  { value: "telefone", label: "Telefone" },
];

const TOOL_OPTIONS = [
  { value: "", label: "Nenhuma" },
  { value: "save_field", label: "Salvar campo" },
  { value: "http_request", label: "Chamar API" },
  { value: "send_file", label: "Enviar arquivo" },
  { value: "handoff", label: "Transferir humano" },
  { value: "add_tag", label: "Adicionar tag" },
];

export function slugifyStepId(titulo: string, fallbackIndex: number): string {
  const base = titulo
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "")
    .slice(0, 40);
  return base || `step_${fallbackIndex + 1}`;
}

export function stepsFromRoteiro(roteiro: Record<string, unknown> | undefined): FlowStepDraft[] {
  const etapas = (roteiro?.etapas as Array<Record<string, unknown>>) || [];
  return etapas.map((e, i) => {
    const tools = Array.isArray(e.tools) ? e.tools : [];
    const firstTool =
      tools.length > 0 && typeof tools[0] === "object" && tools[0]
        ? String((tools[0] as { type?: string }).type || "")
        : "";
    const validacao =
      e.validacao && typeof e.validacao === "object"
        ? String((e.validacao as { tipo?: string }).tipo || "")
        : "";
    return {
      id: String(e.id || `step_${i + 1}`),
      titulo: String(e.titulo || e.id || `Etapa ${i + 1}`),
      obrigatoria: e.obrigatoria !== false,
      campos: Array.isArray(e.campos) ? e.campos.map(String).join(", ") : "",
      validacao,
      tools: firstTool,
    };
  });
}

export function buildRoteiroPayload(
  steps: FlowStepDraft[],
  meta: { objetivo: string; handoffQuando: string; encerramento: string },
  existing?: Record<string, unknown>
) {
  const usedIds = new Set<string>();
  const etapas = steps.map((s, i) => {
    let id = (s.id || slugifyStepId(s.titulo, i)).trim() || `step_${i + 1}`;
    if (usedIds.has(id)) id = `${id}_${i + 1}`;
    usedIds.add(id);
    const campos = s.campos
      .split(",")
      .map((c) => c.trim())
      .filter(Boolean);
    const tools = s.tools
      ? [
          {
            type: s.tools,
            params: s.tools === "save_field" && campos[0] ? { key: campos[0] } : {},
            condicao: "sempre",
          },
        ]
      : [];
    return {
      id,
      titulo: s.titulo.trim() || id,
      obrigatoria: s.obrigatoria,
      campos,
      validacao: s.validacao ? { tipo: s.validacao } : {},
      tools,
    };
  });

  const checklist = etapas.map((e) => ({ id: e.id, titulo: e.titulo }));
  const camposObrigatorios = Array.from(
    new Set(etapas.filter((e) => e.obrigatoria).flatMap((e) => e.campos))
  );

  return {
    roteiro: {
      ...(existing || {}),
      objetivo: meta.objetivo,
      etapas,
      campos_obrigatorios: camposObrigatorios,
      campos_opcionais: (existing?.campos_opcionais as string[]) || [],
      ferramentas: Array.from(
        new Set([
          ...((existing?.ferramentas as string[]) || []),
          ...etapas.flatMap((e) => e.tools.map((t) => t.type)),
        ].filter(Boolean))
      ),
      encerramento: meta.encerramento,
      handoff_quando: meta.handoffQuando,
    },
    checklist,
    import_summary: {
      titulo: "Editado manualmente",
      etapas_resumo: etapas.map((e, i) => `${i + 1}. ${e.titulo}`),
      campos_detectados: camposObrigatorios,
      integracoes_detectadas: etapas
        .filter((e) => e.tools.some((t) => t.type === "http_request"))
        .map((e) => e.titulo),
      handoff: etapas.some((e) => e.tools.some((t) => t.type === "handoff")),
      observacoes: "Roteiro montado no editor de etapas.",
    },
  };
}

export function FlowStepsEditor({
  steps,
  objetivo,
  basePrompt,
  handoffQuando,
  encerramento,
  saving,
  onChangeSteps,
  onChangeMeta,
  onSave,
}: Props) {
  const [localError, setLocalError] = useState("");

  useEffect(() => {
    setLocalError("");
  }, [steps]);

  function updateStep(index: number, patch: Partial<FlowStepDraft>) {
    const next = steps.map((s, i) => (i === index ? { ...s, ...patch } : s));
    onChangeSteps(next);
  }

  function addStep() {
    const n = steps.length + 1;
    onChangeSteps([
      ...steps,
      {
        id: `step_${n}`,
        titulo: "",
        obrigatoria: true,
        campos: "",
        validacao: "texto_nao_vazio",
        tools: "save_field",
      },
    ]);
  }

  function removeStep(index: number) {
    onChangeSteps(steps.filter((_, i) => i !== index));
  }

  function moveStep(index: number, dir: -1 | 1) {
    const target = index + dir;
    if (target < 0 || target >= steps.length) return;
    const next = [...steps];
    const [item] = next.splice(index, 1);
    next.splice(target, 0, item);
    onChangeSteps(next);
  }

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    if (steps.some((s) => !s.titulo.trim())) {
      setLocalError("Todas as etapas precisam de um título.");
      return;
    }
    setLocalError("");
    await onSave();
  }

  return (
    <form onSubmit={handleSave} className="space-y-4 border-t border-gray-100 pt-4 dark:border-gray-800">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h4 className="text-sm font-medium text-gray-900 dark:text-gray-100">Editor de etapas</h4>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Monte o roteiro que a IA deve seguir. Campos separados por vírgula (ex.: nome, cpf).
          </p>
        </div>
        <button type="button" className="btn-secondary text-sm" onClick={addStep}>
          + Adicionar etapa
        </button>
      </div>

      {localError && <p className="text-sm text-red-600 dark:text-red-400">{localError}</p>}

      <label className="block text-sm">
        Objetivo do Flow
        <input
          className="input-field mt-1 w-full"
          value={objetivo}
          onChange={(e) =>
            onChangeMeta({ objetivo: e.target.value, basePrompt, handoffQuando, encerramento })
          }
          placeholder="Ex.: Qualificar lead e coletar dados do imóvel"
        />
      </label>

      <div className="space-y-3">
        {steps.length === 0 && (
          <p className="rounded-lg border border-dashed border-gray-200 p-4 text-sm text-gray-500 dark:border-gray-800 dark:text-gray-400">
            Nenhuma etapa. Clique em <strong>Adicionar etapa</strong> ou importe um arquivo.
          </p>
        )}
        {steps.map((step, index) => (
          <div key={`${step.id}-${index}`} className="rounded-lg border border-gray-200 bg-gray-50/50 p-3 dark:border-gray-800 dark:bg-gray-950/50">
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Etapa {index + 1}</span>
              <div className="flex gap-1">
                <button type="button" className="btn-secondary px-2 py-1 text-xs" onClick={() => moveStep(index, -1)}>
                  ↑
                </button>
                <button type="button" className="btn-secondary px-2 py-1 text-xs" onClick={() => moveStep(index, 1)}>
                  ↓
                </button>
                <button
                  type="button"
                  className="px-2 py-1 text-xs text-red-600 dark:text-red-400"
                  onClick={() => removeStep(index)}
                >
                  Remover
                </button>
              </div>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="block text-xs sm:col-span-2">
                Título
                <input
                  className="input-field mt-1 w-full"
                  value={step.titulo}
                  onChange={(e) => {
                    const titulo = e.target.value;
                    const shouldSyncId = !step.id || step.id.startsWith("step_");
                    updateStep(index, {
                      titulo,
                      ...(shouldSyncId ? { id: slugifyStepId(titulo, index) } : {}),
                    });
                  }}
                  placeholder="Perguntar nome"
                  required
                />
              </label>
              <label className="block text-xs">
                ID interno
                <input
                  className="input-field mt-1 w-full font-mono"
                  value={step.id}
                  onChange={(e) => updateStep(index, { id: e.target.value })}
                  placeholder="ask_nome"
                />
              </label>
              <label className="block text-xs">
                Campos (vírgula)
                <input
                  className="input-field mt-1 w-full"
                  value={step.campos}
                  onChange={(e) => updateStep(index, { campos: e.target.value })}
                  placeholder="nome"
                />
              </label>
              <label className="block text-xs">
                Validação
                <select
                  className="input-field mt-1 w-full"
                  value={step.validacao}
                  onChange={(e) => updateStep(index, { validacao: e.target.value })}
                >
                  {VALIDATION_OPTIONS.map((o) => (
                    <option key={o.value || "none"} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-xs">
                Tool da etapa
                <select
                  className="input-field mt-1 w-full"
                  value={step.tools}
                  onChange={(e) => updateStep(index, { tools: e.target.value })}
                >
                  {TOOL_OPTIONS.map((o) => (
                    <option key={o.value || "none"} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex items-center gap-2 text-xs sm:col-span-2">
                <input
                  type="checkbox"
                  checked={step.obrigatoria}
                  onChange={(e) => updateStep(index, { obrigatoria: e.target.checked })}
                />
                Etapa obrigatória (IA não pode pular)
              </label>
            </div>
          </div>
        ))}
      </div>

      <label className="block text-sm">
        Prompt base do Flow
        <textarea
          className="input-field mt-1 min-h-[80px] w-full text-xs"
          value={basePrompt}
          onChange={(e) =>
            onChangeMeta({ objetivo, basePrompt: e.target.value, handoffQuando, encerramento })
          }
          placeholder="Instruções extras para a IA seguir este roteiro com naturalidade…"
        />
      </label>
      <label className="block text-sm">
        Quando transferir para humano
        <input
          className="input-field mt-1 w-full"
          value={handoffQuando}
          onChange={(e) =>
            onChangeMeta({ objetivo, basePrompt, handoffQuando: e.target.value, encerramento })
          }
          placeholder="Cliente pedir atendente ou após coleta completa"
        />
      </label>
      <label className="block text-sm">
        Encerramento
        <input
          className="input-field mt-1 w-full"
          value={encerramento}
          onChange={(e) =>
            onChangeMeta({ objetivo, basePrompt, handoffQuando, encerramento: e.target.value })
          }
          placeholder="Agradecer e encerrar quando todas as etapas forem concluídas"
        />
      </label>

      <button type="submit" className="btn-primary" disabled={saving}>
        {saving ? "Salvando etapas…" : "Salvar etapas"}
      </button>
    </form>
  );
}

"use client";

import { FormEvent, useEffect, useState } from "react";
import type { TenantAgent } from "@/lib/flow-types";

type Props = {
  load: () => Promise<TenantAgent>;
  save: (data: Partial<TenantAgent>) => Promise<TenantAgent>;
  loadSpecialists: () => Promise<{ agents: TenantAgent[] }>;
};

export function OrchestratorManager({ load, save, loadSpecialists }: Props) {
  const [orch, setOrch] = useState<TenantAgent | null>(null);
  const [specialists, setSpecialists] = useState<TenantAgent[]>([]);
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    Promise.all([load(), loadSpecialists()])
      .then(([o, s]) => {
        setOrch(o);
        setPrompt(o.system_prompt || "");
        setSpecialists((s.agents || []).filter((a) => a.role !== "orchestrator" && a.active));
      })
      .catch((e) => setError(e.message));
  }, []);

  async function onSave(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const updated = await save({ system_prompt: prompt });
      setOrch(updated);
      setSuccess("Orquestrador salvo.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      {success && <p className="text-sm text-green-700 dark:text-green-300">{success}</p>}

      <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-700 dark:border-gray-800 dark:bg-gray-950 dark:text-gray-300">
        O orquestrador classifica a <strong className="text-gray-900 dark:text-gray-100">primeira mensagem</strong> da conversa e escolhe um
        agente especializado. A conversa permanece sticky nesse agente até transferência explícita
        ou nova conversa.
      </div>

      <form onSubmit={onSave} className="space-y-3 rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100">{orch?.name || "Orquestrador Principal"}</h3>
        <label className="block text-sm text-gray-700 dark:text-gray-300">
          Prompt de roteamento
          <textarea
            className="input-field mt-1 min-h-[180px] w-full font-mono text-xs"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
        </label>
        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? "Salvando…" : "Salvar"}
        </button>
      </form>

      <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950">
        <h4 className="text-sm font-medium text-gray-900 dark:text-gray-100">Especialistas disponíveis</h4>
        <ul className="mt-2 divide-y divide-gray-100 text-sm dark:divide-gray-800">
          {specialists.length === 0 && (
            <li className="py-2 text-gray-400 dark:text-gray-500">Crie agentes em Automação → Agentes.</li>
          )}
          {specialists.map((a) => (
            <li key={a.id} className="py-2">
              <p className="font-medium text-gray-900 dark:text-gray-100">
                {a.name}
                {a.is_default ? <span className="ml-2 text-xs font-normal text-gray-500 dark:text-gray-400">padrão</span> : null}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">{a.description || "Sem descrição"}</p>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

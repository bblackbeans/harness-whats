"use client";

import { FormEvent, useEffect, useState } from "react";
import type { TenantAgent } from "@/lib/flow-types";
import { Modal } from "@/components/Modal";

type Props = {
  load: () => Promise<{ agents: TenantAgent[] }>;
  create: (data: Partial<TenantAgent> & { name: string }) => Promise<TenantAgent>;
  update: (id: number, data: Partial<TenantAgent>) => Promise<TenantAgent>;
  remove: (id: number) => Promise<unknown>;
};

export function AgentsManager({ load, create, update, remove }: Props) {
  const [agents, setAgents] = useState<TenantAgent[]>([]);
  const [selected, setSelected] = useState<TenantAgent | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const specialists = agents.filter((a) => a.role !== "orchestrator");

  async function refresh() {
    const data = await load();
    setAgents(data.agents || []);
  }

  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, []);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    const created = await create({
      name,
      role: "specialist",
      is_default: specialists.length === 0,
    });
    setName("");
    await refresh();
    setSelected(created);
  }

  async function onSavePrompt(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setSaving(true);
    try {
      const form = e.target as HTMLFormElement;
      const updated = await update(selected.id, {
        name: (form.elements.namedItem("agent_name") as HTMLInputElement).value,
        description: (form.elements.namedItem("agent_desc") as HTMLInputElement).value,
        system_prompt: (form.elements.namedItem("agent_prompt") as HTMLTextAreaElement).value,
      });
      setSelected(updated);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <Modal
        open={deleteOpen}
        title="Remover agente"
        message={
          selected
            ? `Remover "${selected.name}"? Flows e tools vinculados também serão removidos.`
            : "Remover este agente?"
        }
        confirmLabel="Remover"
        danger
        onConfirm={async () => {
          if (!selected) return;
          await remove(selected.id);
          setSelected(null);
          setDeleteOpen(false);
          await refresh();
        }}
        onCancel={() => setDeleteOpen(false)}
      />

      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      <form onSubmit={onCreate} className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-white p-4 sm:flex-row dark:border-gray-800 dark:bg-gray-900">
        <input
          className="input-field flex-1"
          placeholder="Nome do agente especializado (ex.: SAC, Comercial)"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <button type="submit" className="btn-primary">
          Criar agente
        </button>
      </form>
      <p className="text-xs text-gray-500 dark:text-gray-400">
        As ferramentas deste agente são criadas em <strong>Automação → Tools</strong> (regras +
        endpoint).
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        <ul className="divide-y divide-gray-100 rounded-lg border border-gray-200 bg-white dark:divide-gray-800 dark:border-gray-800 dark:bg-gray-900">
          {specialists.length === 0 && (
            <li className="p-4 text-sm text-gray-500 dark:text-gray-400">Nenhum especialista ainda.</li>
          )}
          {specialists.map((a) => (
            <li key={a.id}>
              <button
                type="button"
                className={`w-full px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-800 ${selected?.id === a.id ? "bg-brand-50 dark:bg-brand-600/20" : ""}`}
                onClick={() => setSelected(a)}
              >
                <p className="font-medium text-gray-900 dark:text-gray-100">
                  {a.name}
                  {a.is_default ? (
                    <span className="ml-2 text-xs font-normal text-gray-500 dark:text-gray-400">padrão</span>
                  ) : null}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Especialista · {a.active ? "Ativo" : "Inativo"}
                </p>
              </button>
            </li>
          ))}
        </ul>
        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
          {!selected || selected.role === "orchestrator" ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">Selecione um agente para editar o prompt.</p>
          ) : (
            <form key={selected.id} onSubmit={onSavePrompt} className="space-y-3">
              <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-semibold">Editar agente</h3>
                <div className="flex gap-2">
                  {!selected.is_default && (
                    <button
                      type="button"
                      className="btn-secondary text-sm"
                      onClick={async () => {
                        await update(selected.id, { is_default: true });
                        await refresh();
                        setSelected({ ...selected, is_default: true });
                      }}
                    >
                      Tornar padrão
                    </button>
                  )}
                  {!selected.is_default && (
                    <button type="button" className="text-sm text-red-600 dark:text-red-400" onClick={() => setDeleteOpen(true)}>
                      Remover
                    </button>
                  )}
                </div>
              </div>
              <input name="agent_name" className="input-field w-full" defaultValue={selected.name} />
              <input
                name="agent_desc"
                className="input-field w-full"
                defaultValue={selected.description}
                placeholder="Descrição (usada pelo orquestrador para rotear)"
              />
              <textarea
                name="agent_prompt"
                className="input-field min-h-[220px] w-full font-mono text-xs"
                defaultValue={selected.system_prompt}
              />
              <button type="submit" className="btn-primary" disabled={saving}>
                {saving ? "Salvando…" : "Salvar"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

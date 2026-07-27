"use client";

import { FormEvent, useEffect, useState } from "react";
import type { CustomField } from "@/lib/crm-types";

const DEFAULT_FIELDS = [
  {
    key: "phone",
    aliases: ["telefone", "phone"],
    label: "Telefone",
    help: "Chave canônica do contato (identidade). Sempre presente.",
  },
  {
    key: "nome",
    aliases: ["nome", "name"],
    label: "Nome",
    help: "Nome do contato. Preenchido pela conversa, webhook ou edição manual.",
  },
  {
    key: "email",
    aliases: ["email"],
    label: "Email",
    help: "Email do contato. Disponível em prompts e integrações.",
  },
] as const;

type Props = {
  load: () => Promise<{ fields: CustomField[] }>;
  create: (data: { key: string; label: string; field_type?: string; required?: boolean }) => Promise<CustomField>;
  remove: (id: number) => Promise<unknown>;
};

export function FieldsManager({ load, create, remove }: Props) {
  const [fields, setFields] = useState<CustomField[]>([]);
  const [key, setKey] = useState("");
  const [label, setLabel] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function refresh() {
    const data = await load();
    setFields(data.fields || []);
  }

  useEffect(() => {
    refresh()
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await create({ key, label: label || key, field_type: "text" });
      setKey("");
      setLabel("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro");
    }
  }

  async function onDelete(id: number) {
    if (!confirm("Remover este campo?")) return;
    await remove(id);
    await refresh();
  }

  if (loading) return <p className="text-sm text-gray-500 dark:text-gray-400">Carregando…</p>;

  return (
    <div className="space-y-8">
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      <section className="space-y-3">
        <div>
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Campos padrão</h2>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Já existem em todo contato. Não precisam ser criados e não podem ser removidos. Use nas
            integrações com <code className="text-xs">{"{{chave}}"}</code>.
          </p>
        </div>
        <ul className="divide-y divide-gray-100 rounded-lg border border-gray-200 bg-white dark:divide-gray-800 dark:border-gray-800 dark:bg-gray-900">
          {DEFAULT_FIELDS.map((f) => (
            <li key={f.key} className="flex items-start justify-between gap-3 px-4 py-3">
              <div>
                <p className="font-medium text-gray-900 dark:text-gray-100">{f.label}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {f.aliases.map((a, i) => (
                    <span key={a}>
                      {i > 0 ? " · " : ""}
                      <code>{`{{${a}}}`}</code>
                    </span>
                  ))}
                  {" · "}padrão do sistema
                </p>
                <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">{f.help}</p>
              </div>
              <span className="shrink-0 rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600 dark:bg-gray-900 dark:text-gray-300">
                Fixo
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Campos personalizados</h2>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Crie campos extras do seu negócio (CPF, unidade, convênio, etc.). A chave não pode
            repetir os padrões acima.
          </p>
        </div>
        <form
          onSubmit={onCreate}
          className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-white p-4 sm:flex-row sm:items-end dark:border-gray-800 dark:bg-gray-900"
        >
          <label className="flex-1 text-sm">
            <span className="mb-1 block text-gray-600 dark:text-gray-300">Chave (ex.: cpf)</span>
            <input
              className="input-field w-full"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              required
              pattern="[a-z][a-z0-9_]*"
              placeholder="cpf"
            />
          </label>
          <label className="flex-1 text-sm">
            <span className="mb-1 block text-gray-600 dark:text-gray-300">Rótulo</span>
            <input
              className="input-field w-full"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="CPF"
            />
          </label>
          <button type="submit" className="btn-primary">
            Adicionar
          </button>
        </form>
        <ul className="divide-y divide-gray-100 rounded-lg border border-gray-200 bg-white dark:divide-gray-800 dark:border-gray-800 dark:bg-gray-900">
          {fields.length === 0 && (
            <li className="p-4 text-sm text-gray-500 dark:text-gray-400">Nenhum campo personalizado ainda.</li>
          )}
          {fields.map((f) => (
            <li key={f.id} className="flex items-center justify-between gap-3 px-4 py-3">
              <div>
                <p className="font-medium text-gray-900 dark:text-gray-100">{f.label}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  <code>{`{{${f.key}}}`}</code> · {f.field_type}
                  {f.required ? " · obrigatório" : ""}
                </p>
              </div>
              <button type="button" className="btn-secondary text-sm" onClick={() => onDelete(f.id)}>
                Remover
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

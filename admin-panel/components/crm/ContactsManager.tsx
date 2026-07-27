"use client";

import { FormEvent, useEffect, useState } from "react";
import type { Contact, CustomField } from "@/lib/crm-types";

type Props = {
  loadContacts: (q?: string) => Promise<{ contacts: Contact[] }>;
  loadFields: () => Promise<{ fields: CustomField[] }>;
  create: (data: { phone: string; name?: string; email?: string; fields?: Record<string, unknown> }) => Promise<Contact>;
  update: (id: number, data: Partial<{ name: string; email: string; fields: Record<string, unknown> }>) => Promise<Contact>;
  remove: (id: number) => Promise<unknown>;
};

export function ContactsManager({ loadContacts, loadFields, create, update, remove }: Props) {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [fields, setFields] = useState<CustomField[]>([]);
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<Contact | null>(null);
  const [error, setError] = useState("");
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");

  async function refresh(query = q) {
    const [c, f] = await Promise.all([loadContacts(query), loadFields()]);
    setContacts(c.contacts || []);
    setFields(f.fields || []);
  }

  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, []);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await create({ phone, name, email });
      setPhone("");
      setName("");
      setEmail("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro");
    }
  }

  async function onSaveSelected(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    const fieldValues: Record<string, unknown> = { ...(selected.fields || {}) };
    const form = e.target as HTMLFormElement;
    for (const f of fields) {
      const input = form.elements.namedItem(`field_${f.key}`) as HTMLInputElement | null;
      if (input) fieldValues[f.key] = input.value;
    }
    const updated = await update(selected.id, {
      name: (form.elements.namedItem("edit_name") as HTMLInputElement).value,
      email: (form.elements.namedItem("edit_email") as HTMLInputElement).value,
      fields: fieldValues,
    });
    setSelected(updated);
    await refresh();
  }

  return (
    <div className="space-y-6">
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          className="input-field flex-1"
          placeholder="Buscar telefone, nome ou email"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && refresh(q)}
        />
        <button type="button" className="btn-secondary" onClick={() => refresh(q)}>
          Buscar
        </button>
      </div>

      <form onSubmit={onCreate} className="grid gap-3 rounded-lg border border-gray-200 bg-white p-4 sm:grid-cols-4 dark:border-gray-800 dark:bg-gray-900">
        <input className="input-field" placeholder="Telefone" value={phone} onChange={(e) => setPhone(e.target.value)} required />
        <input className="input-field" placeholder="Nome" value={name} onChange={(e) => setName(e.target.value)} />
        <input className="input-field" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <button type="submit" className="btn-primary">
          Novo contato
        </button>
      </form>

      <div className="grid gap-4 lg:grid-cols-2">
        <ul className="max-h-[480px] overflow-auto divide-y divide-gray-100 rounded-lg border border-gray-200 bg-white dark:divide-gray-800 dark:border-gray-800 dark:bg-gray-900">
          {contacts.length === 0 && <li className="p-4 text-sm text-gray-500 dark:text-gray-400">Nenhum contato.</li>}
          {contacts.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                className={`w-full px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-800 ${selected?.id === c.id ? "bg-brand-50 dark:bg-brand-600/20" : ""}`}
                onClick={() => setSelected(c)}
              >
                <p className="font-medium text-gray-900 dark:text-gray-100">{c.name || "Sem nome"}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {c.phone}
                  {c.email ? ` · ${c.email}` : ""}
                </p>
                <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                  {Object.keys(c.fields || {}).length} campo(s) salvos
                </p>
              </button>
            </li>
          ))}
        </ul>

        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
          {!selected ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">Selecione um contato para ver os campos.</p>
          ) : (
            <form onSubmit={onSaveSelected} className="space-y-3">
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-semibold text-gray-900 dark:text-gray-100">{selected.phone}</h3>
                <button
                  type="button"
                  className="text-sm text-red-600 dark:text-red-400"
                  onClick={async () => {
                    if (!confirm("Excluir contato?")) return;
                    await remove(selected.id);
                    setSelected(null);
                    await refresh();
                  }}
                >
                  Excluir
                </button>
              </div>
              <label className="block text-sm">
                Nome
                <input name="edit_name" className="input-field mt-1 w-full" defaultValue={selected.name} key={`n-${selected.id}`} />
              </label>
              <label className="block text-sm">
                Email
                <input name="edit_email" className="input-field mt-1 w-full" defaultValue={selected.email} key={`e-${selected.id}`} />
              </label>
              {fields.map((f) => (
                <label key={f.key} className="block text-sm">
                  {f.label}
                  <input
                    name={`field_${f.key}`}
                    className="input-field mt-1 w-full"
                    defaultValue={String(selected.fields?.[f.key] ?? "")}
                    key={`${selected.id}-${f.key}`}
                  />
                </label>
              ))}
              <button type="submit" className="btn-primary">
                Salvar
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

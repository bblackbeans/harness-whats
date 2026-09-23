"use client";

import { FormEvent, useEffect, useState } from "react";
import type { Contact } from "@/lib/crm-types";

export type Campaign = {
  id: number;
  name: string;
  mode: string;
  template_name: string;
  language: string;
  message: string;
  status: string;
  scheduled_at?: string | null;
  inbox_id?: number | null;
  account_id?: number | null;
  counts?: Record<string, number>;
  recipient_count?: number;
  channel_note?: string;
  error?: string;
  recipients?: Array<{
    id: number;
    phone: string;
    name: string;
    status: string;
    error?: string;
    conversation_id?: number | null;
  }>;
};

type Props = {
  loadCampaigns: () => Promise<{ campaigns: Campaign[] }>;
  getCampaign: (id: number) => Promise<Campaign>;
  createCampaign: (data: Record<string, unknown>) => Promise<Campaign>;
  sendCampaign: (id: number) => Promise<Campaign>;
  scheduleCampaign: (id: number, scheduled_at: string) => Promise<Campaign>;
  cancelCampaign: (id: number) => Promise<Campaign>;
  loadContacts: () => Promise<{ contacts: Contact[] }>;
};

export function CampaignsManager(props: Props) {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [selected, setSelected] = useState<Campaign | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [name, setName] = useState("Campanha WhatsApp");
  const [mode, setMode] = useState<"template" | "conversation">("template");
  const [templateName, setTemplateName] = useState("");
  const [language, setLanguage] = useState("pt_BR");
  const [message, setMessage] = useState("");
  const [inboxId, setInboxId] = useState("");
  const [selectedContactIds, setSelectedContactIds] = useState<number[]>([]);
  const [extraPhones, setExtraPhones] = useState("");
  const [scheduleAt, setScheduleAt] = useState("");

  async function refresh() {
    const [c, k] = await Promise.all([props.loadCampaigns(), props.loadContacts()]);
    setCampaigns(c.campaigns || []);
    setContacts(k.contacts || []);
  }

  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, []);

  function toggleContact(id: number) {
    setSelectedContactIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const phones = extraPhones
        .split(/[\n,;]+/)
        .map((s) => s.trim())
        .filter(Boolean);
      const created = await props.createCampaign({
        name,
        mode,
        template_name: templateName,
        language,
        message,
        inbox_id: inboxId.trim() ? Number(inboxId) : undefined,
        contact_ids: selectedContactIds,
        phones,
      });
      setSelected(created);
      setSelectedContactIds([]);
      setExtraPhones("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar campanha");
    } finally {
      setBusy(false);
    }
  }

  async function openCampaign(id: number) {
    setError("");
    try {
      const full = await props.getCampaign(id);
      setSelected(full);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar");
    }
  }

  async function onSend() {
    if (!selected) return;
    if (!confirm("Enviar campanha agora? Fora da janela 24h use template Meta aprovado.")) return;
    setBusy(true);
    setError("");
    try {
      const updated = await props.sendCampaign(selected.id);
      setSelected(updated);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro no envio");
    } finally {
      setBusy(false);
    }
  }

  async function onSchedule() {
    if (!selected || !scheduleAt) return;
    setBusy(true);
    setError("");
    try {
      const iso = new Date(scheduleAt).toISOString();
      const updated = await props.scheduleCampaign(selected.id, iso);
      setSelected(updated);
      setScheduleAt("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao agendar");
    } finally {
      setBusy(false);
    }
  }

  async function onCancel() {
    if (!selected) return;
    setBusy(true);
    try {
      const updated = await props.cancelCampaign(selected.id);
      setSelected(updated);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao cancelar");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-100">
        Disparo WhatsApp via Chatwoot exige <strong>inbox WhatsApp Cloud (API oficial Meta)</strong> e{" "}
        <strong>templates aprovados</strong> no Meta Business Manager para iniciar conversa / fora da
        janela de 24h. Configure <code className="text-xs">chatwoot_inbox_ids</code> do cliente.
      </div>

      <form
        onSubmit={onCreate}
        className="space-y-3 rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900"
      >
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Nova campanha</h2>
        <input
          className="input-field w-full"
          placeholder="Nome da campanha"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            Modo
            <select
              className="input-field mt-1 w-full"
              value={mode}
              onChange={(e) => setMode(e.target.value as "template" | "conversation")}
            >
              <option value="template">Template Meta (oficial)</option>
              <option value="conversation">Texto livre (só janela 24h)</option>
            </select>
          </label>
          <label className="block text-sm">
            Inbox ID (WhatsApp Cloud)
            <input
              className="input-field mt-1 w-full"
              placeholder="Opcional se já configurado no cliente"
              value={inboxId}
              onChange={(e) => setInboxId(e.target.value)}
            />
          </label>
        </div>
        {mode === "template" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              Nome do template Meta
              <input
                className="input-field mt-1 w-full"
                placeholder="ex.: boas_vindas"
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
                required
              />
            </label>
            <label className="block text-sm">
              Idioma
              <input
                className="input-field mt-1 w-full"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
              />
            </label>
          </div>
        ) : (
          <label className="block text-sm">
            Mensagem
            <textarea
              className="input-field mt-1 w-full"
              rows={3}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              required
            />
          </label>
        )}

        <div>
          <p className="mb-2 text-sm font-medium text-gray-700 dark:text-gray-200">
            Contatos do CRM ({selectedContactIds.length} selecionados)
          </p>
          <ul className="max-h-40 space-y-1 overflow-y-auto rounded border border-gray-200 p-2 dark:border-gray-800">
            {contacts.length === 0 && (
              <li className="text-sm text-gray-500">Nenhum contato. Cadastre em Contatos.</li>
            )}
            {contacts.map((c) => (
              <li key={c.id}>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selectedContactIds.includes(c.id)}
                    onChange={() => toggleContact(c.id)}
                  />
                  <span>
                    {c.name || "Sem nome"} · {c.phone}
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </div>

        <label className="block text-sm">
          Telefones extras (um por linha)
          <textarea
            className="input-field mt-1 w-full font-mono text-xs"
            rows={3}
            placeholder="5511999999999"
            value={extraPhones}
            onChange={(e) => setExtraPhones(e.target.value)}
          />
        </label>

        <button type="submit" className="btn-primary" disabled={busy}>
          Criar campanha
        </button>
      </form>

      <div className="grid gap-4 lg:grid-cols-2">
        <ul className="space-y-2">
          {campaigns.length === 0 && (
            <li className="text-sm text-gray-500 dark:text-gray-400">Nenhuma campanha.</li>
          )}
          {campaigns.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => openCampaign(c.id)}
                className={`w-full rounded-lg border px-3 py-2 text-left text-sm ${
                  selected?.id === c.id
                    ? "border-brand-500 bg-brand-50 dark:border-brand-400 dark:bg-brand-950/40"
                    : "border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900"
                }`}
              >
                <span className="font-medium text-gray-900 dark:text-gray-100">{c.name}</span>
                <span className="mt-0.5 block text-xs text-gray-500">
                  {c.status} · {c.mode}
                  {c.template_name ? ` · ${c.template_name}` : ""} · {c.recipient_count ?? 0} dest.
                </span>
              </button>
            </li>
          ))}
        </ul>

        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
          {!selected ? (
            <p className="text-sm text-gray-500">Selecione uma campanha.</p>
          ) : (
            <div className="space-y-3">
              <h3 className="font-semibold text-gray-900 dark:text-gray-100">{selected.name}</h3>
              <p className="text-sm text-gray-600 dark:text-gray-300">
                Status: <strong>{selected.status}</strong>
                {selected.scheduled_at ? ` · agendada ${selected.scheduled_at}` : ""}
              </p>
              {selected.error && (
                <p className="text-sm text-red-600 dark:text-red-400">{selected.error}</p>
              )}
              <p className="text-xs text-gray-500">
                enviados {selected.counts?.sent ?? 0} · falhas {selected.counts?.failed ?? 0} ·
                pendentes {selected.counts?.pending ?? 0}
              </p>

              <div className="flex flex-wrap gap-2">
                {(selected.status === "draft" ||
                  selected.status === "scheduled" ||
                  selected.status === "failed") && (
                  <button type="button" className="btn-primary" disabled={busy} onClick={onSend}>
                    Enviar agora
                  </button>
                )}
                {(selected.status === "draft" || selected.status === "failed") && (
                  <>
                    <input
                      type="datetime-local"
                      className="input-field"
                      value={scheduleAt}
                      onChange={(e) => setScheduleAt(e.target.value)}
                    />
                    <button
                      type="button"
                      className="btn-secondary"
                      disabled={busy || !scheduleAt}
                      onClick={onSchedule}
                    >
                      Agendar
                    </button>
                  </>
                )}
                {(selected.status === "draft" || selected.status === "scheduled") && (
                  <button type="button" className="btn-secondary" disabled={busy} onClick={onCancel}>
                    Cancelar
                  </button>
                )}
              </div>

              <ul className="max-h-56 space-y-1 overflow-y-auto text-xs">
                {(selected.recipients || []).map((r) => (
                  <li
                    key={r.id}
                    className="rounded border border-gray-100 px-2 py-1 dark:border-gray-800"
                  >
                    {r.name || "—"} · {r.phone} · <strong>{r.status}</strong>
                    {r.conversation_id ? ` · conv #${r.conversation_id}` : ""}
                    {r.error ? ` · ${r.error}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

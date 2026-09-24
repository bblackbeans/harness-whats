"use client";

import { FormEvent, useEffect, useState } from "react";
import { Modal } from "@/components/Modal";
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
  deleteCampaign: (id: number) => Promise<unknown>;
  loadContacts: () => Promise<{ contacts: Contact[] }>;
};

export function CampaignsManager(props: Props) {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [selected, setSelected] = useState<Campaign | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<Campaign | null>(null);
  const [sendOpen, setSendOpen] = useState(false);

  const [name, setName] = useState("Campanha WhatsApp");
  const [mode, setMode] = useState<"template" | "conversation">("template");
  const [templateName, setTemplateName] = useState("");
  const [language, setLanguage] = useState("pt_BR");
  const [message, setMessage] = useState("");
  const [inboxId, setInboxId] = useState("");
  const [selectedContactIds, setSelectedContactIds] = useState<number[]>([]);
  const [extraPhones, setExtraPhones] = useState("");
  const [scheduleAt, setScheduleAt] = useState("");
  const [contactFilter, setContactFilter] = useState("");

  const filteredContacts = contacts.filter((c) => {
    const q = contactFilter.trim().toLowerCase();
    if (!q) return true;
    const digits = q.replace(/\D/g, "");
    const hay = `${c.name || ""} ${c.phone || ""} ${c.email || ""}`.toLowerCase();
    if (hay.includes(q)) return true;
    if (digits && (c.phone || "").includes(digits)) return true;
    return false;
  });

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

  function askSend() {
    if (!selected) return;
    setSendOpen(true);
  }

  async function confirmSend() {
    if (!selected) return;
    setSendOpen(false);
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

  function askDelete(campaign: Campaign) {
    setPendingDelete(campaign);
    setDeleteOpen(true);
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    setBusy(true);
    setError("");
    try {
      await props.deleteCampaign(pendingDelete.id);
      if (selected?.id === pendingDelete.id) setSelected(null);
      setDeleteOpen(false);
      setPendingDelete(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao excluir");
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
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-medium text-gray-700 dark:text-gray-200">
              Contatos do CRM ({selectedContactIds.length} selecionados
              {contactFilter.trim() ? ` · ${filteredContacts.length} filtrados` : ""} /{" "}
              {contacts.length})
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="btn-secondary text-xs"
                onClick={() =>
                  setSelectedContactIds((prev) => {
                    const ids = filteredContacts.map((c) => c.id);
                    const allSelected = ids.length > 0 && ids.every((id) => prev.includes(id));
                    if (allSelected) {
                      return prev.filter((id) => !ids.includes(id));
                    }
                    return Array.from(new Set([...prev, ...ids]));
                  })
                }
              >
                {filteredContacts.length > 0 &&
                filteredContacts.every((c) => selectedContactIds.includes(c.id))
                  ? "Limpar filtrados"
                  : "Selecionar filtrados"}
              </button>
              <button
                type="button"
                className="btn-secondary text-xs"
                onClick={() =>
                  setSelectedContactIds(
                    selectedContactIds.length === contacts.length ? [] : contacts.map((c) => c.id)
                  )
                }
              >
                {selectedContactIds.length === contacts.length && contacts.length > 0
                  ? "Limpar todos"
                  : "Selecionar todos"}
              </button>
            </div>
          </div>
          <input
            className="input-field mb-2 w-full"
            placeholder="Pesquisar por nome ou número"
            value={contactFilter}
            onChange={(e) => setContactFilter(e.target.value)}
          />
          <ul className="max-h-56 space-y-1 overflow-y-auto rounded border border-gray-200 p-2 dark:border-gray-800">
            {contacts.length === 0 && (
              <li className="text-sm text-gray-500">
                Nenhum contato. Use Contatos → Atualizar do Chatwoot.
              </li>
            )}
            {contacts.length > 0 && filteredContacts.length === 0 && (
              <li className="text-sm text-gray-500">Nenhum contato com esse filtro.</li>
            )}
            {filteredContacts.map((c) => (
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
          {campaigns.map((c) => {
            const isSelected = selected?.id === c.id;
            return (
              <li key={c.id} className="flex gap-2">
                <button
                  type="button"
                  onClick={() => openCampaign(c.id)}
                  className={`min-w-0 flex-1 rounded-lg border px-3 py-2 text-left text-sm ${
                    isSelected
                      ? "border-brand-600 bg-brand-100 text-gray-900 dark:border-brand-400 dark:bg-brand-800 dark:text-white"
                      : "border-gray-200 bg-white text-gray-900 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-100"
                  }`}
                >
                  <span className="block font-medium text-inherit">{c.name}</span>
                  <span
                    className={`mt-0.5 block text-xs ${
                      isSelected
                        ? "text-gray-800 dark:text-gray-100"
                        : "text-gray-500 dark:text-gray-400"
                    }`}
                  >
                    {c.status} · {c.mode}
                    {c.template_name ? ` · ${c.template_name}` : ""} · {c.recipient_count ?? 0} dest.
                  </span>
                </button>
                <button
                  type="button"
                  className="btn-secondary shrink-0 self-stretch px-3 text-xs text-red-600 dark:text-red-400"
                  disabled={busy || c.status === "running"}
                  title={c.status === "running" ? "Aguarde a campanha terminar" : "Excluir"}
                  onClick={() => askDelete(c)}
                >
                  Excluir
                </button>
              </li>
            );
          })}
        </ul>

        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
          {!selected ? (
            <p className="text-sm text-gray-500">Selecione uma campanha.</p>
          ) : (
            <div className="space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <h3 className="font-semibold text-gray-900 dark:text-gray-100">{selected.name}</h3>
                <button
                  type="button"
                  className="btn-secondary text-xs text-red-600 dark:text-red-400"
                  disabled={busy || selected.status === "running"}
                  onClick={() => askDelete(selected)}
                >
                  Excluir campanha
                </button>
              </div>
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
                  <button type="button" className="btn-primary" disabled={busy} onClick={askSend}>
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

      <Modal
        open={sendOpen}
        title="Enviar campanha agora?"
        message={
          selected
            ? `Confirma o envio de "${selected.name}" para ${selected.recipient_count ?? selected.recipients?.length ?? 0} destinatário(s)? Fora da janela de 24h use template Meta aprovado.`
            : ""
        }
        confirmLabel="Enviar agora"
        cancelLabel="Voltar"
        onConfirm={confirmSend}
        onCancel={() => setSendOpen(false)}
      />

      <Modal
        open={deleteOpen}
        title="Excluir campanha?"
        message={
          pendingDelete
            ? `Tem certeza que deseja excluir "${pendingDelete.name}"? Esta ação não pode ser desfeita.`
            : ""
        }
        confirmLabel="Excluir"
        cancelLabel="Manter"
        danger
        onConfirm={confirmDelete}
        onCancel={() => {
          setDeleteOpen(false);
          setPendingDelete(null);
        }}
      />
    </div>
  );
}

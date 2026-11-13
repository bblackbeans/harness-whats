"use client";

import { FormEvent, useEffect, useState } from "react";
import { Modal } from "@/components/Modal";
import type { Contact } from "@/lib/crm-types";
import type { MetaTemplate, RecurringCampaign } from "@/lib/portal-api";
import { WhatsAppPreview } from "@/components/crm/WhatsAppPreview";

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
  header_image_url?: string;
  error?: string;
  created_at?: string | null;
  recipients?: Array<{
    id: number;
    phone: string;
    name: string;
    status: string;
    error?: string;
    conversation_id?: number | null;
  }>;
};

const STATUS_META: Record<string, { label: string; badge: string }> = {
  draft: {
    label: "Rascunho",
    badge: "bg-gray-100 text-gray-700 ring-gray-500/20 dark:bg-gray-800 dark:text-gray-200 dark:ring-gray-600",
  },
  scheduled: {
    label: "Agendada",
    badge: "bg-blue-50 text-blue-700 ring-blue-600/20 dark:bg-blue-950 dark:text-blue-300 dark:ring-blue-500/30",
  },
  running: {
    label: "Enviando",
    badge: "bg-amber-50 text-amber-800 ring-amber-600/20 dark:bg-amber-950 dark:text-amber-300 dark:ring-amber-500/30",
  },
  completed: {
    label: "Concluída",
    badge: "bg-green-50 text-green-700 ring-green-600/20 dark:bg-green-950 dark:text-green-300 dark:ring-green-500/30",
  },
  failed: {
    label: "Falhou",
    badge: "bg-red-50 text-red-700 ring-red-600/20 dark:bg-red-950 dark:text-red-300 dark:ring-red-500/30",
  },
  cancelled: {
    label: "Cancelada",
    badge: "bg-gray-100 text-gray-500 ring-gray-400/20 dark:bg-gray-800 dark:text-gray-400 dark:ring-gray-600",
  },
};

const RECIPIENT_META: Record<string, string> = {
  pending: "Pendente",
  sent: "Enviado",
  failed: "Falhou",
  skipped: "Ignorado",
};

const FILTERS: Array<{ key: string; label: string }> = [
  { key: "all", label: "Todas" },
  { key: "draft", label: "Rascunhos" },
  { key: "scheduled", label: "Agendadas" },
  { key: "running", label: "Enviando" },
  { key: "completed", label: "Concluídas" },
  { key: "failed", label: "Falhas" },
];

const PAGE_SIZE = 10;

function statusMeta(status: string) {
  return STATUS_META[status] ?? { label: status, badge: STATUS_META.draft.badge };
}

function fmtDate(iso?: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function StatusBadge({ status }: { status: string }) {
  const m = statusMeta(status);
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${m.badge}`}
    >
      {m.label}
    </span>
  );
}

function Guide({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  const steps = [
    {
      t: "Sincronize os contatos",
      d: "Em Contatos, use “Atualizar do Chatwoot”. Só contatos com telefone entram na lista.",
    },
    {
      t: "Tenha um template aprovado",
      d: "Fora da janela de 24h só funciona template aprovado na Meta. Copie o nome exato e o idioma (ex.: pt_BR).",
    },
    {
      t: "Imagem no cabeçalho (se houver)",
      d: "Se o template foi aprovado com imagem, informe um link público https (.jpg/.png, até 5 MB).",
    },
    {
      t: "Crie, revise e envie",
      d: "Selecione os destinatários, crie a campanha (fica como rascunho), confira os números e envie agora ou agende.",
    },
  ];
  return (
    <div className="rounded-lg border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left text-sm font-semibold text-gray-900 dark:text-gray-100"
        aria-expanded={open}
      >
        <span>Como fazer um disparo</span>
        <span className="text-xs font-normal text-gray-500 dark:text-gray-400">
          {open ? "Ocultar" : "Mostrar"}
        </span>
      </button>
      {open && (
        <div className="space-y-4 border-t border-gray-200 px-4 py-4 dark:border-gray-800">
          <ol className="grid gap-3 sm:grid-cols-2">
            {steps.map((st, i) => (
              <li key={st.t} className="flex gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-600 text-xs font-semibold text-white">
                  {i + 1}
                </span>
                <span className="text-sm text-gray-600 dark:text-gray-300">
                  <strong className="block text-gray-900 dark:text-gray-100">{st.t}</strong>
                  {st.d}
                </span>
              </li>
            ))}
          </ol>
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-100">
            Requer <strong>inbox WhatsApp Cloud (API oficial Meta)</strong> configurada em{" "}
            <code>chatwoot_inbox_ids</code> do cliente. Variáveis do CRM não são enviadas como
            parâmetros do template: use templates sem variáveis ou com texto fixo.
            O modo “Texto livre” só entrega a quem falou com você nas últimas 24h.
          </div>
        </div>
      )}
    </div>
  );
}

type Props = {
  loadCampaigns: () => Promise<{ campaigns: Campaign[] }>;
  getCampaign: (id: number) => Promise<Campaign>;
  createCampaign: (data: Record<string, unknown>) => Promise<Campaign>;
  sendCampaign: (id: number) => Promise<Campaign>;
  scheduleCampaign: (id: number, scheduled_at: string) => Promise<Campaign>;
  cancelCampaign: (id: number) => Promise<Campaign>;
  deleteCampaign: (id: number) => Promise<unknown>;
  loadContacts: () => Promise<{ contacts: Contact[] }>;
  /** Opcional: habilita lista de templates com pré-visualização. */
  loadTemplates?: () => Promise<{ ok: boolean; error?: string; templates: MetaTemplate[] }>;
  /** Opcional: habilita disparos recorrentes mensais. */
  recurring?: {
    list: () => Promise<{ schedules: RecurringCampaign[] }>;
    create: (data: Record<string, unknown>) => Promise<RecurringCampaign>;
    toggle: (id: number, active: boolean) => Promise<RecurringCampaign>;
    run: (id: number) => Promise<unknown>;
    remove: (id: number) => Promise<unknown>;
  };
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
  const [formOpen, setFormOpen] = useState(false);
  const [guideOpen, setGuideOpen] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [visible, setVisible] = useState(PAGE_SIZE);
  const [recipientFilter, setRecipientFilter] = useState("all");
  const [templates, setTemplates] = useState<MetaTemplate[]>([]);
  const [templatesError, setTemplatesError] = useState("");
  const [schedules, setSchedules] = useState<RecurringCampaign[]>([]);
  const [repeatMonthly, setRepeatMonthly] = useState(false);
  const [repeatDay, setRepeatDay] = useState(1);
  const [repeatTime, setRepeatTime] = useState("09:00");
  const [allContacts, setAllContacts] = useState(false);
  const [notice, setNotice] = useState("");
  const [runNow, setRunNow] = useState<RecurringCampaign | null>(null);
  const [deleteSchedule, setDeleteSchedule] = useState<RecurringCampaign | null>(null);

  const [name, setName] = useState("Campanha WhatsApp");
  const [mode, setMode] = useState<"template" | "conversation">("template");
  const [templateName, setTemplateName] = useState("");
  const [language, setLanguage] = useState("pt_BR");
  const [headerImageUrl, setHeaderImageUrl] = useState("");
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

  const filteredCampaigns = campaigns.filter((c) => {
    if (statusFilter !== "all" && c.status !== statusFilter) return false;
    const q = search.trim().toLowerCase();
    return !q || `${c.name} ${c.template_name}`.toLowerCase().includes(q);
  });

  async function refresh() {
    const [c, k] = await Promise.all([props.loadCampaigns(), props.loadContacts()]);
    setCampaigns(c.campaigns || []);
    if ((c.campaigns || []).length > 0) setGuideOpen(false);
    setContacts(k.contacts || []);
    if (props.recurring) {
      props.recurring
        .list()
        .then((r) => setSchedules(r.schedules || []))
        .catch(() => undefined);
    }
  }

  useEffect(() => {
    refresh().catch((e) => setError(e.message));
    props
      .loadTemplates?.()
      .then((r) => {
        setTemplates(r.templates || []);
        if (!r.ok) setTemplatesError(r.error || "Não foi possível listar templates.");
      })
      .catch((e) => setTemplatesError(e.message));
  }, []);

  const selectedTemplate =
    templates.find((t) => t.name === templateName && t.language === language) ||
    templates.find((t) => t.name === templateName) ||
    null;
  const approvedTemplates = templates.filter((t) => !t.status || t.status === "approved");

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
      if (repeatMonthly && props.recurring) {
        const [hh, mm] = repeatTime.split(":").map(Number);
        await props.recurring.create({
          name,
          mode,
          template_name: templateName,
          language,
          message,
          header_image_url: mode === "template" ? headerImageUrl.trim() : "",
          inbox_id: inboxId.trim() ? Number(inboxId) : undefined,
          contact_ids: allContacts ? [] : selectedContactIds,
          all_contacts: allContacts,
          phones,
          day_of_month: repeatDay,
          hour: hh,
          minute: mm,
        });
        setSelectedContactIds([]);
        setExtraPhones("");
        setHeaderImageUrl("");
        setRepeatMonthly(false);
        setFormOpen(false);
        setNotice("Disparo mensal criado. Veja “Disparos recorrentes” abaixo.");
        await refresh();
        return;
      }
      const created = await props.createCampaign({
        name,
        mode,
        template_name: templateName,
        language,
        message,
        header_image_url: mode === "template" ? headerImageUrl.trim() : "",
        inbox_id: inboxId.trim() ? Number(inboxId) : undefined,
        contact_ids: selectedContactIds,
        phones,
      });
      setSelected(created);
      setSelectedContactIds([]);
      setExtraPhones("");
      setHeaderImageUrl("");
      setFormOpen(false);
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
    <div className="space-y-5">
      {error && (
        <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </p>
      )}

      {notice && (
        <p className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800 dark:border-green-900/50 dark:bg-green-950/40 dark:text-green-300">
          {notice}
        </p>
      )}

      <Guide open={guideOpen} onToggle={() => setGuideOpen((v) => !v)} />

      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          Campanhas <span className="text-sm font-normal text-gray-500">({campaigns.length})</span>
        </h2>
        <button type="button" className="btn-primary" onClick={() => setFormOpen((v) => !v)}>
          {formOpen ? "Fechar formulário" : "+ Nova campanha"}
        </button>
      </div>

      {formOpen && (
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
              Template Meta
              {approvedTemplates.length > 0 ? (
                <select
                  className="input-field mt-1 w-full"
                  value={selectedTemplate ? `${selectedTemplate.name}|${selectedTemplate.language}` : ""}
                  onChange={(e) => {
                    const [n, l] = e.target.value.split("|");
                    setTemplateName(n || "");
                    if (l) setLanguage(l);
                  }}
                  required
                >
                  <option value="">Selecione um template aprovado</option>
                  {approvedTemplates.map((t) => (
                    <option key={`${t.name}|${t.language}`} value={`${t.name}|${t.language}`}>
                      {t.name} ({t.language})
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  className="input-field mt-1 w-full"
                  placeholder="ex.: boas_vindas"
                  value={templateName}
                  onChange={(e) => setTemplateName(e.target.value)}
                  required
                />
              )}
              {templatesError && (
                <span className="mt-1 block text-xs text-amber-700 dark:text-amber-300">
                  Lista de templates indisponível ({templatesError.slice(0, 80)}). Digite o nome
                  exato.
                </span>
              )}
            </label>
            <label className="block text-sm">
              Idioma
              <input
                className="input-field mt-1 w-full"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
              />
            </label>
            <label className="block text-sm sm:col-span-2">
              URL da imagem do cabeçalho (opcional)
              <input
                type="url"
                className="input-field mt-1 w-full"
                placeholder="https://site.com/imagem.jpg"
                value={headerImageUrl}
                onChange={(e) => setHeaderImageUrl(e.target.value)}
              />
              <span className="mt-1 block text-xs text-gray-500 dark:text-gray-400">
                Obrigatório se o template foi aprovado com imagem no cabeçalho. Link público direto
                https (.jpg/.png, até 5 MB).
              </span>
            </label>
            {selectedTemplate && (
              <div className="sm:col-span-2">
                <p className="mb-1 text-sm font-medium text-gray-700 dark:text-gray-200">
                  Pré-visualização
                </p>
                <WhatsAppPreview template={selectedTemplate} imageUrl={headerImageUrl.trim()} />
              </div>
            )}
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

        {props.recurring && (
          <div className="rounded-lg border border-gray-200 p-3 dark:border-gray-800">
            <label className="flex items-center gap-2 text-sm font-medium text-gray-900 dark:text-gray-100">
              <input
                type="checkbox"
                checked={repeatMonthly}
                onChange={(e) => setRepeatMonthly(e.target.checked)}
              />
              Repetir todo mês (disparo automático)
            </label>
            {repeatMonthly && (
              <div className="mt-3 space-y-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="block text-sm">
                    Dia do mês
                    <input
                      type="number"
                      min={1}
                      max={31}
                      className="input-field mt-1 w-full"
                      value={repeatDay}
                      onChange={(e) => setRepeatDay(Number(e.target.value))}
                    />
                  </label>
                  <label className="block text-sm">
                    Horário (Brasília)
                    <input
                      type="time"
                      className="input-field mt-1 w-full"
                      value={repeatTime}
                      onChange={(e) => setRepeatTime(e.target.value)}
                    />
                  </label>
                </div>
                <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-200">
                  <input
                    type="checkbox"
                    checked={allContacts}
                    onChange={(e) => setAllContacts(e.target.checked)}
                  />
                  Enviar para todos os contatos do CRM no dia (lista atualizada a cada mês)
                </label>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Dias 29–31 enviam no último dia dos meses mais curtos. Sem marcar “todos”, vale a
                  seleção acima.
                </p>
              </div>
            )}
          </div>
        )}

        <button type="submit" className="btn-primary" disabled={busy}>
          {repeatMonthly ? "Criar disparo mensal" : "Criar campanha"}
        </button>
      </form>
      )}

      {props.recurring && schedules.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Disparos recorrentes{" "}
            <span className="text-sm font-normal text-gray-500">({schedules.length})</span>
          </h2>
          <ul className="space-y-2">
            {schedules.map((r) => (
              <li
                key={r.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-gray-200 bg-white px-3 py-2.5 dark:border-gray-800 dark:bg-gray-900"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-gray-900 dark:text-gray-100">
                    {r.name}{" "}
                    <span
                      className={`ml-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                        r.active
                          ? "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300"
                          : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300"
                      }`}
                    >
                      {r.active ? "Ativo" : "Pausado"}
                    </span>
                  </p>
                  <p className="text-xs text-gray-600 dark:text-gray-400">
                    {r.template_name || "texto livre"} · todo dia {r.day_of_month} às{" "}
                    {String(r.hour).padStart(2, "0")}:{String(r.minute).padStart(2, "0")} ·{" "}
                    {r.all_contacts ? "todos os contatos" : `${r.recipient_count} dest.`}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {r.active && r.next_run_at ? `Próxima: ${fmtDate(r.next_run_at)}` : "Sem próxima execução"}
                    {r.last_run_at ? ` · Última: ${fmtDate(r.last_run_at)}` : ""}
                  </p>
                  {r.last_error && (
                    <p className="text-xs text-red-600 dark:text-red-400">{r.last_error}</p>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="btn-secondary text-xs"
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true);
                      try {
                        await props.recurring!.toggle(r.id, !r.active);
                        await refresh();
                      } catch (e) {
                        setError(e instanceof Error ? e.message : "Erro");
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    {r.active ? "Pausar" : "Retomar"}
                  </button>
                  <button
                    type="button"
                    className="btn-secondary text-xs"
                    disabled={busy}
                    onClick={() => setRunNow(r)}
                  >
                    Executar agora
                  </button>
                  <button
                    type="button"
                    className="btn-secondary text-xs !text-red-600 dark:!text-red-400"
                    disabled={busy}
                    onClick={() => setDeleteSchedule(r)}
                  >
                    Excluir
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <div className="space-y-3">
          <input
            className="input-field"
            placeholder="Pesquisar campanha ou template"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setVisible(PAGE_SIZE);
            }}
          />
          <div className="flex flex-wrap gap-1.5">
            {FILTERS.map((f) => {
              const n =
                f.key === "all"
                  ? campaigns.length
                  : campaigns.filter((c) => c.status === f.key).length;
              const active = statusFilter === f.key;
              return (
                <button
                  key={f.key}
                  type="button"
                  onClick={() => {
                    setStatusFilter(f.key);
                    setVisible(PAGE_SIZE);
                  }}
                  className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                    active
                      ? "border-brand-600 bg-brand-600 text-white"
                      : "border-gray-300 bg-white text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:bg-gray-800"
                  }`}
                >
                  {f.label} · {n}
                </button>
              );
            })}
          </div>

          <ul className="max-h-[70vh] space-y-2 overflow-y-auto pr-1">
            {filteredCampaigns.length === 0 && (
              <li className="rounded-lg border border-dashed border-gray-300 px-3 py-6 text-center text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
                {campaigns.length === 0
                  ? "Nenhuma campanha ainda. Clique em “+ Nova campanha”."
                  : "Nenhuma campanha com esse filtro."}
              </li>
            )}
            {filteredCampaigns.slice(0, visible).map((c) => {
              const isSelected = selected?.id === c.id;
              const total = c.recipient_count ?? 0;
              const sent = c.counts?.sent ?? 0;
              const failed = c.counts?.failed ?? 0;
              const pct = total ? Math.round(((sent + failed) / total) * 100) : 0;
              return (
                <li key={c.id} className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => openCampaign(c.id)}
                    className={`min-w-0 flex-1 rounded-lg border px-3 py-2.5 text-left transition ${
                      isSelected
                        ? "border-brand-500 bg-brand-50 ring-2 ring-brand-500/40 dark:bg-brand-500/15"
                        : "border-gray-200 bg-white hover:border-gray-300 dark:border-gray-800 dark:bg-gray-900 dark:hover:border-gray-700"
                    }`}
                  >
                    <span className="flex items-start justify-between gap-2">
                      <span className="min-w-0 truncate text-sm font-semibold text-gray-900 dark:text-gray-100">
                        {c.name || `Campanha #${c.id}`}
                      </span>
                      <StatusBadge status={c.status} />
                    </span>
                    <span className="mt-1 block truncate text-xs text-gray-600 dark:text-gray-400">
                      {c.mode === "template" ? c.template_name || "template" : "texto livre"}
                      {c.header_image_url ? " · com imagem" : ""} · {total} dest.
                      {c.created_at ? ` · ${fmtDate(c.created_at)}` : ""}
                    </span>
                    {total > 0 && c.status !== "draft" && (
                      <span className="mt-2 block h-1.5 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-800">
                        <span
                          className={`block h-full ${failed ? "bg-amber-500" : "bg-green-500"}`}
                          style={{ width: `${pct}%` }}
                        />
                      </span>
                    )}
                  </button>
                  <button
                    type="button"
                    className="btn-secondary shrink-0 self-stretch px-3 text-xs !text-red-600 dark:!text-red-400"
                    disabled={busy || c.status === "running"}
                    title={c.status === "running" ? "Aguarde a campanha terminar" : "Excluir"}
                    onClick={() => askDelete(c)}
                  >
                    Excluir
                  </button>
                </li>
              );
            })}
            {filteredCampaigns.length > visible && (
              <li>
                <button
                  type="button"
                  className="btn-secondary w-full text-xs"
                  onClick={() => setVisible((v) => v + PAGE_SIZE)}
                >
                  Mostrar mais ({filteredCampaigns.length - visible} restantes)
                </button>
              </li>
            )}
          </ul>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900 lg:sticky lg:top-4">
          {!selected ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Selecione uma campanha para ver detalhes, enviar ou agendar.
            </p>
          ) : (
            <div className="space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <h3 className="truncate font-semibold text-gray-900 dark:text-gray-100">
                    {selected.name}
                  </h3>
                  <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-gray-600 dark:text-gray-300">
                    <StatusBadge status={selected.status} />
                    {selected.mode === "template" ? selected.template_name : "texto livre"}
                    {selected.header_image_url ? " · com imagem" : ""}
                    {selected.scheduled_at ? ` · agendada para ${fmtDate(selected.scheduled_at)}` : ""}
                  </p>
                </div>
                <button
                  type="button"
                  className="btn-secondary text-xs !text-red-600 dark:!text-red-400"
                  disabled={busy || selected.status === "running"}
                  onClick={() => askDelete(selected)}
                >
                  Excluir
                </button>
              </div>
              {selected.error && (
                <p className="text-sm text-red-600 dark:text-red-400">{selected.error}</p>
              )}
              <div className="grid grid-cols-4 gap-2 text-center">
                {[
                  ["Total", selected.recipient_count ?? selected.recipients?.length ?? 0],
                  ["Enviados", selected.counts?.sent ?? 0],
                  ["Falhas", selected.counts?.failed ?? 0],
                  ["Pendentes", selected.counts?.pending ?? 0],
                ].map(([k, v]) => (
                  <div
                    key={k}
                    className="rounded-lg border border-gray-200 px-2 py-1.5 dark:border-gray-800"
                  >
                    <div className="text-base font-semibold text-gray-900 dark:text-gray-100">{v}</div>
                    <div className="text-[11px] text-gray-500 dark:text-gray-400">{k}</div>
                  </div>
                ))}
              </div>

              <div className="flex flex-wrap items-center gap-2">
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
                      className="input-field !w-auto"
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

              <div className="flex flex-wrap gap-1.5">
                {[["all", "Todos"], ["sent", "Enviados"], ["failed", "Falhas"], ["pending", "Pendentes"]].map(
                  ([k, label]) => (
                    <button
                      key={k}
                      type="button"
                      onClick={() => setRecipientFilter(k)}
                      className={`rounded-full border px-2.5 py-0.5 text-xs ${
                        recipientFilter === k
                          ? "border-brand-600 bg-brand-600 text-white"
                          : "border-gray-300 text-gray-700 dark:border-gray-700 dark:text-gray-200"
                      }`}
                    >
                      {label}
                    </button>
                  )
                )}
              </div>
              <ul className="max-h-72 space-y-1 overflow-y-auto text-xs">
                {(selected.recipients || [])
                  .filter((r) => recipientFilter === "all" || r.status === recipientFilter)
                  .map((r) => (
                    <li
                      key={r.id}
                      className="flex flex-wrap items-center justify-between gap-2 rounded border border-gray-200 px-2 py-1.5 text-gray-800 dark:border-gray-800 dark:text-gray-200"
                    >
                      <span className="min-w-0 truncate">
                        {r.name || "—"} · {r.phone}
                        {r.conversation_id ? ` · conv #${r.conversation_id}` : ""}
                      </span>
                      <span
                        className={`font-medium ${
                          r.status === "sent"
                            ? "text-green-600 dark:text-green-400"
                            : r.status === "failed"
                              ? "text-red-600 dark:text-red-400"
                              : "text-gray-500 dark:text-gray-400"
                        }`}
                      >
                        {RECIPIENT_META[r.status] ?? r.status}
                      </span>
                      {r.error && (
                        <span className="w-full text-red-600 dark:text-red-400">{r.error}</span>
                      )}
                    </li>
                  ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      <Modal
        open={!!runNow}
        title="Executar disparo agora?"
        message={runNow ? `Envia "${runNow.name}" imediatamente, além do ciclo mensal normal.` : ""}
        confirmLabel="Enviar agora"
        cancelLabel="Voltar"
        onConfirm={async () => {
          const r = runNow;
          setRunNow(null);
          if (!r) return;
          setBusy(true);
          try {
            await props.recurring!.run(r.id);
            setNotice("Disparo executado. A campanha gerada aparece na lista.");
            await refresh();
          } catch (e) {
            setError(e instanceof Error ? e.message : "Erro ao executar");
          } finally {
            setBusy(false);
          }
        }}
        onCancel={() => setRunNow(null)}
      />

      <Modal
        open={!!deleteSchedule}
        title="Excluir disparo recorrente?"
        message={
          deleteSchedule
            ? `"${deleteSchedule.name}" deixará de ser enviado todo mês. As campanhas já geradas continuam no histórico.`
            : ""
        }
        confirmLabel="Excluir"
        cancelLabel="Manter"
        danger
        onConfirm={async () => {
          const r = deleteSchedule;
          setDeleteSchedule(null);
          if (!r) return;
          try {
            await props.recurring!.remove(r.id);
            await refresh();
          } catch (e) {
            setError(e instanceof Error ? e.message : "Erro ao excluir");
          }
        }}
        onCancel={() => setDeleteSchedule(null)}
      />

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

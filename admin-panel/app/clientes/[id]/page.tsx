"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";
import { Modal } from "@/components/Modal";
import { AppShell } from "@/components/Sidebar";
import { FieldLabel, HelpTip } from "@/components/HelpTip";
import { PasswordInput } from "@/components/PasswordInput";
import {
  createTenantUser,
  deleteKnowledge,
  getTenant,
  listKnowledge,
  listLlmModels,
  listTenantUsers,
  reindexKnowledge,
  Tenant,
  toggleTenantActive,
  updateTenant,
  uploadKnowledge,
} from "@/lib/api";

const PROMPT_TABS = [
  { key: "agent_system", label: "Agente" },
  { key: "facts_system", label: "Fatos" },
  { key: "summarize_system", label: "Resumo" },
] as const;

const SECTIONS = ["Geral", "Prompts", "Conhecimento", "Acesso ao portal"] as const;

export default function ClienteDetailPage() {
  const params = useParams();
  const clienteId = params.id as string;
  const fileRef = useRef<HTMLInputElement>(null);

  const [cliente, setCliente] = useState<Tenant | null>(null);
  const [section, setSection] = useState<(typeof SECTIONS)[number]>("Geral");
  const [promptTab, setPromptTab] = useState<(typeof PROMPT_TABS)[number]["key"]>("agent_system");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [knowledge, setKnowledge] = useState<Array<{ name: string; size: number }>>([]);
  const [llmModels, setLlmModels] = useState<Array<{ id: number; display_name: string; model_id: string }>>([]);
  const [portalUsers, setPortalUsers] = useState<Array<{ id: number; email: string; name: string }>>([]);
  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserPassword, setNewUserPassword] = useState("");
  const [newUserName, setNewUserName] = useState("");

  const [name, setName] = useState("");
  const [inboxIds, setInboxIds] = useState("");
  const [accountIds, setAccountIds] = useState("");
  const [chatwootBotToken, setChatwootBotToken] = useState("");
  const [chatwootBotTokenPreview, setChatwootBotTokenPreview] = useState("");
  const [llmModelId, setLlmModelId] = useState<number | "">("");
  const [prompts, setPrompts] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      window.location.href = "/login";
      return;
    }
    Promise.all([
      getTenant(clienteId),
      listKnowledge(clienteId),
      listLlmModels(),
      listTenantUsers(clienteId).catch(() => []),
    ])
      .then(([t, k, models, users]) => {
        setCliente(t);
        setName(t.name);
        setInboxIds((t.settings?.routing?.chatwoot_inbox_ids || []).join(", "));
        setAccountIds((t.settings?.routing?.chatwoot_account_ids || []).join(", "));
        setChatwootBotToken("");
        setChatwootBotTokenPreview(t.settings?.routing?.chatwoot_bot_token_preview || "");
        setLlmModelId(t.settings?.model?.llm_model_id ?? "");
        setPrompts(t.prompts || {});
        setKnowledge(k.files || []);
        setLlmModels(models);
        setPortalUsers(users);
      })
      .catch((e) => setError(e.message));
  }, [clienteId]);

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const parseIds = (raw: string) =>
        raw.split(/[,\s]+/).map((s) => Number(s.trim())).filter((n) => !Number.isNaN(n));
      const selected = llmModels.find((m) => m.id === llmModelId);
      const updated = await updateTenant(clienteId, {
        name,
        settings: {
          routing: {
            chatwoot_inbox_ids: parseIds(inboxIds),
            chatwoot_account_ids: parseIds(accountIds),
            ...(chatwootBotToken.trim() ? { chatwoot_bot_token: chatwootBotToken.trim() } : {}),
          },
          model: {
            llm_model_id: llmModelId === "" ? null : Number(llmModelId),
            name: selected?.model_id || cliente?.settings?.model?.name,
          },
        },
        prompts,
      });
      setCliente(updated);
      setChatwootBotToken("");
      setChatwootBotTokenPreview(updated.settings?.routing?.chatwoot_bot_token_preview || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  }

  async function confirmToggle() {
    if (!cliente) return;
    const updated = await toggleTenantActive(clienteId, !cliente.active);
    setCliente(updated);
    setModalOpen(false);
  }

  async function handleUpload(file: File) {
    await uploadKnowledge(clienteId, file);
    const k = await listKnowledge(clienteId);
    setKnowledge(k.files || []);
  }

  async function handleReindex() {
    await reindexKnowledge(clienteId);
    alert("Reindexação concluída");
  }

  if (!cliente && !error) {
    return (
      <AppShell>
        <p className="text-sm text-gray-500">Carregando...</p>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <Modal
        open={modalOpen}
        title={cliente?.active ? "Desativar cliente" : "Ativar cliente"}
        message={
          cliente?.active
            ? `Desativar "${cliente.name}"? O harness não atenderá novas conversas deste cliente.`
            : `Reativar "${cliente?.name}"?`
        }
        confirmLabel={cliente?.active ? "Desativar" : "Ativar"}
        danger={cliente?.active}
        onConfirm={confirmToggle}
        onCancel={() => setModalOpen(false)}
      />

      <div className="mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <nav className="text-sm text-gray-500">
            <Link href="/clientes" className="hover:text-gray-700">
              Clientes
            </Link>
            <span className="mx-2">/</span>
            <span className="text-gray-900">{cliente?.name}</span>
          </nav>
          <h1 className="mt-2 text-xl font-semibold text-gray-900 sm:text-2xl">{cliente?.name}</h1>
          <p className="text-sm text-gray-500">{clienteId}</p>
        </div>
        <div className="flex w-full items-center gap-2 sm:w-auto">
          <button type="button" className="btn-secondary w-full sm:w-auto" onClick={() => setModalOpen(true)}>
            {cliente?.active ? "Desativar cliente" : "Ativar cliente"}
          </button>
          <HelpTip text="Clientes inativos não recebem novas conversas do harness." />
        </div>
      </div>

      <div className="-mx-4 mb-6 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        <div className="flex min-w-max flex-nowrap gap-2 sm:min-w-0 sm:flex-wrap">
        {SECTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setSection(s)}
            className={`rounded-lg px-4 py-2 text-sm font-medium ${
              section === s ? "bg-brand-50 text-brand-700" : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            {s}
          </button>
        ))}
        </div>
      </div>

      <form onSubmit={handleSave} className="card max-w-3xl space-y-6">
        {section === "Geral" && (
          <>
            <div>
              <FieldLabel label="Nome" help="Nome comercial exibido no painel." />
              <input className="input-field" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div>
              <FieldLabel label="Inbox IDs (Chatwoot)" help="IDs das caixas de entrada que roteiam mensagens para este cliente." />
              <input className="input-field" value={inboxIds} onChange={(e) => setInboxIds(e.target.value)} />
            </div>
            <div>
              <FieldLabel label="Account IDs (Chatwoot)" help="IDs das contas Chatwoot deste cliente. Separe por vírgula." />
              <input className="input-field" value={accountIds} onChange={(e) => setAccountIds(e.target.value)} placeholder="2, 3" />
            </div>
            <div>
              <FieldLabel
                label="Token de acesso do robô (Chatwoot)"
                help="Token do Agent Bot no Chatwoot para este cliente enviar mensagens. Encontre em Configurações → Agent Bots."
              />
              {chatwootBotTokenPreview ? (
                <p className="mb-2 font-mono text-xs text-gray-500">
                  Token atual: {chatwootBotTokenPreview}
                </p>
              ) : (
                <p className="mb-2 text-xs text-amber-600">
                  Nenhum token configurado — usa o fallback da variável CHATWOOT_BOT_TOKEN no servidor.
                </p>
              )}
              <PasswordInput
                className="font-mono text-sm"
                value={chatwootBotToken}
                onChange={(e) => setChatwootBotToken(e.target.value)}
                placeholder="Cole o novo token para substituir (deixe vazio para manter)"
              />
            </div>
            <div className="rounded-lg border border-blue-100 bg-blue-50/60 p-4 text-sm text-gray-700">
              <p className="font-medium text-gray-900">Atendimento humano (handoff)</p>
              <ul className="mt-2 list-inside list-disc space-y-1 text-gray-600">
                <li>
                  Ao pedir um atendente, o bot envia a mensagem de transferência e para de responder.
                </li>
                <li>
                  A conversa recebe a etiqueta fixa{" "}
                  <strong className="text-gray-800">humano</strong> no Chatwoot (sem espaço no nome).
                </li>
                <li>
                  Crie essa etiqueta em{" "}
                  <strong className="text-gray-800">Chatwoot → Configurações → Etiquetas</strong>{" "}
                  ao montar o ambiente do cliente (uma vez por conta). Use exatamente o nome{" "}
                  <strong className="text-gray-800">humano</strong>.
                </li>
                <li>
                  Depois que alguém clicar <strong className="text-gray-800">Resolver</strong>, o bot volta a atender.
                </li>
              </ul>
            </div>
            <div>
              <FieldLabel
                label="Modelo LLM"
                help="Modelo de IA usado pelo agente deste cliente. Somente o administrador pode alterar; o cliente apenas visualiza no portal."
              />
              <select
                className="input-field"
                value={llmModelId}
                onChange={(e) => setLlmModelId(e.target.value ? Number(e.target.value) : "")}
              >
                <option value="">Padrão (nome no settings)</option>
                {llmModels.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.display_name} ({m.model_id})
                  </option>
                ))}
              </select>
            </div>
          </>
        )}

        {section === "Prompts" && (
          <>
            <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
            <div className="flex min-w-max flex-nowrap gap-2 border-b border-gray-200 pb-2">
              {PROMPT_TABS.map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setPromptTab(tab.key)}
                  className={`px-3 py-1.5 text-sm font-medium ${
                    promptTab === tab.key ? "border-b-2 border-brand-600 text-brand-700" : "text-gray-500"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            </div>
            <textarea
              className="input-field min-h-[200px] font-mono text-xs sm:min-h-[280px]"
              value={prompts[promptTab] || ""}
              onChange={(e) => setPrompts({ ...prompts, [promptTab]: e.target.value })}
            />
          </>
        )}

        {section === "Conhecimento" && (
          <div className="space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row">
              <input
                ref={fileRef}
                type="file"
                accept=".md,.txt"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])}
              />
              <button type="button" className="btn-secondary" onClick={() => fileRef.current?.click()}>
                Upload .md / .txt
              </button>
              <button type="button" className="btn-primary" onClick={handleReindex}>
                Reindexar RAG
              </button>
            </div>
            {knowledge.length === 0 ? (
              <p className="text-sm text-gray-500">Nenhum documento.</p>
            ) : (
              <ul className="divide-y divide-gray-100 text-sm">
                {knowledge.map((f) => (
                  <li key={f.name} className="flex items-center justify-between py-2">
                    <span>{f.name}</span>
                    <button
                      type="button"
                      className="text-red-600 hover:text-red-700"
                      onClick={async () => {
                        await deleteKnowledge(clienteId, f.name);
                        setKnowledge((prev) => prev.filter((x) => x.name !== f.name));
                      }}
                    >
                      Remover
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {section === "Acesso ao portal" && (
          <div className="space-y-6">
            <div className="rounded-lg border border-brand-100 bg-brand-50/50 p-4">
              <p className="text-sm text-gray-700">
                O cliente acessa o portal em{" "}
                <code className="rounded bg-white px-1 text-xs">/portal/login</code> para editar prompts,
                documentos e ver métricas.
              </p>
            </div>
            {portalUsers.length === 0 ? (
              <p className="text-sm text-amber-700">
                Nenhum usuário cadastrado. Crie o acesso abaixo para o cliente poder entrar no portal.
              </p>
            ) : (
              <div>
                <h3 className="mb-2 text-sm font-medium text-gray-900">Usuários cadastrados</h3>
                <ul className="divide-y divide-gray-100 rounded-lg border border-gray-200 text-sm">
                  {portalUsers.map((u) => (
                    <li key={u.id} className="flex justify-between px-4 py-3">
                      <span className="font-medium">{u.name}</span>
                      <span className="text-gray-500">{u.email}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="border-t border-gray-100 pt-4">
              <h3 className="mb-3 text-sm font-medium text-gray-900">Adicionar acesso</h3>
              <div className="grid gap-3 sm:grid-cols-2">
                <input
                  className="input-field"
                  placeholder="Nome"
                  value={newUserName}
                  onChange={(e) => setNewUserName(e.target.value)}
                />
                <input
                  className="input-field"
                  type="email"
                  placeholder="Email"
                  value={newUserEmail}
                  onChange={(e) => setNewUserEmail(e.target.value)}
                />
                <PasswordInput
                  className="sm:col-span-2"
                  placeholder="Senha"
                  value={newUserPassword}
                  onChange={(e) => setNewUserPassword(e.target.value)}
                />
              </div>
              <button
                type="button"
                className="btn-primary mt-3"
                onClick={async () => {
                  try {
                    await createTenantUser(clienteId, {
                      email: newUserEmail,
                      password: newUserPassword,
                      name: newUserName,
                    });
                    const users = await listTenantUsers(clienteId);
                    setPortalUsers(users);
                    setNewUserEmail("");
                    setNewUserPassword("");
                    setNewUserName("");
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "Erro ao criar usuário");
                  }
                }}
              >
                Criar acesso
              </button>
            </div>
          </div>
        )}

        {error && <p className="text-sm text-red-600">{error}</p>}
        {(section === "Geral" || section === "Prompts") && (
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? "Salvando..." : "Salvar alterações"}
          </button>
        )}
      </form>
    </AppShell>
  );
}

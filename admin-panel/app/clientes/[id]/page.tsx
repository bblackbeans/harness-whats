"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";
import { Modal } from "@/components/Modal";
import { AppShell } from "@/components/Sidebar";
import { FieldLabel, HelpTip } from "@/components/HelpTip";
import { PasswordInput } from "@/components/PasswordInput";
import {
  createAgent,
  createAgentTool,
  createContact,
  createCustomField,
  createHttpTool,
  createInboundWebhook,
  createTenantUser,
  deleteAgent,
  deleteAgentTool,
  deleteContact,
  deleteCustomField,
  deleteHttpTool,
  deleteInboundWebhook,
  deleteKnowledge,
  deleteSendableFile,
  getAgentTool,
  getOrchestrator,
  getTenant,
  listAgents,
  listAgentTools,
  listContacts,
  listCustomFields,
  listHttpTools,
  listInboundWebhooks,
  listKnowledge,
  listLlmModels,
  listSendableFiles,
  listTenantUsers,
  regenerateWebhookSecret,
  reindexKnowledge,
  Tenant,
  toggleTenantActive,
  updateAgent,
  updateAgentTool,
  updateContact,
  updateInboundWebhook,
  updateOrchestrator,
  updateSendableFile,
  updateTenant,
  uploadKnowledge,
  uploadSendableFile,
} from "@/lib/api";
import { FieldsManager } from "@/components/crm/FieldsManager";
import { ContactsManager } from "@/components/crm/ContactsManager";
import { IntegrationsManager } from "@/components/crm/IntegrationsManager";
import { FilesManager } from "@/components/crm/FilesManager";
import { AgentsManager } from "@/components/crm/AgentsManager";
import { OrchestratorManager } from "@/components/crm/OrchestratorManager";
import { ToolsManager } from "@/components/crm/ToolsManager";

const PROMPT_TABS = [
  { key: "agent_system", label: "Agente" },
  { key: "facts_system", label: "Fatos" },
  { key: "summarize_system", label: "Resumo" },
] as const;

const SECTIONS = [
  "Geral",
  "Prompts",
  "Conhecimento",
  "Arquivos",
  "Campos",
  "Contatos",
  "Integrações",
  "Orquestrador",
  "Agentes",
  "Tools",
  "Flows",
  "Acesso ao portal",
] as const;

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
        <p className="text-sm text-gray-500 dark:text-gray-400">Carregando...</p>
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
          <nav className="text-sm text-gray-500 dark:text-gray-400">
            <Link href="/clientes" className="hover:text-gray-700 dark:hover:text-gray-200">
              Clientes
            </Link>
            <span className="mx-2">/</span>
            <span className="text-gray-900 dark:text-gray-100">{cliente?.name}</span>
          </nav>
          <h1 className="mt-2 text-xl font-semibold text-gray-900 sm:text-2xl dark:text-gray-100">{cliente?.name}</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">{clienteId}</p>
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
        {SECTIONS.map((s) => {
          const isFlows = s === "Flows";
          if (isFlows) {
            return (
              <span
                key={s}
                title="Flows fora do MVP"
                className="cursor-not-allowed rounded-lg px-4 py-2 text-sm font-medium text-gray-400 opacity-60 dark:text-gray-500"
                aria-disabled="true"
              >
                {s}
                <span className="ml-1.5 text-[10px] uppercase tracking-wide">em breve</span>
              </span>
            );
          }
          return (
          <button
            key={s}
            type="button"
            onClick={() => setSection(s)}
            className={`rounded-lg px-4 py-2 text-sm font-medium ${
              section === s ? "bg-brand-50 text-brand-700 dark:bg-brand-600/20 dark:text-brand-300" : "text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
            }`}
          >
            {s}
          </button>
          );
        })}
        </div>
      </div>

      {(section === "Campos" ||
        section === "Contatos" ||
        section === "Integrações" ||
        section === "Arquivos" ||
        section === "Orquestrador" ||
        section === "Agentes" ||
        section === "Tools") && (
        <div className="max-w-5xl">
          {section === "Campos" && (
            <FieldsManager
              load={() => listCustomFields(clienteId)}
              create={(data) => createCustomField(clienteId, data)}
              remove={(id) => deleteCustomField(clienteId, id)}
            />
          )}
          {section === "Contatos" && (
            <ContactsManager
              loadContacts={(q) => listContacts(clienteId, q)}
              loadFields={() => listCustomFields(clienteId)}
              create={(data) => createContact(clienteId, data)}
              update={(id, data) => updateContact(clienteId, id, data)}
              remove={(id) => deleteContact(clienteId, id)}
            />
          )}
          {section === "Integrações" && (
            <IntegrationsManager
              loadWebhooks={() => listInboundWebhooks(clienteId)}
              createWebhook={(data) => createInboundWebhook(clienteId, data)}
              updateWebhook={(id, data) => updateInboundWebhook(clienteId, id, data)}
              regenSecret={(id) => regenerateWebhookSecret(clienteId, id)}
              deleteWebhook={(id) => deleteInboundWebhook(clienteId, id)}
              loadTools={() => listHttpTools(clienteId)}
              createTool={(data) => createHttpTool(clienteId, data)}
              deleteTool={(id) => deleteHttpTool(clienteId, id)}
              loadFields={() => listCustomFields(clienteId)}
            />
          )}
          {section === "Arquivos" && (
            <FilesManager
              load={() => listSendableFiles(clienteId)}
              upload={(file, description) => uploadSendableFile(clienteId, file, description)}
              update={(id, description) => updateSendableFile(clienteId, id, description)}
              remove={(id) => deleteSendableFile(clienteId, id)}
            />
          )}
          {section === "Orquestrador" && (
            <OrchestratorManager
              load={() => getOrchestrator(clienteId)}
              save={(data) => updateOrchestrator(clienteId, data)}
              loadSpecialists={() => listAgents(clienteId, "specialist")}
            />
          )}
          {section === "Agentes" && (
            <AgentsManager
              load={() => listAgents(clienteId, "specialist")}
              create={(data) => createAgent(clienteId, data)}
              update={(id, data) => updateAgent(clienteId, id, data)}
              remove={(id) => deleteAgent(clienteId, id)}
            />
          )}
          {section === "Tools" && (
            <ToolsManager
              loadAgents={() => listAgents(clienteId, "specialist")}
              loadTools={(agentId) => listAgentTools(clienteId, agentId)}
              getTool={(id) => getAgentTool(clienteId, id)}
              createTool={(data) => createAgentTool(clienteId, data)}
              updateTool={(id, data) => updateAgentTool(clienteId, id, data)}
              deleteTool={(id) => deleteAgentTool(clienteId, id)}
              loadFiles={() => listSendableFiles(clienteId)}
            />
          )}
        </div>
      )}

      {(section === "Geral" ||
        section === "Prompts" ||
        section === "Conhecimento" ||
        section === "Acesso ao portal") && (
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
                <p className="mb-2 font-mono text-xs text-gray-500 dark:text-gray-400">
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
            <div className="rounded-lg border border-gray-200 bg-gray-50/60 p-4 text-sm text-gray-700 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-300">
              <p className="font-medium text-gray-900 dark:text-gray-100">Atendimento humano (handoff)</p>
              <ul className="mt-2 list-inside list-disc space-y-1 text-gray-600 dark:text-gray-300">
                <li>
                  Ao pedir um atendente, o bot envia a mensagem de transferência e para de responder.
                </li>
                <li>
                  O bot marca o handoff internamente e tenta aplicar a etiqueta{" "}
                  <strong className="text-gray-800 dark:text-gray-200">humano</strong> (crie em Configurações → Etiquetas).
                </li>
                <li>
                  Para a etiqueta aparecer automaticamente, configure{" "}
                  <strong className="text-gray-800 dark:text-gray-200">CHATWOOT_ADMIN_TOKEN</strong> no servidor
                  (token de um admin do Chatwoot).
                </li>
                <li>
                  Depois que alguém clicar <strong className="text-gray-800 dark:text-gray-200">Resolver</strong>, o bot volta a atender.
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
            <div className="flex min-w-max flex-nowrap gap-2 border-b border-gray-200 pb-2 dark:border-gray-800">
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
              <p className="text-sm text-gray-500 dark:text-gray-400">Nenhum documento.</p>
            ) : (
              <ul className="divide-y divide-gray-100 text-sm dark:divide-gray-800">
                {knowledge.map((f) => (
                  <li key={f.name} className="flex items-center justify-between py-2">
                    <span>{f.name}</span>
                    <button
                      type="button"
                      className="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-400"
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
            <div className="rounded-lg border border-brand-100 bg-brand-50/50 p-4 dark:border-brand-700/40 dark:bg-brand-600/10">
              <p className="text-sm text-gray-700 dark:text-gray-300">
                O cliente acessa o portal em{" "}
                <code className="rounded bg-white px-1 text-xs dark:bg-gray-900">/portal/login</code> para gerenciar
                prompts, base de conhecimento e acompanhar o uso do chatbot.
              </p>
            </div>
            {portalUsers.length === 0 ? (
              <p className="text-sm text-amber-700">
                Nenhum usuário cadastrado. Crie o acesso abaixo para o cliente poder entrar no portal.
              </p>
            ) : (
              <div>
                <h3 className="mb-2 text-sm font-medium text-gray-900 dark:text-gray-100">Usuários cadastrados</h3>
                <ul className="divide-y divide-gray-100 rounded-lg border border-gray-200 text-sm dark:divide-gray-800 dark:border-gray-800">
                  {portalUsers.map((u) => (
                    <li key={u.id} className="flex justify-between px-4 py-3">
                      <span className="font-medium">{u.name}</span>
                      <span className="text-gray-500 dark:text-gray-400">{u.email}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="border-t border-gray-100 pt-4 dark:border-gray-800">
              <h3 className="mb-3 text-sm font-medium text-gray-900 dark:text-gray-100">Adicionar acesso</h3>
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

        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        {(section === "Geral" || section === "Prompts") && (
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? "Salvando..." : "Salvar alterações"}
          </button>
        )}
      </form>
      )}
    </AppShell>
  );
}

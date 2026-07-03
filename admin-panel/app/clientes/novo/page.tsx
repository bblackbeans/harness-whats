"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { AppShell } from "@/components/Sidebar";
import { FieldLabel } from "@/components/HelpTip";
import { createTenant } from "@/lib/api";

const STEPS = ["Dados", "Chatwoot", "Modelo", "Acesso ao portal", "Prompts"];

export default function NovoClientePage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [id, setId] = useState("");
  const [name, setName] = useState("");
  const [language, setLanguage] = useState("pt-BR");
  const [inboxIds, setInboxIds] = useState("");
  const [accountIds, setAccountIds] = useState("");
  const [modelName, setModelName] = useState("gpt-4o-mini");
  const [temperature, setTemperature] = useState("0.3");
  const [portalEmail, setPortalEmail] = useState("");
  const [portalPassword, setPortalPassword] = useState("");
  const [portalName, setPortalName] = useState("");
  const [agentPrompt, setAgentPrompt] = useState(
    "Você é o assistente virtual de atendimento por mensagem.\n\nResponda em português do Brasil."
  );

  function parseIds(raw: string): number[] {
    return raw
      .split(/[,\s]+/)
      .map((s) => s.trim())
      .filter(Boolean)
      .map(Number)
      .filter((n) => !Number.isNaN(n));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (step < STEPS.length - 1) {
      if (step === 3 && (!portalEmail.trim() || !portalPassword.trim())) {
        setError("Informe email e senha para o acesso ao portal do cliente.");
        return;
      }
      setError("");
      setStep(step + 1);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const cliente = await createTenant({
        id: id.toLowerCase().trim(),
        name,
        language,
        active: true,
        settings: {
          routing: {
            chatwoot_inbox_ids: parseIds(inboxIds),
            chatwoot_account_ids: parseIds(accountIds),
          },
          model: { name: modelName, temperature: parseFloat(temperature) },
        },
        prompts: { agent_system: agentPrompt },
        portal_user: {
          email: portalEmail.trim(),
          password: portalPassword,
          name: portalName.trim() || name,
        },
      });
      router.push(`/clientes/${cliente.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell>
      <div className="mb-8">
        <Link href="/clientes" className="text-sm text-gray-500 hover:text-gray-700">
          ← Clientes
        </Link>
        <h1 className="mt-2 text-xl font-semibold text-gray-900 sm:text-2xl">Novo cliente</h1>
      </div>

      <div className="-mx-4 mb-8 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        <div className="flex min-w-max gap-2 sm:min-w-0 sm:flex-wrap">
        {STEPS.map((label, i) => (
          <div
            key={label}
            className={`min-w-[88px] flex-1 rounded-lg border px-2 py-2 text-center text-xs font-medium sm:min-w-[100px] sm:px-3 sm:text-sm ${
              i === step
                ? "border-brand-600 bg-brand-50 text-brand-700"
                : i < step
                  ? "border-green-200 bg-green-50 text-green-700"
                  : "border-gray-200 text-gray-400"
            }`}
          >
            {i + 1}. <span className="max-sm:hidden">{label}</span><span className="sm:hidden">{label.split(" ")[0]}</span>
          </div>
        ))}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="card max-w-2xl space-y-6">
        {step === 0 && (
          <>
            <div>
              <FieldLabel label="ID (slug)" help="Identificador único sem espaços. Ex.: blackbeans, minha-empresa. Usado nas URLs e no roteamento." />
              <input
                className="input-field"
                value={id}
                onChange={(e) => setId(e.target.value)}
                placeholder="ex: blackbeans"
                required
              />
            </div>
            <div>
              <FieldLabel label="Nome" help="Nome comercial do cliente exibido no painel." />
              <input className="input-field" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div>
              <FieldLabel label="Idioma" help="Idioma padrão das respostas do agente. Ex.: pt-BR." />
              <input className="input-field" value={language} onChange={(e) => setLanguage(e.target.value)} />
            </div>
          </>
        )}
        {step === 1 && (
          <>
            <div>
              <FieldLabel label="Chatwoot Inbox IDs" help="IDs das caixas de entrada no Chatwoot que pertencem a este cliente. Separe por vírgula. Ex.: 1, 2" />
              <input
                className="input-field"
                value={inboxIds}
                onChange={(e) => setInboxIds(e.target.value)}
                placeholder="1, 2, 3"
              />
              <p className="mt-1 text-xs text-gray-500">
                Separados por vírgula. Usado para rotear mensagens ao cliente.
              </p>
            </div>
            <div>
              <FieldLabel label="Chatwoot Account IDs" help="ID da conta Chatwoot, se diferente da padrão do servidor." />
              <input
                className="input-field"
                value={accountIds}
                onChange={(e) => setAccountIds(e.target.value)}
                placeholder="1"
              />
            </div>
          </>
        )}
        {step === 2 && (
          <>
            <div>
              <FieldLabel label="Modelo OpenAI" help="Modelo de linguagem usado pelo agente deste cliente." />
              <select className="input-field" value={modelName} onChange={(e) => setModelName(e.target.value)}>
                <option value="gpt-4o-mini">gpt-4o-mini</option>
                <option value="gpt-4o">gpt-4o</option>
                <option value="gpt-4.1-mini">gpt-4.1-mini</option>
                <option value="gpt-4.1">gpt-4.1</option>
              </select>
            </div>
            <div>
              <FieldLabel
                label="Criatividade das respostas"
                help="Valores baixos (0.3) deixam o agente mais consistente; valores altos aumentam a variação nas respostas."
              />
              <input
                className="input-field"
                type="number"
                step="0.1"
                min="0"
                max="2"
                value={temperature}
                onChange={(e) => setTemperature(e.target.value)}
              />
              <p className="mt-1 text-xs text-gray-500">
                Valores baixos (0.3) deixam o agente mais consistente; valores altos aumentam a variação
                nas respostas.
              </p>
            </div>
          </>
        )}
        {step === 3 && (
          <>
            <p className="text-sm text-gray-600">
              Credenciais para o cliente acessar o portal em{" "}
              <code className="rounded bg-gray-100 px-1 text-xs">/portal/login</code> e editar prompts,
              documentos e métricas.
            </p>
            <div>
              <FieldLabel label="Nome do responsável" help="Nome da pessoa que acessará o portal. Opcional." />
              <input
                className="input-field"
                value={portalName}
                onChange={(e) => setPortalName(e.target.value)}
                placeholder="Opcional"
              />
            </div>
            <div>
              <FieldLabel label="Email de acesso" help="Email que o cliente usará em /portal/login." />
              <input
                className="input-field"
                type="email"
                value={portalEmail}
                onChange={(e) => setPortalEmail(e.target.value)}
                placeholder="cliente@empresa.com"
                required
              />
            </div>
            <div>
              <FieldLabel label="Senha" help="Senha inicial do portal. O cliente pode pedir troca ao administrador." />
              <input
                className="input-field"
                type="password"
                value={portalPassword}
                onChange={(e) => setPortalPassword(e.target.value)}
                required
              />
            </div>
          </>
        )}
        {step === 4 && (
          <div>
            <FieldLabel label="Prompt do agente (agent_system)" help="Instruções de personalidade e comportamento do assistente virtual." />
            <textarea
              className="input-field min-h-[200px] font-mono text-xs"
              value={agentPrompt}
              onChange={(e) => setAgentPrompt(e.target.value)}
            />
          </div>
        )}

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex gap-3">
          {step > 0 && (
            <button type="button" className="btn-secondary" onClick={() => setStep(step - 1)}>
              Voltar
            </button>
          )}
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? "Salvando..." : step < STEPS.length - 1 ? "Continuar" : "Criar cliente"}
          </button>
        </div>
      </form>
    </AppShell>
  );
}

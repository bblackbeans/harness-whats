"use client";

import { FormEvent, useEffect, useState } from "react";
import { FieldLabel } from "@/components/HelpTip";
import { PortalGuide } from "@/components/PortalGuide";
import { PortalShell } from "@/components/PortalShell";
import { PORTAL_PROMPT_HELP } from "@/lib/portal-help";
import { portalGetPrompts, portalUpdatePrompt } from "@/lib/portal-api";

const TABS = [
  { key: "agent_system", label: "Agente" },
  { key: "facts_system", label: "Fatos" },
  { key: "summarize_system", label: "Resumo" },
] as const;

export default function PortalPromptsPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]["key"]>("agent_system");
  const [prompts, setPrompts] = useState<Record<string, string>>({});
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const tabHelp = PORTAL_PROMPT_HELP[tab];

  useEffect(() => {
    if (!localStorage.getItem("portal_access_token")) {
      window.location.href = "/portal/login";
      return;
    }
    portalGetPrompts()
      .then((p) => {
        setPrompts(p);
        setContent(p.agent_system || "");
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    setContent(prompts[tab] || "");
  }, [tab, prompts]);

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMessage("");
    setError("");
    try {
      await portalUpdatePrompt(tab, content);
      setPrompts((prev) => ({ ...prev, [tab]: content }));
      setMessage("Prompt salvo. Novas conversas já usam este texto.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  }

  return (
    <PortalShell>
      <h1 className="mb-2 text-xl font-semibold text-gray-900 sm:text-2xl">Prompts</h1>
      <p className="mb-6 text-sm text-gray-500">
        Instruções que definem como o seu chatbot responde nas conversas.
      </p>

      <PortalGuide title="Como personalizar as respostas" className="mb-6">
        <p>
          Os prompts orientam a inteligência artificial do seu chatbot. O prompt{" "}
          <strong>Agente</strong> é o principal — descreva quem é o bot, o tom de voz e o que ele
          pode ou não responder.
        </p>
        <p className="text-gray-600">
          Escreva em português claro, como se estivesse treinando um atendente. Não é necessário
          usar códigos ou comandos especiais.
        </p>
      </PortalGuide>

      <div className="-mx-4 mb-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        <div className="flex min-w-max flex-nowrap gap-2 border-b border-gray-200">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={`border-b-2 px-4 py-2 text-sm font-medium ${
                tab === t.key ? "border-brand-600 text-brand-700" : "border-transparent text-gray-500"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mb-4 rounded-lg border border-gray-200 bg-gray-50/80 p-4 text-sm text-gray-600">
        <p className="font-medium text-gray-800">{tabHelp.title}</p>
        <p className="mt-1">{tabHelp.description}</p>
        <p className="mt-2 text-xs italic text-gray-500">{tabHelp.example}</p>
      </div>

      <form onSubmit={handleSave} className="card space-y-4">
        <FieldLabel label={`Texto do prompt — ${tabHelp.title}`} help={tabHelp.help} />
        <textarea
          className="input-field min-h-[200px] font-mono text-sm sm:min-h-[320px]"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Descreva aqui como o bot deve se comportar..."
        />
        {message && <p className="text-sm text-green-700">{message}</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? "Salvando..." : "Salvar prompt"}
        </button>
      </form>
    </PortalShell>
  );
}

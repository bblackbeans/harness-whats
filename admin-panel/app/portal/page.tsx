"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PortalActionCard, PortalGuide, PortalLegend } from "@/components/PortalGuide";
import { PortalShell } from "@/components/PortalShell";
import { PORTAL_DASHBOARD_GUIDE } from "@/lib/portal-help";
import { portalListKnowledge, portalMe, portalUsage } from "@/lib/portal-api";

export default function PortalDashboardPage() {
  const [name, setName] = useState("");
  const [tenantName, setTenantName] = useState("");
  const [model, setModel] = useState("");
  const [docCount, setDocCount] = useState(0);
  const [usage, setUsage] = useState<{ calls: number; cost_estimate: number; tokens_total: number } | null>(null);
  const [planName, setPlanName] = useState("");
  const [exceeded, setExceeded] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!localStorage.getItem("portal_access_token")) {
      window.location.href = "/portal/login";
      return;
    }
    Promise.all([portalMe(), portalUsage(), portalListKnowledge().catch(() => ({ files: [] }))])
      .then(([me, u, k]) => {
        setName(me.name);
        setTenantName(me.tenant.name);
        setModel(me.tenant.settings?.model?.name || "—");
        setDocCount(k.files?.length ?? 0);
        setUsage(u.usage);
        setPlanName(u.limits.plan?.name || "");
        setExceeded(u.limits.exceeded);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const costBrl = ((usage?.cost_estimate ?? 0) * 5.8).toFixed(4);

  return (
    <PortalShell>
      <div className="mb-6 sm:mb-8">
        <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl">Olá, {name || "..."}</h1>
        <p className="text-sm text-gray-500">{tenantName}</p>
      </div>

      {loading && <p className="text-sm text-gray-500">Carregando...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {!loading && !error && (
        <>
          <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="card">
              <p className="text-sm text-gray-500">Modelo de IA</p>
              <p className="mt-1 text-xl font-semibold text-gray-900">{model}</p>
              <p className="mt-2 text-xs text-gray-400">
                Definido pelo administrador da plataforma.
              </p>
            </div>
            <div className="card">
              <p className="text-sm text-gray-500">Chamadas (mês)</p>
              <p className="mt-1 text-xl font-semibold text-gray-900">{usage?.calls ?? 0}</p>
              <p className="mt-2 text-xs text-gray-400">
                Cada resposta do bot conta como uma chamada.
              </p>
            </div>
            <div className="card">
              <p className="text-sm text-gray-500">Custo estimado</p>
              <p className="mt-1 text-xl font-semibold text-gray-900">
                ${(usage?.cost_estimate ?? 0).toFixed(4)}
              </p>
              <p className="mt-2 text-xs text-gray-400">≈ R$ {costBrl} (cotação ~R$ 5,80)</p>
            </div>
            <div className="card">
              <p className="text-sm text-gray-500">Documentos na base</p>
              <p className="mt-1 text-xl font-semibold text-gray-900">{docCount}</p>
              <p className="mt-2 text-xs text-gray-400">
                {docCount === 0 ? (
                  <Link href="/portal/knowledge" className="text-brand-600 hover:underline">
                    Envie seu primeiro FAQ →
                  </Link>
                ) : (
                  "Arquivos .md ou .txt indexados para o bot."
                )}
              </p>
            </div>
          </div>

          {planName && (
            <p className="mb-6 text-sm text-gray-500">
              Plano atual: <span className="font-medium text-gray-700">{planName}</span>
            </p>
          )}

          <div className="mb-6 grid gap-4 sm:grid-cols-2">
            <PortalActionCard
              href="/portal/prompts"
              title="Personalizar prompts"
              description="Ajuste como o bot fala, o tom e as regras de atendimento."
            />
            <PortalActionCard
              href="/portal/knowledge"
              title="Base de conhecimento"
              description="Envie FAQs e materiais para o bot responder com informação da sua empresa."
            />
          </div>

          <PortalGuide title="O que você pode fazer aqui" className="mb-6">
            <p>
              Aqui você gerencia o <strong>conteúdo do seu chatbot</strong>: em{" "}
              <strong>Prompts</strong>, define como ele fala e se comporta; em{" "}
              <strong>Conhecimento</strong>, envia FAQs e materiais que ele usa para responder com
              informação da sua empresa.
            </p>
          </PortalGuide>

          <PortalLegend
            items={PORTAL_DASHBOARD_GUIDE.howItWorks.map((item) => ({
              color: "blue",
              label: item.label,
              text: item.text,
            }))}
            footer="Dúvidas sobre canais (WhatsApp, Telegram) ou integração técnica? Fale com o administrador da plataforma."
          />
        </>
      )}

      {exceeded && (
        <div className="card mt-6 border-amber-200 bg-amber-50">
          <p className="text-sm text-amber-800">
            <strong>Limite de uso atingido.</strong> O bot pode parar de responder até o
            administrador ajustar o plano. Entre em contato com o suporte.
          </p>
        </div>
      )}
    </PortalShell>
  );
}

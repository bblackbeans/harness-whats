"use client";

import { useEffect, useState } from "react";
import { PortalShell } from "@/components/PortalShell";
import { portalMe, portalUsage } from "@/lib/portal-api";

export default function PortalDashboardPage() {
  const [name, setName] = useState("");
  const [tenantName, setTenantName] = useState("");
  const [model, setModel] = useState("");
  const [usage, setUsage] = useState<{ calls: number; cost_estimate: number; tokens_total: number } | null>(null);
  const [exceeded, setExceeded] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!localStorage.getItem("portal_access_token")) {
      window.location.href = "/portal/login";
      return;
    }
    Promise.all([portalMe(), portalUsage()])
      .then(([me, u]) => {
        setName(me.name);
        setTenantName(me.tenant.name);
        setModel(me.tenant.settings?.model?.name || "—");
        setUsage(u.usage);
        setExceeded(u.limits.exceeded);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <PortalShell>
      <div className="mb-6 sm:mb-8">
        <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl">Olá, {name || "..."}</h1>
        <p className="text-sm text-gray-500">{tenantName}</p>
      </div>

      {loading && <p className="text-sm text-gray-500">Carregando...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {!loading && !error && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="card">
            <p className="text-sm text-gray-500">Modelo atual</p>
            <p className="mt-1 text-xl font-semibold text-gray-900">{model}</p>
            <p className="mt-2 text-xs text-gray-400">
              Alterações de modelo são feitas pelo administrador da plataforma.
            </p>
          </div>
          <div className="card">
            <p className="text-sm text-gray-500">Chamadas (mês)</p>
            <p className="mt-1 text-xl font-semibold text-gray-900">{usage?.calls ?? 0}</p>
          </div>
          <div className="card">
            <p className="text-sm text-gray-500">Custo estimado</p>
            <p className="mt-1 text-xl font-semibold text-gray-900">
              ${(usage?.cost_estimate ?? 0).toFixed(4)}
            </p>
          </div>
        </div>
      )}

      {exceeded && (
        <div className="card mt-6">
          <p className="text-sm text-amber-700">
            Limite de uso atingido. Entre em contato com o suporte.
          </p>
        </div>
      )}
    </PortalShell>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/Sidebar";
import { listAudit, listTenants, Tenant, usageSummary } from "@/lib/api";
import { formatBrasiliaDateTime } from "@/lib/datetime";

const MAX_CLIENT_CARDS = 6;

export default function DashboardPage() {
  const [clientes, setClientes] = useState<Tenant[]>([]);
  const [ativos, setAtivos] = useState(0);
  const [usage, setUsage] = useState<Array<{ tenant_id: string; calls: number; cost_estimate: number }>>([]);
  const [audit, setAudit] = useState<Array<{ action: string; tenant_id: string | null; created_at: string }>>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      window.location.href = "/login";
      return;
    }
    Promise.all([listTenants(), usageSummary().catch(() => []), listAudit(10).catch(() => [])])
      .then(([lista, u, a]) => {
        setClientes(lista);
        setAtivos(lista.filter((c) => c.active).length);
        setUsage(u);
        setAudit(a);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const totalClientes = clientes.length;
  const totalCost = usage.reduce((s, u) => s + (u.cost_estimate || 0), 0);
  const clientesVisiveis = clientes.slice(0, MAX_CLIENT_CARDS);

  return (
    <AppShell>
      <div className="mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl">Dashboard</h1>
          <p className="text-sm text-gray-500">Visão geral da plataforma</p>
        </div>
        <Link href="/clientes/novo" className="btn-primary w-full sm:w-auto">
          Novo cliente
        </Link>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 sm:mb-8 sm:grid-cols-2 lg:grid-cols-4">
        <div className="card">
          <p className="text-sm text-gray-500">Total de clientes</p>
          <p className="mt-1 text-3xl font-semibold text-gray-900">{totalClientes}</p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-500">Ativos</p>
          <p className="mt-1 text-3xl font-semibold text-green-600">{ativos}</p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-500">Inativos</p>
          <p className="mt-1 text-3xl font-semibold text-gray-400">{totalClientes - ativos}</p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-500">Custo estimado (LLM)</p>
          <p className="mt-1 text-3xl font-semibold text-gray-900">${totalCost.toFixed(4)}</p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Clientes</h2>
            <Link href="/clientes" className="text-sm font-medium text-brand-600">
              Ver todos
            </Link>
          </div>
          {loading && <p className="text-sm text-gray-500">Carregando...</p>}
          {!loading && totalClientes === 0 && (
            <p className="text-sm text-gray-500">Nenhum cliente cadastrado.</p>
          )}
          {!loading && totalClientes > 0 && (
            <>
              <p className="mb-4 text-sm text-gray-600">
                {totalClientes} cliente{totalClientes !== 1 ? "s" : ""} na plataforma
              </p>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {clientesVisiveis.map((c) => (
                  <Link
                    key={c.id}
                    href={`/clientes/${c.id}`}
                    className="group rounded-lg border border-gray-200 bg-gray-50/50 p-4 transition hover:border-brand-300 hover:bg-brand-50/40"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-medium text-gray-900 group-hover:text-brand-700">{c.name}</p>
                      {c.active ? (
                        <span className="badge-success shrink-0">Ativo</span>
                      ) : (
                        <span className="badge-neutral shrink-0">Inativo</span>
                      )}
                    </div>
                    <p className="mt-1 truncate text-xs text-gray-500">{c.id}</p>
                    {c.settings?.model?.name && (
                      <p className="mt-2 text-xs text-gray-500">
                        Modelo: <span className="text-gray-700">{c.settings.model.name}</span>
                      </p>
                    )}
                  </Link>
                ))}
              </div>
              {totalClientes > MAX_CLIENT_CARDS && (
                <p className="mt-4 text-sm text-gray-600">
                  <Link href="/clientes" className="font-medium text-brand-600">
                    Ver todos os {totalClientes} clientes →
                  </Link>
                </p>
              )}
            </>
          )}
        </div>

        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Atividade recente</h2>
          {error && <p className="mb-2 text-sm text-red-600">{error}</p>}
          {audit.length === 0 ? (
            <p className="text-sm text-gray-500">Nenhum evento registrado.</p>
          ) : (
            <ul className="space-y-3 text-sm">
              {audit.map((e, i) => (
                <li key={i} className="flex flex-col gap-1 border-b border-gray-100 pb-2 sm:flex-row sm:justify-between">
                  <span className="text-gray-700">
                    {e.action}
                    {e.tenant_id ? ` · ${e.tenant_id}` : ""}
                  </span>
                  <span className="text-xs text-gray-400">{formatBrasiliaDateTime(e.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </AppShell>
  );
}

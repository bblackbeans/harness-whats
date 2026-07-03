"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/Sidebar";
import { listTenants, Tenant, usageByModel, usageDaily, usageSummary } from "@/lib/api";

export default function UsagePage() {
  const [clientes, setClientes] = useState<Tenant[]>([]);
  const [summary, setSummary] = useState<Array<{ tenant_id: string; calls: number; cost_estimate: number; tokens_total: number }>>([]);
  const [daily, setDaily] = useState<Array<{ date: string; calls: number; cost_estimate: number }>>([]);
  const [byModel, setByModel] = useState<Array<{ model_ref: string; calls: number; cost_estimate: number }>>([]);
  const [filterCliente, setFilterCliente] = useState("");

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      window.location.href = "/login";
      return;
    }
    listTenants().then(setClientes);
    usageSummary().then(setSummary);
    usageDaily().then(setDaily);
    usageByModel().then(setByModel);
  }, []);

  useEffect(() => {
    usageDaily(filterCliente || undefined).then(setDaily);
    usageByModel(filterCliente || undefined).then(setByModel);
  }, [filterCliente]);

  const totalCost = summary.reduce((s, r) => s + r.cost_estimate, 0);
  const totalCalls = summary.reduce((s, r) => s + r.calls, 0);

  return (
    <AppShell>
      <h1 className="mb-2 text-xl font-semibold text-gray-900 sm:text-2xl">Métricas de uso</h1>
      <p className="mb-6 text-sm text-gray-500 sm:mb-8">Consumo LLM no mês corrente</p>

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="card">
          <p className="text-sm text-gray-500">Chamadas LLM (mês)</p>
          <p className="mt-1 text-3xl font-semibold">{totalCalls}</p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-500">Custo estimado</p>
          <p className="mt-1 text-3xl font-semibold">${totalCost.toFixed(4)}</p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-500">Clientes com uso</p>
          <p className="mt-1 text-3xl font-semibold">{summary.length}</p>
        </div>
      </div>

      <div className="mb-4">
        <label className="mb-1.5 block text-sm text-gray-600 sm:mb-0 sm:mr-2 sm:inline">Filtrar cliente:</label>
        <select
          className="input-field w-full sm:inline-block sm:w-auto"
          value={filterCliente}
          onChange={(e) => setFilterCliente(e.target.value)}
        >
          <option value="">Todos</option>
          {clientes.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card">
          <h2 className="mb-4 font-semibold">Por cliente</h2>
          <div className="table-wrap">
          <table className="w-full min-w-[280px] text-sm">
            <thead className="text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="pb-2">Cliente</th>
                <th className="pb-2">Chamadas</th>
                <th className="pb-2">Custo</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {summary.map((r) => (
                <tr key={r.tenant_id}>
                  <td className="py-2">{r.tenant_id}</td>
                  <td className="py-2">{r.calls}</td>
                  <td className="py-2">${r.cost_estimate.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </div>

        <div className="card">
          <h2 className="mb-4 font-semibold">Por modelo</h2>
          <div className="table-wrap">
          <table className="w-full min-w-[280px] text-sm">
            <thead className="text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="pb-2">Modelo</th>
                <th className="pb-2">Chamadas</th>
                <th className="pb-2">Custo</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {byModel.map((r) => (
                <tr key={r.model_ref}>
                  <td className="py-2">{r.model_ref}</td>
                  <td className="py-2">{r.calls}</td>
                  <td className="py-2">${r.cost_estimate.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </div>

        <div className="card lg:col-span-2">
          <h2 className="mb-4 font-semibold">Série diária (30 dias)</h2>
          <div className="table-wrap">
          <table className="w-full min-w-[280px] text-sm">
            <thead className="text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="pb-2">Data</th>
                <th className="pb-2">Chamadas</th>
                <th className="pb-2">Custo</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {daily.map((r) => (
                <tr key={r.date}>
                  <td className="py-2">{r.date}</td>
                  <td className="py-2">{r.calls}</td>
                  <td className="py-2">${r.cost_estimate.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </div>
      </div>
    </AppShell>
  );
}

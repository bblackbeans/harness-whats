"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Plus, Search } from "lucide-react";
import { AppShell } from "@/components/Sidebar";
import { listTenants, Tenant } from "@/lib/api";

export default function ClientesPage() {
  const [clientes, setClientes] = useState<Tenant[]>([]);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      window.location.href = "/login";
      return;
    }
    listTenants()
      .then(setClientes)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return clientes;
    return clientes.filter(
      (c) => c.name.toLowerCase().includes(q) || c.id.toLowerCase().includes(q)
    );
  }, [clientes, search]);

  return (
    <AppShell>
      <div className="mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl">Clientes</h1>
          <p className="text-sm text-gray-500">Gerencie os clientes da plataforma</p>
        </div>
        <Link href="/clientes/novo" className="btn-primary inline-flex w-full items-center justify-center gap-2 sm:w-auto">
          <Plus className="h-4 w-4" />
          Novo cliente
        </Link>
      </div>

      <div className="card mb-6">
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            className="input-field pl-10"
            placeholder="Buscar por nome ou ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="card overflow-hidden p-0">
        {loading && <p className="p-6 text-sm text-gray-500">Carregando...</p>}
        {error && <p className="p-6 text-sm text-red-600">{error}</p>}
        {!loading && filtered.length === 0 && (
          <div className="p-10 text-center">
            <p className="text-sm text-gray-500">Nenhum cliente encontrado.</p>
            <Link href="/clientes/novo" className="mt-3 inline-block text-sm font-medium text-brand-600">
              Criar primeiro cliente
            </Link>
          </div>
        )}
        {!loading && filtered.length > 0 && (
          <div className="table-wrap">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead className="bg-gray-50 text-xs font-medium uppercase text-gray-500">
              <tr>
                <th className="px-6 py-3">Cliente</th>
                <th className="px-6 py-3">ID</th>
                <th className="px-6 py-3">Modelo</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {filtered.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 font-medium text-gray-900">{c.name}</td>
                  <td className="px-6 py-4 text-gray-500">{c.id}</td>
                  <td className="px-6 py-4 text-gray-500">{c.settings?.model?.name || "—"}</td>
                  <td className="px-6 py-4">
                    {c.active ? (
                      <span className="badge-success">Ativo</span>
                    ) : (
                      <span className="badge-neutral">Inativo</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Link
                      href={`/clientes/${c.id}`}
                      className="text-sm font-medium text-brand-600 hover:text-brand-700"
                    >
                      Gerenciar
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>
    </AppShell>
  );
}

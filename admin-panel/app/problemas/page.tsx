"use client";

import { useRouter } from "next/navigation";
import { ChevronLeft, ChevronRight, Image, RefreshCw, Trash2, Video } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Modal } from "@/components/Modal";
import { AppShell } from "@/components/Sidebar";
import { deleteProblema, listProblemas, listTenants, Problema, Tenant } from "@/lib/api";
import { formatBrasiliaDateTime } from "@/lib/datetime";

const PAGE_SIZE = 20;

const STATUS_LABELS: Record<string, string> = {
  novo: "Novo",
  em_analise: "Em análise",
  resolvido: "Resolvido",
  descartado: "Descartado",
};

const STATUS_STYLES: Record<string, string> = {
  novo: "bg-blue-50 text-blue-700",
  em_analise: "bg-amber-50 text-amber-700",
  resolvido: "bg-green-50 text-green-700",
  descartado: "bg-gray-100 text-gray-600",
};

export default function ProblemasPage() {
  const router = useRouter();
  const [items, setItems] = useState<Problema[]>([]);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [tenantFilter, setTenantFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Problema | null>(null);
  const [deleting, setDeleting] = useState(false);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const load = useCallback(async () => {
    try {
      const res = await listProblemas({
        page,
        pageSize: PAGE_SIZE,
        tenantId: tenantFilter || undefined,
        status: statusFilter || undefined,
      });
      setItems(res.items);
      setTotal(res.total);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar problemas");
    } finally {
      setLoading(false);
    }
  }, [page, tenantFilter, statusFilter]);

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      window.location.href = "/login";
      return;
    }
    listTenants().then(setTenants).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  async function confirmDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteProblema(deleteTarget.id);
      setDeleteTarget(null);
      if (items.length === 1 && page > 1) {
        setPage((p) => p - 1);
      } else {
        await load();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao excluir");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <AppShell>
      <div className="mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl">Problemas</h1>
          <p className="mt-1 text-sm text-gray-500">
            Reportes enviados pelos clientes pelo portal (bugs, sugestões e pedidos de ajuste).
          </p>
        </div>
        <button type="button" className="btn-secondary inline-flex items-center gap-2" onClick={() => load()}>
          <RefreshCw className="h-4 w-4" />
          Atualizar
        </button>
      </div>

      <div className="card mb-6 flex flex-col gap-4 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label className="mb-1 block text-sm font-medium text-gray-700">Cliente</label>
          <select
            className="input-field"
            value={tenantFilter}
            onChange={(e) => {
              setTenantFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Todos os clientes</option>
            {tenants.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </div>
        <div className="flex-1">
          <label className="mb-1 block text-sm font-medium text-gray-700">Status</label>
          <select
            className="input-field"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Todos os status</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      <div className="card overflow-hidden p-0">
        <div className="table-wrap">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="border-b border-gray-200 bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3">Data</th>
                <th className="px-4 py-3">Cliente</th>
                <th className="px-4 py-3">Título</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Origem</th>
                <th className="px-4 py-3">Mídia</th>
                <th className="px-4 py-3 w-12" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading && items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                    Carregando...
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                    Nenhum problema encontrado.
                  </td>
                </tr>
              ) : (
                items.map((p) => (
                  <tr
                    key={p.id}
                    className="cursor-pointer transition hover:bg-gray-50"
                    onClick={() => router.push(`/problemas/${p.id}`)}
                  >
                    <td className="whitespace-nowrap px-4 py-3 text-gray-600">
                      {formatBrasiliaDateTime(p.criado_em)}
                    </td>
                    <td className="px-4 py-3 text-gray-700">{p.tenant_name}</td>
                    <td className="px-4 py-3 font-medium text-gray-900">{p.titulo}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                          STATUS_STYLES[p.status] || "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {STATUS_LABELS[p.status] || p.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{p.origem}</td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2 text-gray-400">
                        {p.tem_screenshot && <Image className="h-4 w-4 text-blue-500" aria-label="Screenshot" />}
                        {p.tem_gravacao && <Video className="h-4 w-4 text-purple-500" aria-label="Gravação" />}
                        {!p.tem_screenshot && !p.tem_gravacao && <span className="text-gray-300">—</span>}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 transition hover:bg-red-50 hover:text-red-600"
                        aria-label="Excluir problema"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeleteTarget(p);
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="flex flex-col items-center justify-between gap-3 border-t border-gray-100 px-4 py-4 sm:flex-row">
          <p className="text-sm text-gray-500">
            {total} registro{total !== 1 ? "s" : ""} · página {page} de {totalPages}
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="btn-secondary inline-flex items-center gap-1 px-3 py-1.5 text-sm disabled:opacity-40"
              disabled={page <= 1 || loading}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft className="h-4 w-4" />
              Anterior
            </button>
            <button
              type="button"
              className="btn-secondary inline-flex items-center gap-1 px-3 py-1.5 text-sm disabled:opacity-40"
              disabled={page >= totalPages || loading}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Próxima
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      <Modal
        open={!!deleteTarget}
        title="Excluir problema"
        message={
          deleteTarget
            ? `Tem certeza que deseja excluir "${deleteTarget.titulo}"? Esta ação não pode ser desfeita.`
            : ""
        }
        confirmLabel={deleting ? "Excluindo..." : "Excluir"}
        cancelLabel="Cancelar"
        danger
        onConfirm={confirmDelete}
        onCancel={() => !deleting && setDeleteTarget(null)}
      />
    </AppShell>
  );
}

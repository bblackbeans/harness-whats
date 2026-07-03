"use client";

import { ArrowDownLeft, ArrowUpRight, ChevronLeft, ChevronRight, CircleDot, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/Sidebar";
import { HelpTip } from "@/components/HelpTip";
import { listOpsLogs, listTenants, OpsLogEvent, Tenant } from "@/lib/api";
import { formatBrasiliaDateTime } from "@/lib/datetime";

const PAGE_SIZE = 20;

const STATUS_STYLES: Record<string, string> = {
  received: "bg-blue-50 text-blue-700",
  replied: "bg-green-50 text-green-700",
  failed: "bg-red-50 text-red-700",
  processing: "bg-amber-50 text-amber-700",
  handed_off: "bg-purple-50 text-purple-700",
  bot_resumed: "bg-teal-50 text-teal-700",
  ignored: "bg-gray-100 text-gray-600",
  webhook_ignored: "bg-gray-100 text-gray-600",
  duplicate: "bg-gray-100 text-gray-500",
};

function DirectionIcon({ direction }: { direction: OpsLogEvent["direction"] }) {
  if (direction === "inbound") return <ArrowDownLeft className="h-4 w-4 text-blue-600" />;
  if (direction === "outbound") return <ArrowUpRight className="h-4 w-4 text-green-600" />;
  return <CircleDot className="h-4 w-4 text-gray-400" />;
}

function LogsLegend() {
  return (
    <div className="mb-6 rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
      <p className="mb-2 font-medium text-gray-800">Legenda</p>
      <ul className="space-y-1">
        <li>
          <span className="font-medium text-blue-700">Mensagem recebida</span> — cliente enviou mensagem e o
          harness aceitou o webhook.
        </li>
        <li>
          <span className="font-medium text-green-700">Resposta enviada</span> — bot respondeu no Chatwoot.
        </li>
        <li>
          <span className="font-medium text-red-700">Falha</span> — erro no processamento (veja o detalhe).
        </li>
        <li>
          <span className="font-medium text-gray-700">Webhook ignorado</span> — Chatwoot chamou o webhook, mas a
          mensagem foi descartada (ex.: atendente humano ativo, mensagem vazia).
        </li>
      </ul>
      <p className="mt-3 border-t border-gray-200 pt-3 text-xs text-gray-500">
        <strong className="text-gray-700">Chatwoot:</strong> conversas com Agent Bot ficam em status{" "}
        <em>pendente</em>, não em &quot;Abertas&quot;. No filtro de conversas, use{" "}
        <strong>Todos</strong> ou <strong>Pendentes</strong> — não só &quot;Abertas&quot;.
      </p>
    </div>
  );
}

export default function LogsPage() {
  const [events, setEvents] = useState<OpsLogEvent[]>([]);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [tenantFilter, setTenantFilter] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const logs = await listOpsLogs(page, PAGE_SIZE, tenantFilter || undefined);
      setEvents(logs.events);
      setTotal(logs.total);
      setTotalPages(logs.pages);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar logs");
    } finally {
      setLoading(false);
    }
  }, [page, tenantFilter]);

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

  useEffect(() => {
    if (!autoRefresh) return;
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [autoRefresh, load]);

  function handleTenantChange(value: string) {
    setTenantFilter(value);
    setPage(1);
  }

  return (
    <AppShell>
      <div className="mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl">Logs de mensagens</h1>
          <p className="mt-1 text-sm text-gray-500">
            Acompanhe mensagens recebidas do Chatwoot, respostas enviadas e falhas de processamento.
          </p>
        </div>
        <button type="button" className="btn-secondary inline-flex items-center gap-2" onClick={() => load()}>
          <RefreshCw className="h-4 w-4" />
          Atualizar
        </button>
      </div>

      <LogsLegend />

      <div className="card mb-6 flex flex-col gap-4 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label className="mb-1 flex items-center gap-1 text-sm font-medium text-gray-700">
            Cliente
            <HelpTip text="Filtra os eventos pelo cliente roteado via Account/Inbox ID no Chatwoot." />
          </label>
          <select
            className="input-field"
            value={tenantFilter}
            onChange={(e) => handleTenantChange(e.target.value)}
          >
            <option value="">Todos os clientes</option>
            {tenants.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.id})
              </option>
            ))}
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(e) => setAutoRefresh(e.target.checked)}
          />
          Atualizar a cada 5s
        </label>
      </div>

      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      <div className="card">
        <div className="table-wrap">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="pb-2 pr-3">Hora</th>
                <th className="pb-2 pr-3">Cliente</th>
                <th className="pb-2 pr-3">Evento</th>
                <th className="pb-2 pr-3">Conversa</th>
                <th className="pb-2 pr-3">Inbox</th>
                <th className="pb-2">Detalhe</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading && events.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-gray-500">
                    Carregando...
                  </td>
                </tr>
              ) : events.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-gray-500">
                    Nenhum evento ainda. Envie uma mensagem no Telegram/WhatsApp para gerar logs.
                  </td>
                </tr>
              ) : (
                events.map((event, index) => (
                  <tr key={`${event.ts}-${event.message_id}-${event.status}-${index}`}>
                    <td className="py-2 pr-3 whitespace-nowrap text-gray-500">{formatBrasiliaDateTime(event.ts)}</td>
                    <td className="py-2 pr-3">
                      <div className="font-medium text-gray-900">{event.tenant_name || "—"}</div>
                      {event.tenant_id ? (
                        <div className="text-xs text-gray-400">{event.tenant_id}</div>
                      ) : null}
                    </td>
                    <td className="py-2 pr-3">
                      <div className="flex items-center gap-2">
                        <DirectionIcon direction={event.direction} />
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                            STATUS_STYLES[event.status] || "bg-gray-100 text-gray-600"
                          }`}
                        >
                          {event.label}
                        </span>
                      </div>
                      {event.message_id ? (
                        <div className="mt-1 text-xs text-gray-400">msg #{event.message_id}</div>
                      ) : null}
                    </td>
                    <td className="py-2 pr-3 text-gray-700">#{event.conversation_id || "—"}</td>
                    <td className="py-2 pr-3 text-gray-500">{event.inbox_id ?? "—"}</td>
                    <td className="py-2 max-w-xs truncate text-gray-700" title={event.detail}>
                      {event.detail || "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {total > 0 && (
          <div className="mt-4 flex flex-col items-center justify-between gap-3 border-t border-gray-100 pt-4 sm:flex-row">
            <p className="text-sm text-gray-500">
              {total} evento{total !== 1 ? "s" : ""} · página {page} de {totalPages}
            </p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="btn-secondary inline-flex items-center gap-1 px-3 py-1.5 text-sm disabled:opacity-40"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                <ChevronLeft className="h-4 w-4" />
                Anterior
              </button>
              <button
                type="button"
                className="btn-secondary inline-flex items-center gap-1 px-3 py-1.5 text-sm disabled:opacity-40"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                Próxima
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}

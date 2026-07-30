"use client";

import { PortalShell } from "@/components/PortalShell";

export default function PortalFlowsPage() {
  return (
    <PortalShell>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl dark:text-gray-100">Flows</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Fora do MVP. Em breve você poderá montar roteiros/checklist por agente aqui.
        </p>
      </div>
      <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 px-4 py-10 text-center dark:border-gray-700 dark:bg-gray-900/40">
        <p className="text-sm text-gray-600 dark:text-gray-300">
          Flows não estão disponíveis neste momento. Use Orquestrador, Agentes e Tools para o atendimento.
        </p>
      </div>
    </PortalShell>
  );
}

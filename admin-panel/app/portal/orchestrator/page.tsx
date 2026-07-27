"use client";

import { OrchestratorManager } from "@/components/crm/OrchestratorManager";
import { PortalShell } from "@/components/PortalShell";
import {
  portalGetOrchestrator,
  portalListAgents,
  portalUpdateOrchestrator,
} from "@/lib/portal-api";

export default function PortalOrchestratorPage() {
  return (
    <PortalShell>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl dark:text-gray-100">Orquestrador</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Decide qual agente especializado assume a conversa no início.
        </p>
      </div>
      <OrchestratorManager
        load={portalGetOrchestrator}
        save={portalUpdateOrchestrator}
        loadSpecialists={() => portalListAgents("specialist")}
      />
    </PortalShell>
  );
}

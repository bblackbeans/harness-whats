"use client";

import { AgentsManager } from "@/components/crm/AgentsManager";
import { PortalShell } from "@/components/PortalShell";
import {
  portalCreateAgent,
  portalDeleteAgent,
  portalListAgents,
  portalUpdateAgent,
} from "@/lib/portal-api";

export default function PortalAgentsPage() {
  return (
    <PortalShell>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl dark:text-gray-100">Agentes</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Especialistas com prompt próprio. Crie as tools em Automação → Tools (regras + endpoint).
        </p>
      </div>
      <AgentsManager
        load={() => portalListAgents("specialist")}
        create={portalCreateAgent}
        update={portalUpdateAgent}
        remove={portalDeleteAgent}
      />
    </PortalShell>
  );
}

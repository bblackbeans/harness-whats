"use client";

import { FlowsManager } from "@/components/crm/FlowsManager";
import { PortalShell } from "@/components/PortalShell";
import {
  portalCreateFlow,
  portalDeleteFlow,
  portalGetFlow,
  portalImportFlow,
  portalListAgents,
  portalListFlowRuns,
  portalListFlows,
  portalPublishFlow,
  portalRecompileFlow,
  portalUpdateFlow,
} from "@/lib/portal-api";

export default function PortalFlowsPage() {
  return (
    <PortalShell>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl dark:text-gray-100">Flows</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Guia operacional opcional (roteiro/checklist). O centro da arquitetura é Orquestrador →
          Agentes → Tools; o Flow não executa a conversa.
        </p>
      </div>
      <FlowsManager
        loadAgents={() => portalListAgents("specialist")}
        loadFlows={portalListFlows}
        getFlow={portalGetFlow}
        createFlow={portalCreateFlow}
        publishFlow={portalPublishFlow}
        deleteFlow={portalDeleteFlow}
        importFlow={portalImportFlow}
        recompileFlow={portalRecompileFlow}
        updateFlow={portalUpdateFlow}
        loadRuns={portalListFlowRuns}
      />
    </PortalShell>
  );
}

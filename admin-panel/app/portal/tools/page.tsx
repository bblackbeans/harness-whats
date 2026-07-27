"use client";

import { ToolsManager } from "@/components/crm/ToolsManager";
import { PortalShell } from "@/components/PortalShell";
import {
  portalListSendableFiles,
  portalCreateAgentTool,
  portalDeleteAgentTool,
  portalGetAgentTool,
  portalListAgentTools,
  portalListAgents,
  portalUpdateAgentTool,
} from "@/lib/portal-api";

export default function PortalToolsPage() {
  return (
    <PortalShell>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl dark:text-gray-100">Tools</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Crie ferramentas por agente com regras e endpoints. O agente decide quando usá-las na
          conversa.
        </p>
      </div>
      <ToolsManager
        loadAgents={() => portalListAgents("specialist")}
        loadTools={(agentId) => portalListAgentTools(agentId)}
        getTool={portalGetAgentTool}
        createTool={portalCreateAgentTool}
        updateTool={portalUpdateAgentTool}
        deleteTool={portalDeleteAgentTool}
        loadFiles={portalListSendableFiles}
      />
    </PortalShell>
  );
}

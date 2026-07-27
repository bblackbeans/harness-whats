"use client";

import { IntegrationsManager } from "@/components/crm/IntegrationsManager";
import { PortalShell } from "@/components/PortalShell";
import {
  portalCreateHttpTool,
  portalCreateWebhook,
  portalDeleteHttpTool,
  portalDeleteWebhook,
  portalListFields,
  portalListHttpTools,
  portalListWebhooks,
  portalRegenWebhookSecret,
  portalUpdateWebhook,
} from "@/lib/portal-api";

export default function PortalIntegracoesPage() {
  return (
    <PortalShell>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl dark:text-gray-100">Integrações</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Webhooks de entrada (sistemas externos → Harness) e APIs HTTP do tenant. As tools que o
          agente usa no atendimento — com regras e endpoint — ficam em Automação → Tools.
        </p>
      </div>
      <IntegrationsManager
        loadWebhooks={portalListWebhooks}
        createWebhook={portalCreateWebhook}
        updateWebhook={portalUpdateWebhook}
        regenSecret={portalRegenWebhookSecret}
        deleteWebhook={portalDeleteWebhook}
        loadTools={portalListHttpTools}
        createTool={portalCreateHttpTool}
        deleteTool={portalDeleteHttpTool}
        loadFields={portalListFields}
      />
    </PortalShell>
  );
}

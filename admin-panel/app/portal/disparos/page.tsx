"use client";

import { CampaignsManager } from "@/components/crm/CampaignsManager";
import { PortalShell } from "@/components/PortalShell";
import {
  portalCancelCampaign,
  portalCreateCampaign,
  portalGetCampaign,
  portalListCampaigns,
  portalListContacts,
  portalScheduleCampaign,
  portalSendCampaign,
} from "@/lib/portal-api";

export default function PortalDisparosPage() {
  return (
    <PortalShell>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl dark:text-gray-100">
          Disparos WhatsApp
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Campanhas com template Meta (oficial) via Chatwoot. Envie agora ou agende por data/hora.
        </p>
      </div>
      <CampaignsManager
        loadCampaigns={portalListCampaigns}
        getCampaign={portalGetCampaign}
        createCampaign={portalCreateCampaign}
        sendCampaign={portalSendCampaign}
        scheduleCampaign={portalScheduleCampaign}
        cancelCampaign={portalCancelCampaign}
        loadContacts={() => portalListContacts()}
      />
    </PortalShell>
  );
}

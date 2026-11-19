"use client";

import { CampaignsManager } from "@/components/crm/CampaignsManager";
import { PortalShell } from "@/components/PortalShell";
import {
  portalCancelCampaign,
  portalCreateRecurring,
  portalDeleteRecurring,
  portalListRecurring,
  portalListTemplates,
  portalListMedia,
  portalUploadMedia,
  portalRunRecurring,
  portalToggleRecurring,
  portalUpdateRecurring,
  portalCreateCampaign,
  portalDeleteCampaign,
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
          Campanhas com template Meta (oficial) via Chatwoot. Envie agora, agende por data/hora ou deixe um disparo automático todo mês.
        </p>
      </div>
      <CampaignsManager
        loadCampaigns={portalListCampaigns}
        getCampaign={portalGetCampaign}
        createCampaign={portalCreateCampaign}
        sendCampaign={portalSendCampaign}
        scheduleCampaign={portalScheduleCampaign}
        cancelCampaign={portalCancelCampaign}
        deleteCampaign={portalDeleteCampaign}
        loadContacts={() => portalListContacts()}
        loadTemplates={portalListTemplates}
        media={{ load: portalListMedia, upload: portalUploadMedia }}
        recurring={{
          list: portalListRecurring,
          create: portalCreateRecurring,
          update: portalUpdateRecurring,
          toggle: portalToggleRecurring,
          run: portalRunRecurring,
          remove: portalDeleteRecurring,
        }}
      />
    </PortalShell>
  );
}

"use client";

import { MediaLibrary } from "@/components/crm/MediaLibrary";
import { PortalShell } from "@/components/PortalShell";
import { portalDeleteMedia, portalListMedia, portalUploadMedia } from "@/lib/portal-api";

export default function PortalMidiaPage() {
  return (
    <PortalShell>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl dark:text-gray-100">Banco de imagens</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Envie imagens e copie o link público para usar no cabeçalho dos disparos de template.
        </p>
      </div>
      <MediaLibrary load={portalListMedia} upload={portalUploadMedia} remove={portalDeleteMedia} />
    </PortalShell>
  );
}

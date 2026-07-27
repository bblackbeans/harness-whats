"use client";

import { FilesManager } from "@/components/crm/FilesManager";
import { PortalShell } from "@/components/PortalShell";
import {
  portalDeleteSendableFile,
  portalListSendableFiles,
  portalUpdateSendableFile,
  portalUploadSendableFile,
} from "@/lib/portal-api";

export default function PortalArquivosPage() {
  return (
    <PortalShell>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl dark:text-gray-100">Arquivos para envio</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Biblioteca de PDFs, imagens e documentos que o chatbot pode enviar nas conversas.
        </p>
      </div>
      <FilesManager
        load={portalListSendableFiles}
        upload={portalUploadSendableFile}
        update={portalUpdateSendableFile}
        remove={portalDeleteSendableFile}
      />
    </PortalShell>
  );
}

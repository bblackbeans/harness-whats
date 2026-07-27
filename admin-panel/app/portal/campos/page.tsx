"use client";

import { FieldsManager } from "@/components/crm/FieldsManager";
import { PortalShell } from "@/components/PortalShell";
import { portalCreateField, portalDeleteField, portalListFields } from "@/lib/portal-api";

export default function PortalCamposPage() {
  return (
    <PortalShell>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl dark:text-gray-100">Campos e variáveis</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Todo contato já tem <strong>telefone</strong>, <strong>nome</strong> e <strong>email</strong>.
          Abaixo você cria campos extras. A IA salva respostas neles e você usa como{" "}
          <code>{"{{chave}}"}</code> nas integrações.
        </p>
      </div>
      <FieldsManager load={portalListFields} create={portalCreateField} remove={portalDeleteField} />
    </PortalShell>
  );
}

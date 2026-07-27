"use client";

import { ContactsManager } from "@/components/crm/ContactsManager";
import { PortalShell } from "@/components/PortalShell";
import {
  portalCreateContact,
  portalDeleteContact,
  portalListContacts,
  portalListFields,
  portalUpdateContact,
} from "@/lib/portal-api";

export default function PortalContatosPage() {
  return (
    <PortalShell>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl dark:text-gray-100">Contatos</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Perfis persistentes por telefone — veja e edite os campos salvos pela IA ou pelas integrações.
        </p>
      </div>
      <ContactsManager
        loadContacts={portalListContacts}
        loadFields={portalListFields}
        create={portalCreateContact}
        update={portalUpdateContact}
        remove={portalDeleteContact}
      />
    </PortalShell>
  );
}

"use client";

import type { MetaTemplate } from "@/lib/portal-api";

type Comp = {
  type?: string;
  format?: string;
  text?: string;
  buttons?: Array<{ text?: string }>;
};

/** Balão estilo WhatsApp com o conteúdo do template Meta aprovado. */
export function WhatsAppPreview({
  template,
  imageUrl,
}: {
  template: MetaTemplate | null;
  imageUrl?: string;
}) {
  if (!template) return null;
  const comps = (template.components || []) as Comp[];
  const header = comps.find((c) => (c.type || "").toUpperCase() === "HEADER");
  const body = comps.find((c) => (c.type || "").toUpperCase() === "BODY");
  const footer = comps.find((c) => (c.type || "").toUpperCase() === "FOOTER");
  const buttons = comps.find((c) => (c.type || "").toUpperCase() === "BUTTONS")?.buttons || [];
  const hasVars = /\{\{\s*\d+\s*\}\}/.test(`${body?.text || ""}${header?.text || ""}`);
  const headerFormat = (header?.format || "").toUpperCase();

  return (
    <div className="rounded-lg bg-[#e5ddd5] p-3 dark:bg-[#0b141a]">
      <div className="max-w-xs rounded-lg bg-white p-2 text-sm text-gray-900 shadow dark:bg-[#202c33] dark:text-gray-100">
        {headerFormat === "IMAGE" &&
          (imageUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={imageUrl} alt="Cabeçalho" className="mb-2 max-h-48 w-full rounded object-cover" />
          ) : (
            <div className="mb-2 flex h-28 items-center justify-center rounded bg-gray-200 text-xs text-gray-500 dark:bg-gray-700 dark:text-gray-300">
              Imagem do cabeçalho (informe a URL)
            </div>
          ))}
        {headerFormat === "TEXT" && header?.text && (
          <p className="mb-1 font-semibold">{header.text}</p>
        )}
        {body?.text ? (
          <p className="whitespace-pre-wrap">{body.text}</p>
        ) : (
          <p className="text-xs text-gray-500">Sem corpo de texto disponível.</p>
        )}
        {footer?.text && <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{footer.text}</p>}
        <p className="mt-1 text-right text-[10px] text-gray-400">12:00</p>
      </div>
      {buttons.map((b, i) => (
        <div
          key={i}
          className="mt-1 max-w-xs rounded-lg bg-white py-1.5 text-center text-sm font-medium text-sky-600 shadow dark:bg-[#202c33] dark:text-sky-400"
        >
          {b.text}
        </div>
      ))}
      <p className="mt-2 text-[11px] text-gray-600 dark:text-gray-400">
        {template.status ? `Status Meta: ${template.status}` : ""}
        {template.category ? ` · ${template.category}` : ""}
      </p>
      {hasVars && (
        <p className="mt-1 text-[11px] font-medium text-amber-700 dark:text-amber-300">
          Este template tem variáveis ({"{{1}}"}…). O disparo ainda não preenche variáveis: pode ser
          rejeitado pela Meta.
        </p>
      )}
    </div>
  );
}

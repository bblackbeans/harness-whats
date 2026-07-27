"use client";

import { FormEvent, useEffect, useState } from "react";
import type { CustomField, HttpTool, InboundWebhook } from "@/lib/crm-types";

type Props = {
  loadWebhooks: () => Promise<{ webhooks: InboundWebhook[] }>;
  createWebhook: (data: {
    name: string;
    field_mapping?: Record<string, string>;
    start_conversation?: boolean;
    initial_message?: string;
  }) => Promise<InboundWebhook>;
  updateWebhook: (id: number, data: Partial<InboundWebhook>) => Promise<InboundWebhook>;
  regenSecret: (id: number) => Promise<InboundWebhook>;
  deleteWebhook: (id: number) => Promise<unknown>;
  loadTools: () => Promise<{ tools: HttpTool[] }>;
  createTool: (data: Partial<HttpTool> & { name: string; url: string }) => Promise<HttpTool>;
  deleteTool: (id: number) => Promise<unknown>;
  loadFields: () => Promise<{ fields: CustomField[] }>;
};

export function IntegrationsManager(props: Props) {
  const [webhooks, setWebhooks] = useState<InboundWebhook[]>([]);
  const [tools, setTools] = useState<HttpTool[]>([]);
  const [fields, setFields] = useState<CustomField[]>([]);
  const [error, setError] = useState("");
  const [whName, setWhName] = useState("");
  const [mappingText, setMappingText] = useState('{\n  "nome": "lead.name",\n  "email": "lead.email",\n  "phone": "lead.phone"\n}');
  const [toolName, setToolName] = useState("");
  const [toolUrl, setToolUrl] = useState("");
  const [toolMethod, setToolMethod] = useState("POST");
  const [includeFields, setIncludeFields] = useState<string[]>(["nome", "email", "phone"]);
  const [bodyTemplate, setBodyTemplate] = useState("");

  async function refresh() {
    const [w, t, f] = await Promise.all([props.loadWebhooks(), props.loadTools(), props.loadFields()]);
    setWebhooks(w.webhooks || []);
    setTools(t.tools || []);
    setFields(f.fields || []);
  }

  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, []);

  async function onCreateWebhook(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const field_mapping = JSON.parse(mappingText || "{}");
      await props.createWebhook({ name: whName, field_mapping, start_conversation: false });
      setWhName("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro no webhook");
    }
  }

  async function onCreateTool(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await props.createTool({
        name: toolName,
        url: toolUrl,
        method: toolMethod,
        include_fields: includeFields,
        body_template: bodyTemplate,
        description: `Envia contato via ${toolMethod}`,
      });
      setToolName("");
      setToolUrl("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro na API");
    }
  }

  function toggleField(key: string) {
    setIncludeFields((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));
  }

  const selectable = [
    { key: "nome", label: "Nome" },
    { key: "email", label: "Email" },
    { key: "phone", label: "Telefone" },
    ...fields.map((f) => ({ key: f.key, label: f.label })),
  ];

  return (
    <div className="space-y-10">
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Webhooks de entrada</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Cole a URL e o secret em ferramentas externas (RD Station, CRM, etc.). Envie header{" "}
            <code className="text-xs">X-Webhook-Secret</code>.
          </p>
        </div>
        <form onSubmit={onCreateWebhook} className="space-y-3 rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
          <input className="input-field w-full" placeholder="Nome do webhook" value={whName} onChange={(e) => setWhName(e.target.value)} required />
          <label className="block text-sm text-gray-600 dark:text-gray-300">
            Mapping JSON (destino ← path origem)
            <textarea className="input-field mt-1 w-full font-mono text-xs" rows={5} value={mappingText} onChange={(e) => setMappingText(e.target.value)} />
          </label>
          <button type="submit" className="btn-primary">
            Criar webhook
          </button>
        </form>
        <ul className="space-y-3">
          {webhooks.map((w) => (
            <li key={w.id} className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{w.name}</p>
                  <p className="mt-1 break-all text-xs text-gray-600 dark:text-gray-300">
                    URL: <code>{w.url}</code>
                  </p>
                  <p className="mt-1 break-all text-xs text-gray-600 dark:text-gray-300">
                    Secret: <code>{w.secret}</code>
                  </p>
                </div>
                <div className="flex gap-2">
                  <button type="button" className="btn-secondary text-sm" onClick={() => navigator.clipboard.writeText(w.url)}>
                    Copiar URL
                  </button>
                  <button
                    type="button"
                    className="btn-secondary text-sm"
                    onClick={async () => {
                      await props.regenSecret(w.id);
                      await refresh();
                    }}
                  >
                    Novo secret
                  </button>
                  <button
                    type="button"
                    className="text-sm text-red-600 dark:text-red-400"
                    onClick={async () => {
                      if (!confirm("Remover?")) return;
                      await props.deleteWebhook(w.id);
                      await refresh();
                    }}
                  >
                    Remover
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">APIs de saída</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            A IA pode chamar estas APIs. Use body com <code>{"{{campo}}"}</code> ou selecione campos do contato.
          </p>
        </div>
        <form onSubmit={onCreateTool} className="space-y-3 rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
          <div className="grid gap-3 sm:grid-cols-3">
            <input className="input-field" placeholder="Nome" value={toolName} onChange={(e) => setToolName(e.target.value)} required />
            <select className="input-field" value={toolMethod} onChange={(e) => setToolMethod(e.target.value)}>
              {["GET", "POST", "PUT", "PATCH", "DELETE"].map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
            <input className="input-field sm:col-span-1" placeholder="URL" value={toolUrl} onChange={(e) => setToolUrl(e.target.value)} required />
          </div>
          <div className="flex flex-wrap gap-2">
            {selectable.map((f) => (
              <label key={f.key} className="flex items-center gap-1 text-sm">
                <input type="checkbox" checked={includeFields.includes(f.key)} onChange={() => toggleField(f.key)} />
                {f.label}
              </label>
            ))}
          </div>
          <textarea
            className="input-field w-full font-mono text-xs"
            rows={3}
            placeholder='Body template opcional, ex: {"name":"{{nome}}","cpf":"{{cpf}}"}'
            value={bodyTemplate}
            onChange={(e) => setBodyTemplate(e.target.value)}
          />
          <button type="submit" className="btn-primary">
            Criar API
          </button>
        </form>
        <ul className="divide-y divide-gray-100 rounded-lg border border-gray-200 bg-white dark:divide-gray-800 dark:border-gray-800 dark:bg-gray-900">
          {tools.length === 0 && <li className="p-4 text-sm text-gray-500 dark:text-gray-400">Nenhuma API.</li>}
          {tools.map((t) => (
            <li key={t.id} className="flex items-center justify-between gap-3 px-4 py-3">
              <div>
                <p className="font-medium">
                  {t.name} <span className="text-xs text-gray-400 dark:text-gray-500">({t.slug})</span>
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {t.method} {t.url}
                </p>
                <p className="text-xs text-gray-400 dark:text-gray-500">Campos: {(t.include_fields || []).join(", ") || "—"}</p>
              </div>
              <button
                type="button"
                className="text-sm text-red-600 dark:text-red-400"
                onClick={async () => {
                  if (!confirm("Remover?")) return;
                  await props.deleteTool(t.id);
                  await refresh();
                }}
              >
                Remover
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

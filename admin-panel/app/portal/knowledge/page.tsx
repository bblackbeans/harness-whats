"use client";

import { useEffect, useRef, useState } from "react";
import { PortalGuide, PortalHelpLabel } from "@/components/PortalGuide";
import { PortalShell } from "@/components/PortalShell";
import { PORTAL_KNOWLEDGE_INTRO } from "@/lib/portal-help";
import {
  portalDeleteKnowledge,
  portalListKnowledge,
  portalReindexKnowledge,
  portalUploadKnowledge,
} from "@/lib/portal-api";

export default function PortalKnowledgePage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<Array<{ name: string; size: number }>>([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(true);

  async function refresh() {
    const k = await portalListKnowledge();
    setFiles(k.files || []);
  }

  useEffect(() => {
    if (!localStorage.getItem("portal_access_token")) {
      window.location.href = "/portal/login";
      return;
    }
    refresh()
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleUpload(file: File) {
    setError("");
    setSuccess("");
    await portalUploadKnowledge(file);
    await refresh();
    setSuccess(`Arquivo «${file.name}» enviado. Clique em Reindexar para o bot usar o conteúdo.`);
  }

  async function handleDelete(name: string) {
    if (!confirm(`Remover ${name}?`)) return;
    setSuccess("");
    await portalDeleteKnowledge(name);
    await refresh();
    setSuccess("Arquivo removido. Reindexe se quiser atualizar a base imediatamente.");
  }

  async function handleReindex() {
    setError("");
    await portalReindexKnowledge();
    setSuccess("Reindexação concluída — o bot já pode usar os documentos atualizados.");
  }

  return (
    <PortalShell>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl">Base de conhecimento</h1>
          <p className="mt-1 text-sm text-gray-500">Materiais que o bot consulta antes de responder.</p>
        </div>
        <div className="flex w-full flex-col gap-3 sm:w-auto">
          <div className="flex items-center justify-end gap-1">
            <button type="button" className="btn-secondary w-full sm:w-auto" onClick={handleReindex}>
              Reindexar
            </button>
            <PortalHelpLabel
              label=""
              help="Reprocessa todos os arquivos e atualiza a memória do bot. Faça isso após cada upload, remoção ou edição de conteúdo."
            />
          </div>
          <div className="flex items-center justify-end gap-1">
            <button type="button" className="btn-primary w-full sm:w-auto" onClick={() => fileRef.current?.click()}>
              Enviar arquivo
            </button>
            <PortalHelpLabel
              label=""
              help="Aceita .md (Markdown) ou .txt. O texto será dividido em trechos e buscado quando o cliente perguntar algo relacionado."
            />
          </div>
          <input
            ref={fileRef}
            type="file"
            className="hidden"
            accept=".md,.txt"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleUpload(f).catch((err) => setError(err.message));
              e.target.value = "";
            }}
          />
        </div>
      </div>

      <PortalGuide title={PORTAL_KNOWLEDGE_INTRO.title} className="mb-6">
        <p>{PORTAL_KNOWLEDGE_INTRO.body}</p>
        <p>
          <strong className="text-gray-800">{PORTAL_KNOWLEDGE_INTRO.formats}</strong>
        </p>
        <div>
          <p className="font-medium text-gray-800">Exemplos do que enviar:</p>
          <ul className="mt-1 list-inside list-disc space-y-0.5 text-gray-600">
            {PORTAL_KNOWLEDGE_INTRO.examples.map((ex) => (
              <li key={ex}>{ex}</li>
            ))}
          </ul>
        </div>
        <div>
          <p className="font-medium text-gray-800">Dicas:</p>
          <ul className="mt-1 list-inside list-disc space-y-0.5 text-gray-600">
            {PORTAL_KNOWLEDGE_INTRO.tips.map((tip) => (
              <li key={tip}>{tip}</li>
            ))}
          </ul>
        </div>
      </PortalGuide>

      {loading && <p className="text-sm text-gray-500">Carregando...</p>}
      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}
      {success && <p className="mb-4 text-sm text-green-700">{success}</p>}

      <div className="card overflow-hidden p-0">
        {files.length === 0 ? (
          <div className="p-6 text-sm text-gray-500">
            <p>Nenhum documento enviado ainda.</p>
            <p className="mt-2">
              Comece com um arquivo <code className="rounded bg-gray-100 px-1">faq.md</code> com as
              perguntas mais comuns e respostas da sua empresa.
            </p>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="w-full min-w-[400px] text-left text-sm">
              <thead className="bg-gray-50 text-xs font-medium uppercase text-gray-500">
                <tr>
                  <th className="px-6 py-3">Arquivo</th>
                  <th className="px-6 py-3">Tamanho</th>
                  <th className="px-6 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {files.map((f) => (
                  <tr key={f.name}>
                    <td className="px-6 py-4 font-medium">{f.name}</td>
                    <td className="px-6 py-4 text-gray-500">{Math.round(f.size / 1024)} KB</td>
                    <td className="px-6 py-4 text-right">
                      <button
                        type="button"
                        className="text-sm text-red-600"
                        onClick={() => handleDelete(f.name).catch((e) => setError(e.message))}
                      >
                        Remover
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </PortalShell>
  );
}

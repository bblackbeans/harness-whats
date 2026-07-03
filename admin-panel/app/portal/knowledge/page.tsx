"use client";

import { useEffect, useRef, useState } from "react";
import { PortalShell } from "@/components/PortalShell";
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
    await portalUploadKnowledge(file);
    await refresh();
  }

  async function handleDelete(name: string) {
    if (!confirm(`Remover ${name}?`)) return;
    await portalDeleteKnowledge(name);
    await refresh();
  }

  async function handleReindex() {
    await portalReindexKnowledge();
    alert("Reindexação concluída");
  }

  return (
    <PortalShell>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl">Base de conhecimento</h1>
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
          <button type="button" className="btn-secondary w-full sm:w-auto" onClick={handleReindex}>
            Reindexar
          </button>
          <button type="button" className="btn-primary w-full sm:w-auto" onClick={() => fileRef.current?.click()}>
            Upload
          </button>
          <input
            ref={fileRef}
            type="file"
            className="hidden"
            accept=".md,.txt,.pdf"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleUpload(f).catch((err) => setError(err.message));
              e.target.value = "";
            }}
          />
        </div>
      </div>

      {loading && <p className="text-sm text-gray-500">Carregando...</p>}
      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      <div className="card overflow-hidden p-0">
        {files.length === 0 ? (
          <p className="p-6 text-sm text-gray-500">Nenhum documento enviado.</p>
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

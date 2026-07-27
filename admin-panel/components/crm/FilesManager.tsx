"use client";

import { useEffect, useRef, useState } from "react";
import type { SendableFile } from "@/lib/crm-types";

type Props = {
  load: () => Promise<{ files: SendableFile[] }>;
  upload: (file: File, description: string) => Promise<SendableFile>;
  update: (id: number, description: string) => Promise<SendableFile>;
  remove: (id: number) => Promise<unknown>;
};

export function FilesManager({ load, upload, update, remove }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<SendableFile[]>([]);
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function refresh() {
    const data = await load();
    setFiles(data.files || []);
  }

  useEffect(() => {
    refresh()
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function onUpload(file: File) {
    setError("");
    await upload(file, description);
    setDescription("");
    await refresh();
  }

  if (loading) return <p className="text-sm text-gray-500 dark:text-gray-400">Carregando…</p>;

  return (
    <div className="space-y-6">
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
        <p className="mb-3 text-sm text-gray-500 dark:text-gray-400">
          Arquivos que a IA pode <strong>enviar</strong> na conversa (PDF, imagem, documento) — diferente da base de conhecimento (RAG).
        </p>
        <input
          className="input-field mb-3 w-full"
          placeholder="Descrição para a IA (ex.: Regulamento do empreendimento Aurora)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <input
          ref={fileRef}
          type="file"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onUpload(f).catch((err) => setError(err.message));
            e.target.value = "";
          }}
        />
        <button type="button" className="btn-primary" onClick={() => fileRef.current?.click()}>
          Enviar arquivo
        </button>
      </div>
      <ul className="divide-y divide-gray-100 rounded-lg border border-gray-200 bg-white dark:divide-gray-800 dark:border-gray-800 dark:bg-gray-900">
        {files.length === 0 && <li className="p-4 text-sm text-gray-500 dark:text-gray-400">Nenhum arquivo.</li>}
        {files.map((f) => (
          <li key={f.id} className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-medium text-gray-900 dark:text-gray-100">{f.original_name}</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {(f.size_bytes / 1024).toFixed(1)} KB · {f.mime_type}
              </p>
              <input
                className="input-field mt-2 w-full text-sm"
                defaultValue={f.description}
                onBlur={async (e) => {
                  if (e.target.value !== f.description) {
                    await update(f.id, e.target.value);
                    await refresh();
                  }
                }}
                placeholder="Descrição"
              />
            </div>
            <button
              type="button"
              className="text-sm text-red-600 dark:text-red-400"
              onClick={async () => {
                if (!confirm("Remover?")) return;
                await remove(f.id);
                await refresh();
              }}
            >
              Remover
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

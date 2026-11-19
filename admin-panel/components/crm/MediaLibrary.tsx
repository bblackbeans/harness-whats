"use client";

import { useEffect, useRef, useState } from "react";
import { Check, Copy, ImagePlus, Trash2, UploadCloud } from "lucide-react";
import type { MediaItem } from "@/lib/crm-types";
import { Modal } from "@/components/Modal";

/** Link público da imagem: usa PUBLIC_BASE_URL da API se houver; senão a origem do painel (/backend). */
export function mediaPublicUrl(item: MediaItem): string {
  if (item.url) return item.url;
  if (typeof window === "undefined") return item.path;
  return `${window.location.origin}/backend${item.path}`;
}

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

type Props = {
  load: () => Promise<{ media: MediaItem[] }>;
  upload: (file: File) => Promise<MediaItem>;
  remove?: (id: number) => Promise<unknown>;
  /** Modo seletor: clicar na imagem escolhe o link em vez de só visualizar. */
  onSelect?: (item: MediaItem) => void;
};

export function MediaLibrary({ load, upload, remove, onSelect }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [items, setItems] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [toDelete, setToDelete] = useState<MediaItem | null>(null);
  const [preview, setPreview] = useState<MediaItem | null>(null);

  async function refresh() {
    const data = await load();
    setItems(data.media || []);
  }

  useEffect(() => {
    refresh()
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleFiles(files: FileList | File[]) {
    const list = Array.from(files);
    if (!list.length) return;
    setError("");
    setUploading(true);
    const failures: string[] = [];
    for (const file of list) {
      try {
        await upload(file);
      } catch (e) {
        failures.push(`${file.name}: ${e instanceof Error ? e.message : "falha"}`);
      }
    }
    await refresh().catch(() => undefined);
    if (failures.length) setError(failures.join(" · "));
    setUploading(false);
  }

  async function copy(item: MediaItem) {
    const url = mediaPublicUrl(item);
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      window.prompt("Copie o link:", url);
    }
    setCopiedId(item.id);
    setTimeout(() => setCopiedId((c) => (c === item.id ? null : c)), 2000);
  }

  return (
    <div className="space-y-4">
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          void handleFiles(e.dataTransfer.files);
        }}
        className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-4 py-8 text-center transition-colors ${
          dragging
            ? "border-brand-500 bg-brand-50 dark:bg-brand-500/10"
            : "border-gray-300 bg-white dark:border-gray-700 dark:bg-gray-900"
        }`}
      >
        <UploadCloud className="h-8 w-8 text-gray-400" aria-hidden />
        <p className="mt-2 text-sm text-gray-700 dark:text-gray-200">
          Arraste imagens aqui ou{" "}
          <button
            type="button"
            className="font-medium text-brand-600 underline dark:text-brand-400"
            onClick={() => fileRef.current?.click()}
          >
            escolha do computador
          </button>
        </p>
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
          JPG, PNG, WEBP ou GIF · até 5 MB cada. Para cabeçalho de template Meta use JPG ou PNG.
        </p>
        {uploading && <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">Enviando…</p>}
        <input
          ref={fileRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files) void handleFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </div>

      {loading ? (
        <p className="text-sm text-gray-500 dark:text-gray-400">Carregando…</p>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-gray-200 bg-white p-6 text-center text-sm text-gray-500 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-400">
          <ImagePlus className="mx-auto mb-2 h-6 w-6" aria-hidden />
          Nenhuma imagem ainda. Envie a primeira acima.
        </div>
      ) : (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {items.map((item) => (
            <li
              key={item.id}
              className="overflow-hidden rounded-lg border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900"
            >
              <button
                type="button"
                className="block aspect-square w-full bg-gray-100 dark:bg-gray-800"
                onClick={() => (onSelect ? onSelect(item) : setPreview(item))}
                title={onSelect ? "Usar esta imagem" : "Ver imagem"}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={mediaPublicUrl(item)}
                  alt={item.original_name}
                  loading="lazy"
                  className="h-full w-full object-cover"
                />
              </button>
              <div className="space-y-2 p-2">
                <p className="truncate text-xs font-medium text-gray-800 dark:text-gray-100" title={item.original_name}>
                  {item.original_name}
                </p>
                <p className="text-[11px] text-gray-500 dark:text-gray-400">
                  {item.width && item.height ? `${item.width}×${item.height} · ` : ""}
                  {formatSize(item.size_bytes)}
                </p>
                <div className="flex items-center gap-1">
                  {onSelect ? (
                    <button type="button" className="btn-primary flex-1 px-2 py-1 text-xs" onClick={() => onSelect(item)}>
                      Usar
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn-secondary flex flex-1 items-center justify-center gap-1 px-2 py-1 text-xs"
                      onClick={() => void copy(item)}
                    >
                      {copiedId === item.id ? (
                        <>
                          <Check className="h-3.5 w-3.5" aria-hidden /> Copiado
                        </>
                      ) : (
                        <>
                          <Copy className="h-3.5 w-3.5" aria-hidden /> Copiar link
                        </>
                      )}
                    </button>
                  )}
                  {remove && !onSelect && (
                    <button
                      type="button"
                      className="rounded p-1.5 text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10"
                      onClick={() => setToDelete(item)}
                      title="Excluir"
                    >
                      <Trash2 className="h-4 w-4" aria-hidden />
                    </button>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      {preview && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/70 p-4"
          onClick={() => setPreview(null)}
        >
          <div className="card w-full max-w-2xl" onClick={(e) => e.stopPropagation()}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={mediaPublicUrl(preview)}
              alt={preview.original_name}
              className="mx-auto max-h-[60vh] rounded object-contain"
            />
            <p className="mt-3 text-sm font-medium text-gray-900 dark:text-gray-100">{preview.original_name}</p>
            <input
              readOnly
              className="input-field mt-2 w-full text-xs"
              value={mediaPublicUrl(preview)}
              onFocus={(e) => e.currentTarget.select()}
            />
            <div className="mt-3 flex justify-end gap-2">
              <button type="button" className="btn-secondary" onClick={() => void copy(preview)}>
                {copiedId === preview.id ? "Copiado!" : "Copiar link"}
              </button>
              <button type="button" className="btn-primary" onClick={() => setPreview(null)}>
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}

      <Modal
        open={!!toDelete}
        danger
        title="Excluir imagem?"
        message="O link público deixa de funcionar. Campanhas recorrentes que usam esta imagem vão falhar até você trocar o link."
        confirmLabel="Excluir"
        onCancel={() => setToDelete(null)}
        onConfirm={async () => {
          const target = toDelete;
          setToDelete(null);
          if (!target || !remove) return;
          try {
            await remove(target.id);
            await refresh();
          } catch (e) {
            setError(e instanceof Error ? e.message : "Erro ao excluir");
          }
        }}
      />
    </div>
  );
}

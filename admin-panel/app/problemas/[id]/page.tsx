"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Modal } from "@/components/Modal";
import { ScreenshotPreview } from "@/components/ImageLightbox";
import { AppShell } from "@/components/Sidebar";
import { deleteProblema, getProblema, Problema, updateProblema } from "@/lib/api";
import { formatBrasiliaDateTime } from "@/lib/datetime";

const STATUS_OPTIONS = [
  { value: "novo", label: "Novo" },
  { value: "em_analise", label: "Em análise" },
  { value: "resolvido", label: "Resolvido" },
  { value: "descartado", label: "Descartado" },
];

function JsonBlock({ title, data }: { title: string; data: unknown }) {
  if (!data || (Array.isArray(data) && data.length === 0)) {
    return (
      <div>
        <h3 className="mb-2 text-sm font-medium text-gray-800">{title}</h3>
        <p className="text-sm text-gray-500">Nenhum registro.</p>
      </div>
    );
  }
  return (
    <div>
      <h3 className="mb-2 text-sm font-medium text-gray-800">{title}</h3>
      <pre className="max-h-64 overflow-auto rounded-lg bg-gray-50 p-3 text-xs text-gray-700">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}

export default function ProblemaDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [problema, setProblema] = useState<Problema | null>(null);
  const [status, setStatus] = useState("");
  const [notas, setNotas] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      window.location.href = "/login";
      return;
    }
    getProblema(id)
      .then((p) => {
        setProblema(p);
        setStatus(p.status);
        setNotas(p.notas_internas || "");
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    if (!problema) return;
    setSaving(true);
    setSaved(false);
    setError("");
    try {
      const updated = await updateProblema(id, { status, notas_internas: notas });
      setProblema(updated);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    setError("");
    try {
      await deleteProblema(id);
      router.push("/problemas");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao excluir");
      setDeleting(false);
      setDeleteOpen(false);
    }
  }

  if (loading) {
    return (
      <AppShell>
        <p className="text-gray-500">Carregando...</p>
      </AppShell>
    );
  }

  if (!problema) {
    return (
      <AppShell>
        <p className="text-red-600">{error || "Problema não encontrado"}</p>
        <Link href="/problemas" className="mt-4 inline-block text-brand-700 hover:underline">
          Voltar à lista
        </Link>
      </AppShell>
    );
  }

  const ctx = problema.contexto_json || {};
  const screenshot = ctx.screenshot as { data?: string; mime?: string } | undefined;
  const recording = ctx.screen_recording as { data?: string; mime?: string; duration_ms?: number } | undefined;

  return (
    <AppShell>
      <div className="mb-6">
        <Link href="/problemas" className="text-sm text-brand-700 hover:underline">
          ← Voltar aos problemas
        </Link>
        <h1 className="mt-2 text-xl font-semibold text-gray-900 sm:text-2xl">{problema.titulo}</h1>
        <p className="mt-1 text-sm text-gray-500">
          {formatBrasiliaDateTime(problema.criado_em)} · {problema.tenant_name}
          {problema.usuario_email ? ` · ${problema.usuario_name || problema.usuario_email}` : ""}
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <section className="card">
            <h2 className="mb-3 text-sm font-semibold text-gray-900">Descrição</h2>
            <p className="whitespace-pre-wrap text-sm text-gray-700">{problema.descricao}</p>
          </section>

          {(problema.passos || (typeof ctx.passos === "string" && ctx.passos)) && (
            <section className="card">
              <h2 className="mb-3 text-sm font-semibold text-gray-900">Passos para reproduzir</h2>
              <p className="whitespace-pre-wrap text-sm text-gray-700">
                {problema.passos || (typeof ctx.passos === "string" ? ctx.passos : "")}
              </p>
            </section>
          )}

          {problema.url && (
            <section className="card">
              <h2 className="mb-2 text-sm font-semibold text-gray-900">URL</h2>
              <a href={problema.url} target="_blank" rel="noreferrer" className="break-all text-sm text-brand-700">
                {problema.url}
              </a>
            </section>
          )}

          {screenshot?.data && (
            <section className="card">
              <h2 className="mb-3 text-sm font-semibold text-gray-900">Screenshot</h2>
              <ScreenshotPreview
                src={screenshot.data}
                alt="Screenshot do reporte"
                thumbnailClassName="max-h-64"
              />
            </section>
          )}

          {recording?.data && (
            <section className="card">
              <h2 className="mb-3 text-sm font-semibold text-gray-900">
                Gravação de tela
                {recording.duration_ms ? ` (${Math.round(recording.duration_ms / 1000)}s)` : ""}
              </h2>
              <video controls className="max-w-full rounded border" src={recording.data}>
                <track kind="captions" />
              </video>
            </section>
          )}

          <section className="card space-y-4">
            <h2 className="text-sm font-semibold text-gray-900">Contexto técnico</h2>
            <JsonBlock title="Erros JavaScript" data={ctx.js_errors} />
            <JsonBlock title="Requisições com falha" data={ctx.failed_requests} />
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <h3 className="mb-1 text-sm font-medium text-gray-800">Viewport</h3>
                <p className="text-sm text-gray-600">{JSON.stringify(ctx.viewport || {})}</p>
              </div>
              <div>
                <h3 className="mb-1 text-sm font-medium text-gray-800">User-Agent</h3>
                <p className="break-all text-xs text-gray-600">{String(ctx.user_agent || "—")}</p>
              </div>
            </div>
            <p className="text-xs text-gray-500">Correlation ID: {problema.correlation_id}</p>
          </section>
        </div>

        <div>
          <form onSubmit={handleSave} className="card space-y-4">
            <h2 className="text-sm font-semibold text-gray-900">Triagem</h2>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Status</label>
              <select className="input-field w-full" value={status} onChange={(e) => setStatus(e.target.value)}>
                {STATUS_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Notas internas</label>
              <textarea
                className="input-field w-full min-h-[120px]"
                maxLength={8000}
                value={notas}
                onChange={(e) => setNotas(e.target.value)}
                placeholder="Anotações visíveis só para administradores"
              />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            {saved && <p className="text-sm text-green-700">Salvo com sucesso.</p>}
            <button type="submit" className="btn-primary w-full" disabled={saving}>
              {saving ? "Salvando..." : "Salvar"}
            </button>
            <button
              type="button"
              className="btn-secondary w-full border-red-200 text-red-700 hover:bg-red-50"
              onClick={() => setDeleteOpen(true)}
            >
              Excluir problema
            </button>
          </form>
        </div>
      </div>

      <Modal
        open={deleteOpen}
        title="Excluir problema"
        message={`Tem certeza que deseja excluir "${problema.titulo}"? Esta ação não pode ser desfeita.`}
        confirmLabel={deleting ? "Excluindo..." : "Excluir"}
        cancelLabel="Cancelar"
        danger
        onConfirm={handleDelete}
        onCancel={() => !deleting && setDeleteOpen(false)}
      />
    </AppShell>
  );
}

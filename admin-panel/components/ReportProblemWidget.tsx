"use client";

import { AlertTriangle, Camera, Loader2, Square, Video, X } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  beginGlobalPageRecording,
  captureScreenshot,
  clearReportDraft,
  collectTechnicalContext,
  endGlobalPageRecording,
  installReportProblemCollectors,
  isPageRecordingActive,
  loadReportDraft,
  saveReportDraft,
  subscribeRecordingState,
} from "@/lib/report-problem";
import { portalReportProblem } from "@/lib/portal-api";
import { ScreenshotPreview } from "@/components/ImageLightbox";

const fieldClass =
  "w-full rounded-xl border-2 border-gray-200 bg-white px-4 py-3 text-sm text-gray-900 shadow-sm transition placeholder:text-gray-400 hover:border-gray-300 focus:border-brand-500 focus:outline-none focus:ring-4 focus:ring-brand-100";

export function ReportProblemWidget() {
  const [open, setOpen] = useState(false);
  const [drawerMounted, setDrawerMounted] = useState(false);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [titulo, setTitulo] = useState("");
  const [descricao, setDescricao] = useState("");
  const [passos, setPassos] = useState("");
  const [incluirContexto, setIncluirContexto] = useState(true);
  const [screenshot, setScreenshot] = useState<{ mime: string; data: string } | null>(null);
  const [recording, setRecording] = useState<{ mime: string; data: string; duration_ms: number } | null>(null);
  const [capturing, setCapturing] = useState(false);
  const [recordingActive, setRecordingActive] = useState(false);
  const [recordingElapsed, setRecordingElapsed] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [draftRestored, setDraftRestored] = useState(false);

  const persistDraft = useCallback(
    (overrides?: Partial<{ open: boolean }>) => {
      saveReportDraft({
        titulo,
        descricao,
        passos,
        incluirContexto,
        open: overrides?.open ?? open,
      });
    },
    [titulo, descricao, passos, incluirContexto, open]
  );

  useEffect(() => {
    installReportProblemCollectors();
    const draft = loadReportDraft();
    if (draft) {
      setTitulo(draft.titulo);
      setDescricao(draft.descricao);
      setPassos(draft.passos);
      setIncluirContexto(draft.incluirContexto);
      if (draft.open) setOpen(true);
    }
    setDraftRestored(true);
  }, []);

  useEffect(() => {
    if (!draftRestored) return;
    persistDraft();
  }, [draftRestored, persistDraft]);

  useEffect(() => {
    return subscribeRecordingState(({ active, elapsedMs }) => {
      setRecordingActive(active);
      setRecordingElapsed(elapsedMs);
    });
  }, []);

  useEffect(() => {
    if (open) {
      setDrawerMounted(true);
      const frame = requestAnimationFrame(() => {
        requestAnimationFrame(() => setDrawerVisible(true));
      });
      return () => cancelAnimationFrame(frame);
    }

    setDrawerVisible(false);
    const timer = window.setTimeout(() => setDrawerMounted(false), 300);
    return () => clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    if (!drawerMounted) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !isPageRecordingActive()) closeDrawer();
    };
    document.addEventListener("keydown", onKeyDown);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = prevOverflow;
    };
  }, [drawerMounted, recordingActive]);

  function resetForm() {
    setTitulo("");
    setDescricao("");
    setPassos("");
    setScreenshot(null);
    setRecording(null);
    setError("");
    setSuccess(false);
    setIncluirContexto(true);
    clearReportDraft();
  }

  function closeDrawer() {
    if (isPageRecordingActive()) return;
    setOpen(false);
  }

  useEffect(() => {
    if (!drawerMounted && !open && !isPageRecordingActive()) resetForm();
  }, [drawerMounted, open]);

  const showRecordingUi = recordingActive || isPageRecordingActive();

  async function handleCapture() {
    setError("");
    setOpen(false);
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    setCapturing(true);
    try {
      const shot = await captureScreenshot();
      if (shot) {
        setScreenshot(shot);
      }
      setOpen(true);
    } catch (err) {
      setOpen(true);
      setError(err instanceof Error ? err.message : "Falha na captura");
    } finally {
      setCapturing(false);
    }
  }

  function handleStartRecord() {
    setError("");
    try {
      beginGlobalPageRecording();
      persistDraft({ open: false });
      setOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao iniciar gravação");
    }
  }

  async function handleStopRecord() {
    try {
      const rec = await endGlobalPageRecording();
      if (rec) {
        setRecording(rec);
      }
      setOpen(true);
    } catch (err) {
      setOpen(true);
      setError(err instanceof Error ? err.message : "Falha na gravação");
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const contexto: Record<string, unknown> = incluirContexto ? collectTechnicalContext() : { url: window.location.href };
      if (screenshot) contexto.screenshot = screenshot;
      if (recording) contexto.screen_recording = recording;

      await portalReportProblem({
        titulo: titulo.trim(),
        descricao: descricao.trim(),
        passos: passos.trim(),
        contexto,
      });
      setSuccess(true);
      setTimeout(() => closeDrawer(), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao enviar");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      {showRecordingUi && (
        <button
          type="button"
          data-report-problem-ui
          onClick={handleStopRecord}
          className="fixed bottom-6 right-6 z-[60] inline-flex items-center gap-2 rounded-full bg-red-600 px-4 py-3 text-sm font-medium text-white shadow-lg hover:bg-red-700"
        >
          <Square className="h-4 w-4 fill-current" />
          Parar gravação ({Math.floor(recordingElapsed / 1000)}s)
        </button>
      )}

      {!showRecordingUi && !capturing && (
        <button
          type="button"
          data-report-problem-ui
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-50 inline-flex items-center gap-2 rounded-full bg-brand-600 px-4 py-3 text-sm font-medium text-white shadow-lg hover:bg-brand-700"
          aria-label="Relatar problema"
        >
          <AlertTriangle className="h-4 w-4" />
          Relatar problema
        </button>
      )}

      {drawerMounted && (
        <div
          className={`fixed inset-0 z-50 flex justify-end transition-opacity duration-300 ease-in-out motion-reduce:transition-none ${
            drawerVisible ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
          }`}
          data-report-problem-ui
          aria-hidden={!drawerVisible}
        >
          <div
            className="absolute inset-0 bg-black/40 transition-opacity duration-300 ease-in-out motion-reduce:transition-none"
            onClick={closeDrawer}
            aria-hidden
          />
          <aside
            role="dialog"
            aria-modal={drawerVisible}
            aria-labelledby="report-problem-title"
            className={`relative flex h-full w-full max-w-md flex-col bg-gray-50 shadow-2xl transition-transform duration-300 ease-in-out motion-reduce:transition-none motion-reduce:transform-none ${
              drawerVisible ? "translate-x-0" : "translate-x-full"
            }`}
          >
            <div className="border-b border-gray-200 bg-gradient-to-br from-brand-50 via-white to-white px-5 pb-5 pt-5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-3">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-brand-200 bg-brand-100 text-brand-700 shadow-sm">
                    <AlertTriangle className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <h2 id="report-problem-title" className="text-xl font-bold tracking-tight text-gray-900">
                      Relatar problema
                    </h2>
                    <p className="mt-2 rounded-lg border border-brand-100 bg-white/80 px-3 py-2 text-sm leading-relaxed text-gray-600 shadow-sm">
                      Reporte um bug, sugira uma melhoria ou peça um ajuste no portal.
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={closeDrawer}
                  className="shrink-0 rounded-lg border border-gray-200 bg-white p-2 text-gray-500 shadow-sm transition hover:border-gray-300 hover:bg-gray-50 hover:text-gray-700"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="flex flex-1 flex-col overflow-y-auto px-5 py-5">
              {success ? (
                <p className="rounded-lg bg-green-50 p-4 text-sm text-green-800">
                  Obrigado! Seu reporte foi enviado com sucesso.
                </p>
              ) : (
                <div className="space-y-5">
                  <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                    <label className="mb-2 block text-sm font-semibold text-gray-800">
                      Título <span className="text-brand-600">*</span>
                    </label>
                    <input
                      className={fieldClass}
                      maxLength={200}
                      required
                      value={titulo}
                      onChange={(e) => setTitulo(e.target.value)}
                      placeholder="Resumo do problema ou sugestão"
                    />
                  </div>
                  <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                    <label className="mb-2 block text-sm font-semibold text-gray-800">
                      Descrição <span className="text-brand-600">*</span>
                    </label>
                    <textarea
                      className={`${fieldClass} min-h-[112px] resize-y`}
                      maxLength={8000}
                      required
                      value={descricao}
                      onChange={(e) => setDescricao(e.target.value)}
                      placeholder="Descreva o que aconteceu ou o que você gostaria de ver"
                    />
                  </div>
                  <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                    <label className="mb-2 block text-sm font-semibold text-gray-800">
                      Passos para reproduzir
                      <span className="ml-1 text-xs font-normal text-gray-500">(opcional)</span>
                    </label>
                    <textarea
                      className={`${fieldClass} min-h-[88px] resize-y`}
                      maxLength={8000}
                      value={passos}
                      onChange={(e) => setPassos(e.target.value)}
                      placeholder="1) Abri o portal…  2) Cliquei em…"
                    />
                  </div>

                  <div className="rounded-xl border border-dashed border-gray-300 bg-white px-4 py-3 text-xs leading-relaxed text-gray-600">
                    <span className="font-medium text-gray-700">Dica:</span> screenshot captura a página atual. A
                    gravação continua ao navegar entre Prompts, Conhecimento etc. — só para quando você clicar em{" "}
                    <span className="font-medium text-gray-800">Parar gravação</span>.
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      className="btn-secondary inline-flex items-center gap-2 text-sm"
                      onClick={handleCapture}
                      disabled={capturing || showRecordingUi}
                    >
                      {capturing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Camera className="h-4 w-4" />}
                      Capturar página
                    </button>
                    <button
                      type="button"
                      className="btn-secondary inline-flex items-center gap-2 text-sm"
                      onClick={handleStartRecord}
                      disabled={capturing || showRecordingUi}
                    >
                      <Video className="h-4 w-4" />
                      Gravar página
                    </button>
                  </div>

                  {screenshot && (
                    <div className="rounded-xl border border-gray-200 bg-white p-3 shadow-sm">
                      <p className="mb-2 text-xs font-medium text-gray-700">Screenshot da página anexado</p>
                      <ScreenshotPreview src={screenshot.data} alt="Screenshot anexado" thumbnailClassName="max-h-32" />
                      <button
                        type="button"
                        className="mt-2 text-xs text-red-600 hover:underline"
                        onClick={() => setScreenshot(null)}
                      >
                        Remover screenshot
                      </button>
                    </div>
                  )}

                  {recording && (
                    <div className="rounded-xl border border-gray-200 bg-white p-3 text-sm text-gray-600 shadow-sm">
                      Gravação anexada ({Math.round(recording.duration_ms / 1000)}s)
                      <button
                        type="button"
                        className="ml-2 text-xs text-red-600 hover:underline"
                        onClick={() => setRecording(null)}
                      >
                        Remover
                      </button>
                    </div>
                  )}

                  <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-gray-200 bg-white p-4 text-sm text-gray-700 shadow-sm">
                    <input
                      type="checkbox"
                      className="mt-0.5 h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
                      checked={incluirContexto}
                      onChange={(e) => setIncluirContexto(e.target.checked)}
                    />
                    <span>Incluir contexto técnico (erros JS, requisições falhas, navegador)</span>
                  </label>

                  {error && <p className="text-sm text-red-600">{error}</p>}
                </div>
              )}

              {!success && (
                <div className="mt-auto flex gap-3 border-t border-gray-200 bg-gray-50/80 pt-5">
                  <button type="button" className="btn-secondary flex-1" onClick={closeDrawer}>
                    Cancelar
                  </button>
                  <button type="submit" className="btn-primary flex-1" disabled={submitting}>
                    {submitting ? "Enviando..." : "Enviar"}
                  </button>
                </div>
              )}
            </form>
          </aside>
        </div>
      )}
    </>
  );
}

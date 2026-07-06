import html2canvas from "html2canvas";

export type JsErrorEntry = {
  message: string;
  source?: string;
  line?: number;
  col?: number;
  stack?: string;
  ts: string;
};

export type FailedRequestEntry = {
  url: string;
  method: string;
  status: number;
  ts: string;
  body_preview?: string;
};

export type ReportContext = {
  url: string;
  user_agent: string;
  viewport: { width: number; height: number };
  js_errors: JsErrorEntry[];
  failed_requests: FailedRequestEntry[];
  screenshot?: { mime: string; data: string };
  screen_recording?: { mime: string; data: string; duration_ms: number };
};

export type PageRecordingSession = {
  stop: () => Promise<{ mime: string; data: string; duration_ms: number } | null>;
};

export type RecordingState = {
  active: boolean;
  elapsedMs: number;
};

const DRAFT_STORAGE_KEY = "harness-report-problem-draft";

type ReportDraft = {
  titulo: string;
  descricao: string;
  passos: string;
  incluirContexto: boolean;
  open: boolean;
};

let activeRecordingSession: PageRecordingSession | null = null;
let recordingElapsedMs = 0;
const recordingListeners = new Set<(state: RecordingState) => void>();

function notifyRecordingState() {
  const state: RecordingState = {
    active: activeRecordingSession !== null,
    elapsedMs: recordingElapsedMs,
  };
  recordingListeners.forEach((listener) => listener(state));
}

export function subscribeRecordingState(listener: (state: RecordingState) => void): () => void {
  recordingListeners.add(listener);
  listener({
    active: activeRecordingSession !== null,
    elapsedMs: recordingElapsedMs,
  });
  return () => recordingListeners.delete(listener);
}

export function isPageRecordingActive(): boolean {
  return activeRecordingSession !== null;
}

export function beginGlobalPageRecording(): void {
  if (activeRecordingSession) return;
  recordingElapsedMs = 0;
  try {
    activeRecordingSession = startPageRecording((ms) => {
      recordingElapsedMs = ms;
      notifyRecordingState();
    });
    notifyRecordingState();
  } catch (err) {
    activeRecordingSession = null;
    recordingElapsedMs = 0;
    notifyRecordingState();
    throw err;
  }
}

export async function endGlobalPageRecording(): Promise<{
  mime: string;
  data: string;
  duration_ms: number;
} | null> {
  const session = activeRecordingSession;
  activeRecordingSession = null;
  recordingElapsedMs = 0;
  notifyRecordingState();
  return session ? session.stop() : null;
}

export function saveReportDraft(draft: ReportDraft): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(draft));
  } catch {
    /* ignore quota */
  }
}

export function loadReportDraft(): ReportDraft | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(DRAFT_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as ReportDraft;
  } catch {
    return null;
  }
}

export function clearReportDraft(): void {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(DRAFT_STORAGE_KEY);
}

const MAX_JS_ERRORS = 20;
const MAX_FAILED_REQUESTS = 30;
const RECORDING_MAX_MS = 60_000;
const RECORDING_FPS = 6;
const RECORDING_SCALE_CAP = 2;
const RECORDING_BITRATE = 2_500_000;

let collectorsInstalled = false;
const jsErrors: JsErrorEntry[] = [];
const failedRequests: FailedRequestEntry[] = [];
let originalFetch: typeof fetch | null = null;

function pushJsError(entry: JsErrorEntry) {
  jsErrors.push(entry);
  if (jsErrors.length > MAX_JS_ERRORS) jsErrors.shift();
}

function pushFailedRequest(entry: FailedRequestEntry) {
  failedRequests.push(entry);
  if (failedRequests.length > MAX_FAILED_REQUESTS) failedRequests.shift();
}

function onWindowError(event: ErrorEvent) {
  pushJsError({
    message: event.message || "Erro desconhecido",
    source: event.filename,
    line: event.lineno,
    col: event.colno,
    stack: event.error?.stack,
    ts: new Date().toISOString(),
  });
}

function onUnhandledRejection(event: PromiseRejectionEvent) {
  const reason = event.reason;
  const message = reason instanceof Error ? reason.message : String(reason);
  pushJsError({
    message: `Unhandled rejection: ${message}`,
    stack: reason instanceof Error ? reason.stack : undefined,
    ts: new Date().toISOString(),
  });
}

function installFetchInterceptor() {
  if (typeof window === "undefined" || originalFetch) return;
  originalFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const input = args[0];
    const init = args[1];
    const method = (init?.method || "GET").toUpperCase();
    const url = typeof input === "string" ? input : input instanceof Request ? input.url : String(input);
    try {
      const res = await originalFetch!(...args);
      if (!res.ok && res.status >= 400) {
        let bodyPreview = "";
        try {
          const clone = res.clone();
          const text = await clone.text();
          bodyPreview = text.slice(0, 200);
        } catch {
          /* ignore */
        }
        pushFailedRequest({
          url,
          method,
          status: res.status,
          ts: new Date().toISOString(),
          body_preview: bodyPreview,
        });
      }
      return res;
    } catch (err) {
      pushFailedRequest({
        url,
        method,
        status: 0,
        ts: new Date().toISOString(),
        body_preview: err instanceof Error ? err.message : String(err),
      });
      throw err;
    }
  };
}

export function installReportProblemCollectors() {
  if (typeof window === "undefined" || collectorsInstalled) return;
  collectorsInstalled = true;
  window.addEventListener("error", onWindowError);
  window.addEventListener("unhandledrejection", onUnhandledRejection);
  installFetchInterceptor();
}

export function collectTechnicalContext(): Omit<ReportContext, "screenshot" | "screen_recording"> {
  return {
    url: typeof window !== "undefined" ? window.location.href : "",
    user_agent: typeof navigator !== "undefined" ? navigator.userAgent : "",
    viewport: {
      width: typeof window !== "undefined" ? window.innerWidth : 0,
      height: typeof window !== "undefined" ? window.innerHeight : 0,
    },
    js_errors: [...jsErrors],
    failed_requests: [...failedRequests],
  };
}

function isReportProblemUi(el: Element): boolean {
  return el.closest("[data-report-problem-ui]") !== null;
}

function captureScale(forRecording = false): number {
  const dpr = window.devicePixelRatio || 1;
  if (forRecording) return Math.min(Math.max(dpr, 1.5), RECORDING_SCALE_CAP);
  return Math.min(dpr, 1.25);
}

/** Limite alinhado ao backend (SCREENSHOT_MAX_CHARS ≈ 120k). */
const SCREENSHOT_MAX_DATA_URL_LENGTH = 115_000;

function compressCanvasToJpeg(source: HTMLCanvasElement): { mime: string; data: string } {
  const qualities = [0.8, 0.65, 0.5, 0.38, 0.28];
  const maxWidths = [source.width, 1920, 1600, 1280, 1024, 800];

  for (const maxW of maxWidths) {
    let canvas = source;
    if (maxW < source.width) {
      const ratio = maxW / source.width;
      canvas = document.createElement("canvas");
      canvas.width = Math.round(source.width * ratio);
      canvas.height = Math.round(source.height * ratio);
      const ctx = canvas.getContext("2d");
      if (!ctx) continue;
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(source, 0, 0, canvas.width, canvas.height);
    }
    for (const quality of qualities) {
      const data = canvas.toDataURL("image/jpeg", quality);
      if (data.length <= SCREENSHOT_MAX_DATA_URL_LENGTH) {
        return { mime: "image/jpeg", data };
      }
    }
  }

  const fallback = source.toDataURL("image/jpeg", 0.2);
  return { mime: "image/jpeg", data: fallback };
}

/** Captura só o que está visível nesta página (sem diálogo do navegador). */
async function capturePageCanvas(forRecording = false): Promise<HTMLCanvasElement> {
  if (typeof window === "undefined") {
    throw new Error("Captura disponível apenas no navegador");
  }

  const scale = captureScale(forRecording);

  return html2canvas(document.documentElement, {
    ignoreElements: isReportProblemUi,
    useCORS: true,
    logging: false,
    scale,
    width: window.innerWidth,
    height: window.innerHeight,
    windowWidth: window.innerWidth,
    windowHeight: window.innerHeight,
    x: window.scrollX,
    y: window.scrollY,
    scrollX: -window.scrollX,
    scrollY: -window.scrollY,
  });
}

export async function captureScreenshot(): Promise<{ mime: string; data: string } | null> {
  const canvas = await capturePageCanvas(false);
  return compressCanvasToJpeg(canvas);
}

function createMediaRecorder(stream: MediaStream): { recorder: MediaRecorder; mime: string } {
  const mimeCandidates = [
    "video/webm;codecs=vp9",
    "video/webm;codecs=vp8",
    "video/webm",
  ];

  for (const mime of mimeCandidates) {
    if (!MediaRecorder.isTypeSupported(mime)) continue;
    try {
      return {
        recorder: new MediaRecorder(stream, {
          mimeType: mime,
          videoBitsPerSecond: RECORDING_BITRATE,
        }),
        mime,
      };
    } catch {
      try {
        return { recorder: new MediaRecorder(stream, { mimeType: mime }), mime };
      } catch {
        /* tenta próximo */
      }
    }
  }

  return { recorder: new MediaRecorder(stream), mime: "video/webm" };
}

/** Grava a página atual (viewport) sem pedir escolha de aba. Clique em Parar para finalizar. */
export function startPageRecording(onTick?: (elapsedMs: number) => void): PageRecordingSession {
  if (typeof window === "undefined" || typeof MediaRecorder === "undefined") {
    throw new Error("Gravação não suportada neste navegador");
  }

  const scale = captureScale(true);
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(window.innerWidth * scale);
  canvas.height = Math.round(window.innerHeight * scale);
  const ctx = canvas.getContext("2d", { alpha: false });
  if (!ctx) throw new Error("Não foi possível iniciar a gravação");
  const paintCtx = ctx;
  paintCtx.imageSmoothingEnabled = true;
  paintCtx.imageSmoothingQuality = "high";

  const stream = canvas.captureStream(RECORDING_FPS);
  const { recorder, mime: recorderMime } = createMediaRecorder(stream);
  const chunks: Blob[] = [];
  const startedAt = Date.now();
  let stopped = false;
  let captureInFlight = false;
  const frameIntervalMs = 1000 / RECORDING_FPS;
  const outputMime = recorderMime.split(";")[0];

  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };

  try {
    recorder.start(500);
  } catch (err) {
    stream.getTracks().forEach((t) => t.stop());
    throw err instanceof Error ? err : new Error("Não foi possível iniciar a gravação");
  }

  async function paintFrame() {
    if (stopped || captureInFlight) return;
    captureInFlight = true;
    const frameStart = Date.now();
    try {
      const frame = await capturePageCanvas(true);
      if (!stopped) {
        paintCtx.clearRect(0, 0, canvas.width, canvas.height);
        paintCtx.drawImage(frame, 0, 0, canvas.width, canvas.height);
      }
    } catch {
      /* ignora frame com falha */
    } finally {
      captureInFlight = false;
      if (!stopped) {
        const elapsed = Date.now() - frameStart;
        const delay = Math.max(16, frameIntervalMs - elapsed);
        window.setTimeout(() => void paintFrame(), delay);
      }
    }
  }

  void paintFrame();

  const tickInterval = setInterval(() => {
    const elapsed = Date.now() - startedAt;
    onTick?.(elapsed);
    if (elapsed >= RECORDING_MAX_MS) {
      void finish();
    }
  }, 500);

  let finishPromise: Promise<{ mime: string; data: string; duration_ms: number } | null> | null = null;

  function finish(): Promise<{ mime: string; data: string; duration_ms: number } | null> {
    if (finishPromise) return finishPromise;

    finishPromise = new Promise((resolve, reject) => {
      if (stopped) {
        resolve(null);
        return;
      }
      stopped = true;
      clearInterval(tickInterval);

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const duration_ms = Date.now() - startedAt;
        if (chunks.length === 0) {
          resolve(null);
          return;
        }
        try {
          const blob = new Blob(chunks, { type: outputMime });
          const dataUrl = await blobToDataUrl(blob);
          resolve({
            mime: outputMime,
            data: dataUrl,
            duration_ms,
          });
        } catch (err) {
          reject(err);
        }
      };

      if (recorder.state === "recording") recorder.stop();
      else recorder.onstop?.(new Event("stop"));
    });

    return finishPromise;
  }

  return { stop: finish };
}

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

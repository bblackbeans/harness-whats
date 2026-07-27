# PROMPT DE IMPLEMENTAÇÃO — Módulo "Relatar Problema" (Sistema de RH)

> **Instrução para o agente/desenvolvedor:** Implemente este módulo completo seguindo esta especificação à risca. Não use `getDisplayMedia`. Não crie painel admin separado do app. Siga todos os pitfalls documentados — eles vêm de bugs reais já encontrados em produção.

---

## 1. Contexto do produto

Sistema de **RH / recrutamento** com dois perfis de uso no **mesmo frontend** (mesmo deploy, mesma base de código):

| Perfil | Quem é | O que faz no módulo |
|--------|--------|---------------------|
| **Recrutador** | Usuário do dia a dia (vagas, candidatos, entrevistas…) | Vê widget **"Relatar problema"** e envia bugs/sugestões com screenshot e gravação |
| **Admin** | Gestor da plataforma / TI / superusuário | Vê aba **"Problemas"** na sidebar → lista, detalhe, triagem, status, notas internas |

**Não existe app separado para admin.** É o mesmo sistema; a sidebar e as rotas mudam conforme o `role` do usuário logado.

```
┌──────────────────────────────────────────────────────────────┐
│  Sistema RH — um app, roles diferentes                        │
├────────────────────────────┬─────────────────────────────────┤
│  RECRUTADOR                │  ADMIN                           │
│  • Dashboard               │  • Dashboard                     │
│  • Vagas                   │  • Vagas (ou visão global)       │
│  • Candidatos              │  • Usuários / Empresas           │
│  • …                       │  • Problemas  ← SÓ ADMIN         │
│  • [Widget Relatar]        │  • [Widget opcional]             │
└────────────────────────────┴─────────────────────────────────┘
```

---

## 2. Objetivo do módulo (MVP)

Permitir que **recrutadores** (e opcionalmente admins) reportem problemas diretamente do painel, com:

1. **Formulário:** título*, descrição*, passos para reproduzir (opcional)
2. **Screenshot da página atual** — sem diálogo do navegador (`html2canvas`)
3. **Gravação de tela da página** — continua ao **navegar entre rotas** do painel do recrutador
4. **Contexto técnico automático:** URL, user-agent, viewport, erros JS, requests HTTP com falha
5. **Triagem no painel admin:** página `/problemas` com lista, filtros, detalhe, screenshot, vídeo, mudança de status

**Fora do escopo MVP:** upload para S3, notificação por email, purge automático de mídia antiga.

---

## 3. Requisitos não funcionais

- Coletores de erro/fetch são leves; **zero impacto** quando idle
- Gravação consome CPU **somente enquanto ativa**
- Mídia (screenshot + vídeo) em **base64 dentro de JSONB** no PostgreSQL
- Rate limit: **10 reportes/hora por usuário** (configurável)
- Feature flag: `PROBLEMAS_FEEDBACK_ENABLED=true|false`
- Não quebrar fluxos existentes de vagas/candidatos

---

## 4. Banco de dados (PostgreSQL)

### Migration

```sql
CREATE TABLE problemas (
  id VARCHAR(36) PRIMARY KEY,
  empresa_id INTEGER REFERENCES empresas(id) ON DELETE CASCADE,  -- adaptar FK ao seu modelo
  usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
  titulo VARCHAR(200) NOT NULL,
  descricao TEXT NOT NULL,
  passos TEXT DEFAULT '',
  origem VARCHAR(32) DEFAULT 'feedback',       -- feedback | recrutador | admin
  painel_origem VARCHAR(32) DEFAULT 'recrutador', -- recrutador | admin
  status VARCHAR(32) DEFAULT 'novo',           -- novo | em_analise | resolvido | descartado
  url VARCHAR(2048) DEFAULT '',
  correlation_id VARCHAR(36) NOT NULL,
  contexto_json JSONB DEFAULT '{}',
  notas_internas TEXT DEFAULT '',
  criado_em TIMESTAMPTZ DEFAULT now(),
  atualizado_em TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ix_problemas_empresa_id ON problemas(empresa_id);
CREATE INDEX ix_problemas_usuario_id ON problemas(usuario_id);
CREATE INDEX ix_problemas_status ON problemas(status);
CREATE INDEX ix_problemas_criado_em ON problemas(criado_em);
CREATE INDEX ix_problemas_painel_origem ON problemas(painel_origem);
```

> Se o sistema não tiver `empresa_id`, use o identificador de tenant/organização que já existir. O importante é poder filtrar por empresa na triagem admin.

### Campos

| Campo | Uso |
|-------|-----|
| `empresa_id` | Empresa do recrutador que reportou |
| `usuario_id` | Quem enviou |
| `painel_origem` | `recrutador` ou `admin` — de qual área do app veio |
| `contexto_json` | Mídia + contexto técnico (ver schema abaixo) |
| `notas_internas` | Só admin edita — anotações de triagem |
| `correlation_id` | UUID para rastrear no suporte |

---

## 5. API Backend

### Variáveis de ambiente

```env
PROBLEMAS_FEEDBACK_ENABLED=true
PROBLEMAS_RATE_LIMIT_PER_HOUR=10
```

### Endpoints

| Método | Rota | Role | Função |
|--------|------|------|--------|
| POST | `/api/problemas/feedback` | `recrutador`, `admin` | Criar reporte |
| GET | `/api/problemas` | `admin` | Lista paginada |
| GET | `/api/problemas/{id}` | `admin` | Detalhe completo |
| PATCH | `/api/problemas/{id}` | `admin` | Status + notas internas |
| DELETE | `/api/problemas/{id}` | `admin` | Excluir |

**Guards:** recrutador que tentar `GET /problemas` → **403**. Admin que tentar sem role → **403**.

### Schemas (Pydantic ou equivalente)

```python
class ProblemaFeedbackCreate(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=200)
    descricao: str = Field(..., min_length=1, max_length=8000)
    passos: str = Field(default="", max_length=8000)
    painel_origem: str = Field(default="recrutador")  # recrutador | admin
    correlation_id: str | None = None
    contexto: dict[str, Any] = Field(default_factory=dict)

class ProblemaUpdate(BaseModel):
    status: str | None = None
    notas_internas: str | None = Field(default=None, max_length=8000)

class ProblemaFeedbackResponse(BaseModel):
    id: str
    correlation_id: str
```

### Payload POST — exemplo real

```json
{
  "titulo": "Filtro de candidatos não aplica status",
  "descricao": "Ao selecionar 'Em entrevista' e clicar Filtrar, a lista não muda.",
  "passos": "1) Login como recrutador\n2) Ir em Candidatos\n3) Selecionar filtro\n4) Clicar Filtrar",
  "painel_origem": "recrutador",
  "contexto": {
    "url": "https://rh.empresa.com/recrutador/candidatos",
    "user_agent": "Mozilla/5.0 ...",
    "viewport": { "width": 1440, "height": 900 },
    "js_errors": [
      {
        "message": "TypeError: Cannot read properties of undefined",
        "source": "https://rh.empresa.com/_next/static/chunks/app.js",
        "line": 842,
        "col": 12,
        "stack": "TypeError: ...",
        "ts": "2026-07-08T14:30:00.000Z"
      }
    ],
    "failed_requests": [
      {
        "url": "/api/candidatos?status=entrevista",
        "method": "GET",
        "status": 500,
        "ts": "2026-07-08T14:29:58.000Z",
        "body_preview": "{\"detail\":\"Internal Server Error\"}"
      }
    ],
    "screenshot": {
      "mime": "image/jpeg",
      "data": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
    },
    "screen_recording": {
      "mime": "video/webm",
      "data": "data:video/webm;base64,GkXfo0AgQoaBAUL3gQFC8oEEQvKEIIv..."
      "duration_ms": 18400
    }
  }
}
```

### Validação backend — OBRIGATÓRIA

```python
SCREENSHOT_MAX_CHARS = 120_000       # ~115 KB data URL
VIDEO_MAX_CHARS = 7_000_000          # ~5 MB base64
VIDEO_MAX_DURATION_MS = 120_000      # máx 120s (cliente auto-stop em 60s)
CONTEXTO_MAX_CHARS = 65_536          # JSON sem mídia

VALID_STATUS = {"novo", "em_analise", "resolvido", "descartado"}
VALID_PAINEL = {"recrutador", "admin"}

def _validate_screenshot(data: dict) -> None:
    raw = str(data.get("data", ""))
    if not raw.startswith("data:image/"):
        raise HTTPException(400, "Screenshot inválido")
    if len(raw) > SCREENSHOT_MAX_CHARS:
        raise HTTPException(400, "Screenshot muito grande — comprima no cliente")

def _validate_recording(data: dict) -> None:
    mime = str(data.get("mime", "")).lower().split(";")[0]
    if mime not in {"video/webm", "video/mp4"}:
        raise HTTPException(400, "Gravação inválida")
    if len(str(data.get("data", ""))) > VIDEO_MAX_CHARS:
        raise HTTPException(400, "Gravação muito grande")
    if int(data.get("duration_ms") or 0) > VIDEO_MAX_DURATION_MS:
        raise HTTPException(400, "Gravação muito longa")
```

### Rate limit (memória, por `usuario_id`)

```python
_rate_limit: dict[int, list[float]] = {}

def _check_rate_limit(usuario_id: int) -> None:
    now = time.time()
    window = 3600.0
    hits = [t for t in _rate_limit.get(usuario_id, []) if now - t < window]
    if len(hits) >= PROBLEMAS_RATE_LIMIT_PER_HOUR:
        raise HTTPException(429, f"Limite de {PROBLEMAS_RATE_LIMIT_PER_HOUR} reportes por hora")
    hits.append(now)
    _rate_limit[usuario_id] = hits
```

### Lista vs detalhe (performance)

**Lista (`GET /problemas`):** NÃO retornar data URLs completas.

```json
{
  "items": [{
    "id": "uuid",
    "empresa_nome": "Acme Corp",
    "usuario_nome": "Maria Silva",
    "usuario_email": "maria@acme.com",
    "titulo": "Filtro não funciona",
    "status": "novo",
    "painel_origem": "recrutador",
    "url": "https://...",
    "criado_em": "2026-07-08T14:30:00Z",
    "tem_screenshot": true,
    "tem_gravacao": true
  }],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

**Detalhe (`GET /problemas/{id}`):** `contexto_json` completo com mídia.

### Query params da lista (admin)

- `empresa_id` — filtrar por empresa
- `status` — novo | em_analise | resolvido | descartado
- `painel_origem` — recrutador | admin
- `page`, `page_size` (default 20, max 100)

---

## 6. Frontend — Onde montar o quê

### Layout do recrutador

```tsx
// app/recrutador/layout.tsx (ou equivalente)
"use client";

import { usePathname } from "next/navigation";
import { ReportProblemWidget } from "@/components/ReportProblemWidget";

export default function RecrutadorLayout({ children }) {
  const pathname = usePathname();
  const isLogin = pathname.includes("/login");

  return (
    <>
      {children}
      {!isLogin && <ReportProblemWidget painelOrigem="recrutador" />}
    </>
  );
}
```

### Layout do admin (widget opcional + rota problemas)

```tsx
// app/admin/layout.tsx
export default function AdminLayout({ children }) {
  const isLogin = pathname.includes("/login");
  return (
    <>
      {children}
      {!isLogin && <ReportProblemWidget painelOrigem="admin" />}
    </>
  );
}
```

> **CRÍTICO:** O widget DEVE ficar no **layout**, não em cada página. Senão a gravação morre ao navegar.

### Sidebar admin — item condicional

```tsx
const adminMenuItems = [
  { href: "/admin/dashboard", label: "Dashboard", icon: Home },
  { href: "/admin/empresas", label: "Empresas", icon: Building },
  { href: "/admin/usuarios", label: "Usuários", icon: Users },
  { href: "/admin/problemas", label: "Problemas", icon: AlertTriangle }, // SÓ ADMIN
];

// Recrutador NÃO tem item "Problemas" no menu
```

### Rotas admin — página Problemas

| Rota | Tela |
|------|------|
| `/admin/problemas` | Lista com filtros |
| `/admin/problemas/[id]` | Detalhe + triagem |

---

## 7. Componente `ReportProblemWidget`

### Dependência

```bash
npm install html2canvas
```

### Props

```tsx
type ReportProblemWidgetProps = {
  painelOrigem: "recrutador" | "admin";
};
```

### UI obrigatória

1. **Botão flutuante** fixo `bottom-6 right-6 z-50` — ícone + "Relatar problema"
2. **Drawer lateral direito** (`max-w-md`, animação `translate-x`)
3. **Header** com gradiente, ícone, título e texto de ajuda
4. **Campos** em cards com `border-2`:
   - Título* (max 200)
   - Descrição* (textarea, max 8000)
   - Passos para reproduzir (opcional, max 8000)
5. **Dica** em caixa tracejada explicando screenshot vs gravação
6. **Botões:** "Capturar página" | "Gravar página"
7. **Checkbox:** "Incluir contexto técnico (erros JS, requisições falhas, navegador)"
8. **Preview** screenshot (thumbnail clicável) + badge gravação anexada
9. **Durante gravação:** botão vermelho fixo "Parar gravação (Xs)" — substitui o botão principal
10. **Footer:** Cancelar | Enviar

### Marcação para exclusão na captura

Todo elemento do widget (botão, drawer, overlay, botão parar) deve ter `data-report-problem-ui`:

```tsx
<button data-report-problem-ui onClick={...}>Relatar problema</button>
<div data-report-problem-ui className="fixed inset-0 ...">...</div>
```

### Fluxo — Capturar screenshot

```typescript
async function handleCapture() {
  setError("");
  setOpen(false);  // FECHAR drawer primeiro
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); // 2 frames
  setCapturing(true);
  try {
    const shot = await captureScreenshot();
    if (shot) setScreenshot(shot);  // NÃO fazer setRecording(null)
    setOpen(true);
  } catch (err) {
    setOpen(true);
    setError(err.message);
  } finally {
    setCapturing(false);
  }
}
```

### Fluxo — Iniciar gravação (ORDEM EXATA)

```typescript
function handleStartRecord() {
  setError("");
  try {
    beginGlobalPageRecording();      // 1. Singleton global PRIMEIRO
    persistDraft({ open: false });     // 2. Salva rascunho
    setOpen(false);                    // 3. Fecha drawer DEPOIS
  } catch (err) {
    setError(err.message);
  }
}

async function handleStopRecord() {
  try {
    const rec = await endGlobalPageRecording();
    if (rec) setRecording(rec);      // NÃO fazer setScreenshot(null)
    setOpen(true);
  } catch (err) {
    setOpen(true);
    setError(err.message);
  }
}
```

### Fluxo — Submit

```typescript
async function handleSubmit(e: FormEvent) {
  e.preventDefault();
  const contexto = incluirContexto
    ? collectTechnicalContext()
    : { url: window.location.href };
  if (screenshot) contexto.screenshot = screenshot;
  if (recording) contexto.screen_recording = recording;

  await api.post("/api/problemas/feedback", {
    titulo: titulo.trim(),
    descricao: descricao.trim(),
    passos: passos.trim(),
    painel_origem: painelOrigem,
    contexto,
  });

  setSuccess(true);
  clearReportDraft();
  setTimeout(() => closeDrawer(), 2000);
}
```

### Comportamentos UX

- **ESC** fecha drawer — exceto durante gravação (`!isPageRecordingActive()`)
- **Body overflow hidden** quando drawer aberto
- **Rascunho** em `sessionStorage` — persiste título/descrição ao navegar ou gravar
- **Não resetar** formulário enquanto gravação ativa
- **Sucesso:** mensagem verde 2s → fecha drawer → limpa form

---

## 8. Módulo `lib/report-problem.ts` — núcleo técnico

### Constantes (valores testados em produção)

```typescript
const DRAFT_STORAGE_KEY = "rh-report-problem-draft";
const MAX_JS_ERRORS = 20;
const MAX_FAILED_REQUESTS = 30;
const RECORDING_MAX_MS = 60_000;
const RECORDING_FPS = 6;
const RECORDING_SCALE_CAP = 2;
const RECORDING_BITRATE = 2_500_000;
const SCREENSHOT_MAX_DATA_URL_LENGTH = 115_000;
```

### Singleton de gravação (FORA do React)

```typescript
let activeRecordingSession: PageRecordingSession | null = null;
let recordingElapsedMs = 0;
const recordingListeners = new Set<(state: RecordingState) => void>();

export function beginGlobalPageRecording(): void {
  if (activeRecordingSession) return;
  recordingElapsedMs = 0;
  activeRecordingSession = startPageRecording((ms) => {
    recordingElapsedMs = ms;
    notifyRecordingState();
  });
  notifyRecordingState();
}

export async function endGlobalPageRecording() {
  const session = activeRecordingSession;
  activeRecordingSession = null;
  recordingElapsedMs = 0;
  notifyRecordingState();
  return session ? session.stop() : null;
}

export function isPageRecordingActive(): boolean {
  return activeRecordingSession !== null;
}

export function subscribeRecordingState(listener: (s: RecordingState) => void) {
  recordingListeners.add(listener);
  listener({ active: activeRecordingSession !== null, elapsedMs: recordingElapsedMs });
  return () => recordingListeners.delete(listener);
}
```

### Screenshot com html2canvas

```typescript
import html2canvas from "html2canvas";

function isReportProblemUi(el: Element): boolean {
  return el.closest("[data-report-problem-ui]") !== null;
}

async function capturePageCanvas(forRecording = false): Promise<HTMLCanvasElement> {
  const scale = forRecording
    ? Math.min(Math.max(window.devicePixelRatio || 1, 1.5), RECORDING_SCALE_CAP)
    : Math.min(window.devicePixelRatio || 1, 1.25);

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
```

### Compressão JPEG (evita 400 no backend)

```typescript
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
      const ctx = canvas.getContext("2d")!;
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(source, 0, 0, canvas.width, canvas.height);
    }
    for (const q of qualities) {
      const data = canvas.toDataURL("image/jpeg", q);
      if (data.length <= SCREENSHOT_MAX_DATA_URL_LENGTH) {
        return { mime: "image/jpeg", data };
      }
    }
  }
  return { mime: "image/jpeg", data: source.toDataURL("image/jpeg", 0.2) };
}

export async function captureScreenshot() {
  const canvas = await capturePageCanvas(false);
  return compressCanvasToJpeg(canvas);
}
```

### Gravação — html2canvas + canvas.captureStream + MediaRecorder

```typescript
export function startPageRecording(onTick?: (elapsedMs: number) => void): PageRecordingSession {
  if (typeof MediaRecorder === "undefined") {
    throw new Error("Gravação não suportada neste navegador");
  }

  const scale = Math.min(Math.max(window.devicePixelRatio || 1, 1.5), RECORDING_SCALE_CAP);
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(window.innerWidth * scale);
  canvas.height = Math.round(window.innerHeight * scale);
  const ctx = canvas.getContext("2d", { alpha: false })!;

  const stream = canvas.captureStream(RECORDING_FPS);
  const mimeCandidates = ["video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm"];
  let recorder: MediaRecorder;
  let recorderMime = "video/webm";
  for (const mime of mimeCandidates) {
    if (MediaRecorder.isTypeSupported(mime)) {
      recorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: RECORDING_BITRATE });
      recorderMime = mime;
      break;
    }
  }
  recorder ??= new MediaRecorder(stream);

  const chunks: Blob[] = [];
  const startedAt = Date.now();
  let stopped = false;
  let captureInFlight = false;
  const frameIntervalMs = 1000 / RECORDING_FPS;

  recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
  recorder.start(500);

  async function paintFrame() {
    if (stopped || captureInFlight) return;
    captureInFlight = true;
    const frameStart = Date.now();
    try {
      const frame = await capturePageCanvas(true);
      if (!stopped) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(frame, 0, 0, canvas.width, canvas.height);
      }
    } catch { /* ignora frame com falha */ }
    finally {
      captureInFlight = false;
      if (!stopped) {
        const elapsed = Date.now() - frameStart;
        const delay = Math.max(16, frameIntervalMs - elapsed);
        setTimeout(() => void paintFrame(), delay);
      }
    }
  }
  void paintFrame();

  const tickInterval = setInterval(() => {
    const elapsed = Date.now() - startedAt;
    onTick?.(elapsed);
    if (elapsed >= RECORDING_MAX_MS) void finish();
  }, 500);

  let finishPromise: Promise<...> | null = null;

  function finish() {
    if (finishPromise) return finishPromise;
    finishPromise = new Promise((resolve, reject) => {
      if (stopped) { resolve(null); return; }
      stopped = true;
      clearInterval(tickInterval);
      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        if (chunks.length === 0) { resolve(null); return; }
        const blob = new Blob(chunks, { type: recorderMime.split(";")[0] });
        const data = await blobToDataUrl(blob);
        resolve({ mime: recorderMime.split(";")[0], data, duration_ms: Date.now() - startedAt });
      };
      if (recorder.state === "recording") recorder.stop();
    });
    return finishPromise;
  }

  return { stop: finish };
}
```

### Coletores de contexto técnico

```typescript
export function installReportProblemCollectors() {
  if (collectorsInstalled) return;
  collectorsInstalled = true;
  window.addEventListener("error", onWindowError);
  window.addEventListener("unhandledrejection", onUnhandledRejection);
  // Interceptar window.fetch — registrar status >= 400 e network errors
}

export function collectTechnicalContext() {
  return {
    url: window.location.href,
    user_agent: navigator.userAgent,
    viewport: { width: window.innerWidth, height: window.innerHeight },
    js_errors: [...jsErrors],
    failed_requests: [...failedRequests],
  };
}
```

---

## 9. Componente `ImageLightbox` — ampliação de screenshot

**Problema:** drawer usa `transform` → `position: fixed` dos filhos quebra.

**Solução:** `createPortal` para `document.body`:

```tsx
import { createPortal } from "react-dom";

export function ImageLightbox({ src, alt, open, onClose }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!open || !mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/90 p-4" onClick={onClose}>
      <img src={src} alt={alt} className="max-h-[92vh] max-w-[96vw] object-contain" onClick={e => e.stopPropagation()} />
    </div>,
    document.body
  );
}
```

Usar no detalhe admin e no preview do widget.

---

## 10. Página Admin — Lista (`/admin/problemas`)

### Colunas da tabela

| Coluna | Conteúdo |
|--------|----------|
| Data | `criado_em` formatado (fuso Brasília) |
| Empresa | Nome da empresa |
| Usuário | Nome + email do recrutador |
| Título | Texto clicável |
| Painel | Badge `recrutador` / `admin` |
| Status | Badge colorido |
| Mídia | Ícone câmera se `tem_screenshot`, ícone vídeo se `tem_gravacao` |

### Filtros

- Select empresa (todas)
- Select status (todos | novo | em_analise | resolvido | descartado)
- Select painel_origem (opcional)
- Botão atualizar
- Paginação 20/página

### Ações

- Clicar na linha → `/admin/problemas/[id]`
- Excluir → modal de confirmação

### Status — cores sugeridas

```typescript
const STATUS_STYLES = {
  novo: "bg-blue-50 text-blue-700",
  em_analise: "bg-amber-50 text-amber-700",
  resolvido: "bg-green-50 text-green-700",
  descartado: "bg-gray-100 text-gray-600",
};
```

---

## 11. Página Admin — Detalhe (`/admin/problemas/[id]`)

### Seções

1. **Cabeçalho:** título, badges status + painel_origem, botão voltar
2. **Metadados:** empresa, usuário, email, URL, correlation_id, datas
3. **Descrição** e **Passos para reproduzir**
4. **Screenshot** — `ScreenshotPreview` com lightbox
5. **Gravação** — `<video controls className="w-full max-h-96 rounded-lg" src={dataUrl} />`
6. **Erros JS** — `<pre>` JSON formatado (ou "Nenhum registro")
7. **Requisições falhas** — `<pre>` JSON formatado
8. **Triagem:** select status + textarea notas internas (8000) + Salvar
9. **Excluir** — modal confirmação

### Extrair mídia do contexto_json

```typescript
const ctx = problema.contexto_json;
const screenshot = ctx?.screenshot as { mime: string; data: string } | undefined;
const recording = ctx?.screen_recording as { mime: string; data: string; duration_ms: number } | undefined;
```

---

## 12. PITFALLS — NÃO REPITA ESTES ERROS

| # | Erro | Consequência | Solução |
|---|------|--------------|---------|
| 1 | Usar `getDisplayMedia()` | Seletor de aba, gravação para ao navegar | html2canvas + captureStream |
| 2 | Widget em cada página | Gravação morre no route change | Widget no `layout.tsx` |
| 3 | State React para gravação | Perde sessão ao fechar drawer | Singleton em módulo TS |
| 4 | Fechar drawer ANTES de `beginGlobalPageRecording()` | Gravação não inicia | Ordem: begin → persistDraft → setOpen(false) |
| 5 | Capturar com drawer aberto | Screenshot mostra o formulário | Fechar drawer + 2x requestAnimationFrame |
| 6 | PNG sem compressão | HTTP 400 "Screenshot muito grande" | JPEG progressivo até 115KB |
| 7 | `setRecording(null)` ao capturar | Perde gravação anexada | Anexos independentes |
| 8 | Widget sem `data-report-problem-ui` | Aparece na captura/gravação | Marcar todos os elementos do widget |
| 9 | Lightbox dentro do drawer | Imagem torta/deslocada | `createPortal` → `document.body` |
| 10 | FPS alto / bitrate baixo | Vídeo pixelado | 6fps, scale 2x, 2.5Mbps |
| 11 | ESC durante gravação | Para gravação acidentalmente | Bloquear ESC se `isPageRecordingActive()` |
| 12 | Base64 na listagem | API lenta, frontend trava | Só flags `tem_screenshot` / `tem_gravacao` |
| 13 | Painel admin separado | Duplicação de código | Mesmo app, sidebar por role |
| 14 | Recrutador acessa `/admin/problemas` | Vazamento de dados | Guard 403 no backend E redirect no frontend |

---

## 13. Checklist de aceite (todos obrigatórios)

### Widget (recrutador + admin)
- [ ] Visível em todas as páginas autenticadas, exceto login
- [ ] Drawer abre/fecha com animação suave
- [ ] Screenshot captura página sem drawer/widget
- [ ] Screenshot < 115KB
- [ ] Gravação continua ao navegar (ex.: Candidatos → Vagas → Candidatos)
- [ ] Gravação para em "Parar" ou 60s automático
- [ ] Screenshot + gravação no mesmo reporte
- [ ] Contexto técnico com erros JS e fetch >= 400
- [ ] Rascunho persiste em sessionStorage
- [ ] POST retorna 201 `{ id, correlation_id }`
- [ ] Rate limit 429 após 10/hora

### Admin
- [ ] Aba "Problemas" só na sidebar admin
- [ ] Recrutador não vê aba nem acessa rota
- [ ] Lista paginada com filtros empresa/status
- [ ] Detalhe com screenshot (lightbox), vídeo, JSON técnico
- [ ] PATCH status + notas internas
- [ ] DELETE com confirmação
- [ ] Lista sem payload gigante

### Backend
- [ ] Migration `problemas` aplicada
- [ ] Validação de tamanho de mídia
- [ ] `PROBLEMAS_FEEDBACK_ENABLED=false` → 503
- [ ] `painel_origem` salvo corretamente

---

## 14. Ordem de implementação sugerida

1. Migration + model + schemas + `problema_service.py`
2. `POST /api/problemas/feedback` + testes de validação
3. `lib/report-problem.ts` (coletores, screenshot, gravação singleton)
4. `ReportProblemWidget.tsx` + montar nos layouts recrutador e admin
5. `ImageLightbox.tsx`
6. `GET/PATCH/DELETE` admin + guards
7. Páginas `/admin/problemas` e `/admin/problemas/[id]`
8. Item sidebar admin
9. Teste ponta a ponta: reportar → triar → resolver → excluir

---

## 15. Teste manual ponta a ponta

1. Login como **recrutador**
2. Abrir widget → preencher título/descrição
3. Clicar **Gravar página** → navegar entre 2-3 telas → **Parar gravação**
4. Clicar **Capturar página**
5. Marcar contexto técnico → **Enviar**
6. Login como **admin**
7. Ir em **Problemas** → ver reporte na lista
8. Abrir detalhe → ver screenshot, vídeo, contexto
9. Mudar status para `em_analise` → salvar
10. Tentar acessar `/admin/problemas` como recrutador → 403 ou redirect

---

## 16. Referência de implementação validada

Lógica de captura/gravação testada em produção no projeto Harness (BlackBeans). Arquivos de referência se tiver acesso ao repositório `harness-whats`:

- `admin-panel/lib/report-problem.ts`
- `admin-panel/components/ReportProblemWidget.tsx`
- `admin-panel/components/ImageLightbox.tsx`
- `ai/harness_platform/problema_service.py`

**Adaptar:** trocar `tenant_id` por `empresa_id`, adicionar `painel_origem`, montar widget nos layouts `recrutador` e `admin` do sistema RH, rota admin em `/admin/problemas`.

---

*Fim do prompt. Implemente tudo acima sem atalhos.*

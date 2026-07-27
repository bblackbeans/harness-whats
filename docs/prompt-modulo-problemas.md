# Prompt: Implementar módulo "Relatar Problema" (feedback com screenshot + gravação de tela)

Documento de especificação para repasse a outro time/sistema. Baseado na implementação real do Harness, com adaptações de arquitetura.

---

## Contexto e objetivo

Implementar um módulo de **feedback de problemas** no app do cliente (área autenticada), permitindo que o usuário reporte bugs, sugestões ou pedidos de ajuste com:

- Formulário (título, descrição, passos opcionais)
- **Screenshot da página atual** (sem diálogo do navegador)
- **Gravação de tela da página** que **continua ao navegar** entre rotas do app
- **Contexto técnico automático** (URL, user-agent, viewport, erros JS, requisições HTTP falhas)
- Triagem na **aba "Problemas"** visível apenas para **conta admin**

**Requisitos não funcionais:**

- Não impactar o resto do sistema quando idle (coletores leves; gravação só consome CPU enquanto ativa)
- Mídia embutida em JSON no PostgreSQL (JSONB) — sem S3 no MVP
- Rate limit por usuário
- Feature flag para desligar o módulo

---

## Diferença importante: não existe Painel Admin separado

**No Harness original** existem dois ambientes distintos:

- Painel Admin (`/login`) — super_admin da plataforma
- Portal do Cliente (`/portal/login`) — tenant_admin

**No sistema que vocês vão implementar, NÃO replicar isso.**

Existe **um único app** com login único. A diferença é o **tipo de conta**:

| Tipo de conta | O que vê na sidebar |
|---------------|---------------------|
| **Conta cliente** | Itens normais do produto (dashboard, prompts, conhecimento, etc.) |
| **Conta admin** | Tudo do cliente **+** aba extra **"Problemas"** |

Não é outro painel, outra URL nem outro deploy. É a **mesma interface**, com **itens condicionais na sidebar** conforme o role do usuário logado.

### Resumo visual

```
┌─────────────────────────────────────────────────┐
│  App único (mesmo login, mesma sidebar base)    │
├─────────────────────────────────────────────────┤
│  Conta CLIENTE          │  Conta ADMIN           │
│  ─────────────          │  ───────────           │
│  • Dashboard            │  • Dashboard           │
│  • Prompts              │  • Prompts             │
│  • Conhecimento         │  • Conhecimento        │
│  • [Widget Relatar]     │  • Problemas  ← extra  │
│                         │  • [Widget opcional]   │
└─────────────────────────────────────────────────┘
```

---

## Arquitetura geral

```
App único (cliente + admin no mesmo frontend)
  │
  ├── Conta cliente
  │     └── Widget flutuante fixo (todas as páginas exceto login)
  │           ├── Drawer lateral com formulário
  │           ├── Botão "Capturar página" → html2canvas
  │           ├── Botão "Gravar página" → html2canvas + canvas.captureStream + MediaRecorder
  │           └── POST /api/problemas/feedback
  │
  └── Conta admin
        └── Sidebar → aba "Problemas"
              ├── Lista paginada com filtros
              └── Detalhe (screenshot, vídeo, contexto, triagem)

Backend (FastAPI ou equivalente)
  └── problema_service → validação + rate limit + persistência

PostgreSQL
  └── tabela problemas (contexto_json JSONB com screenshot e vídeo em base64)
```

---

## Sidebar — comportamento por role

```tsx
// Exemplo conceitual
const menuItems = [
  { href: "/dashboard", label: "Visão geral", roles: ["cliente", "admin"] },
  { href: "/prompts", label: "Prompts", roles: ["cliente", "admin"] },
  { href: "/knowledge", label: "Conhecimento", roles: ["cliente", "admin"] },
  { href: "/problemas", label: "Problemas", roles: ["admin"] }, // só admin
];
```

**Regra:** renderizar na sidebar apenas itens cujo role do usuário atual está na lista `roles`.

**Conta cliente:** não vê a aba "Problemas" e não acessa essas rotas (403 se tentar URL direta).

---

## Banco de dados

### Migration PostgreSQL

```sql
CREATE TABLE problemas (
  id VARCHAR(36) PRIMARY KEY,
  tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  usuario_id INTEGER REFERENCES tenant_users(id) ON DELETE SET NULL,
  titulo VARCHAR(200) NOT NULL,
  descricao TEXT NOT NULL,
  passos TEXT DEFAULT '',
  origem VARCHAR(32) DEFAULT 'feedback',
  status VARCHAR(32) DEFAULT 'novo',  -- novo | em_analise | resolvido | descartado
  url VARCHAR(2048) DEFAULT '',
  correlation_id VARCHAR(36) NOT NULL,
  contexto_json JSONB DEFAULT '{}',
  notas_internas TEXT DEFAULT '',
  criado_em TIMESTAMPTZ DEFAULT now(),
  atualizado_em TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ix_problemas_tenant_id ON problemas(tenant_id);
CREATE INDEX ix_problemas_status ON problemas(status);
CREATE INDEX ix_problemas_criado_em ON problemas(criado_em);
```

### Modelo (campos principais)

- `id` — UUID
- `tenant_id` — cliente/empresa que reportou
- `usuario_id` — quem enviou
- `titulo`, `descricao`, `passos`
- `status` — workflow de triagem
- `url` — página onde ocorreu
- `correlation_id` — rastreio
- `contexto_json` — JSONB com mídia e contexto técnico
- `notas_internas` — só admin edita

---

## API Backend

### Variáveis de ambiente

```env
PROBLEMAS_FEEDBACK_ENABLED=true
PROBLEMAS_RATE_LIMIT_PER_HOUR=10
```

### Endpoints (app único — guards por role)

| Método | Rota | Quem pode |
|--------|------|-----------|
| POST | `/api/problemas/feedback` | Cliente autenticado |
| GET | `/api/problemas` | **Somente admin** |
| GET | `/api/problemas/{id}` | **Somente admin** |
| PATCH | `/api/problemas/{id}` | **Somente admin** |
| DELETE | `/api/problemas/{id}` | **Somente admin** |

```python
# Exemplo FastAPI
@router.get("/problemas")
def list_problemas(user = Depends(require_role("admin"))):
    ...

@router.post("/problemas/feedback")
def create_feedback(user = Depends(require_auth)):
    ...
```

### Schemas

```python
class ProblemaFeedbackCreate(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=200)
    descricao: str = Field(..., min_length=1, max_length=8000)
    passos: str = Field(default="", max_length=8000)
    correlation_id: str | None = None
    contexto: dict[str, Any] = Field(default_factory=dict)

class ProblemaUpdate(BaseModel):
    status: str | None = None          # novo | em_analise | resolvido | descartado
    notas_internas: str | None = None  # max 8000 chars

class ProblemaFeedbackResponse(BaseModel):
    id: str
    correlation_id: str
```

### Payload do POST (exemplo)

```json
{
  "titulo": "Botão salvar não responde",
  "descricao": "Ao clicar em Salvar na aba Prompts, nada acontece.",
  "passos": "1) Login\n2) Ir em Prompts\n3) Clicar Salvar",
  "contexto": {
    "url": "https://app.exemplo.com/prompts",
    "user_agent": "Mozilla/5.0 ...",
    "viewport": { "width": 1280, "height": 800 },
    "js_errors": [
      { "message": "TypeError: ...", "source": "...", "line": 42, "ts": "2026-07-07T12:00:00.000Z" }
    ],
    "failed_requests": [
      { "url": "/api/prompts", "method": "PUT", "status": 500, "ts": "...", "body_preview": "..." }
    ],
    "screenshot": {
      "mime": "image/jpeg",
      "data": "data:image/jpeg;base64,/9j/4AAQ..."
    },
    "screen_recording": {
      "mime": "video/webm",
      "data": "data:video/webm;base64,GkXf...",
      "duration_ms": 12500
    }
  }
}
```

### Validação no backend (CRÍTICO)

```python
SCREENSHOT_MAX_CHARS = 120_000      # ~115KB em data URL
VIDEO_MAX_CHARS = 7_000_000         # ~5 MB em base64
VIDEO_MAX_DURATION_MS = 120_000     # máx 120s (cliente para em 60s)
CONTEXTO_MAX_CHARS = 65_536         # resto do JSON sem mídia

def _validate_screenshot(data: dict) -> None:
    raw = str(data.get("data", ""))
    if not raw.startswith("data:image/"):
        raise HTTPException(400, "Screenshot inválido: deve ser data URL de imagem")
    if len(raw) > SCREENSHOT_MAX_CHARS:
        raise HTTPException(400, "Screenshot muito grande")

def _validate_recording(data: dict) -> None:
    mime = str(data.get("mime", "")).lower()
    if mime not in {"video/webm", "video/mp4"}:
        raise HTTPException(400, "Gravação inválida")
    if len(str(data.get("data", ""))) > VIDEO_MAX_CHARS:
        raise HTTPException(400, "Gravação muito grande")
    if int(data.get("duration_ms") or 0) > VIDEO_MAX_DURATION_MS:
        raise HTTPException(400, "Gravação muito longa")
```

### Rate limit (memória, por usuário)

```python
_rate_limit: dict[int, list[float]] = {}

def _check_rate_limit(usuario_id: int) -> None:
    now = time.time()
    hits = [t for t in _rate_limit.get(usuario_id, []) if now - t < 3600]
    if len(hits) >= PROBLEMAS_RATE_LIMIT_PER_HOUR:
        raise HTTPException(429, f"Limite de {PROBLEMAS_RATE_LIMIT_PER_HOUR} reportes por hora")
    hits.append(now)
    _rate_limit[usuario_id] = hits
```

### Lista vs detalhe (performance)

Na **listagem**, NÃO retornar data URLs completas — só flags:

```python
"tem_screenshot": bool(ctx.get("screenshot")),
"tem_gravacao": bool(ctx.get("screen_recording")),
"contexto_json": { ...truncated sem base64... }
```

No **detalhe**, retornar `contexto_json` completo com mídia.

---

## Aba "Problemas" (somente conta admin)

### Lista (`/problemas`)

- Todos os reportes enviados pelos clientes via widget
- Filtros: cliente/tenant, status
- Paginação (20/página)
- Colunas: data, cliente, título, status, ícones de screenshot/gravação
- Linha clicável → detalhe
- Excluir com modal de confirmação

### Detalhe (`/problemas/[id]`)

- Metadados (quem reportou, tenant, URL, correlation_id, datas)
- Descrição e passos para reproduzir
- Screenshot com lightbox (`createPortal` → `document.body`)
- Gravação (`<video controls src={dataUrl}>`)
- JSON de erros JS e requests falhos
- Select de status + textarea notas internas (max 8000)
- Salvar / Excluir

---

## Frontend — decisões críticas (leia antes de codar)

### ERRO 1: Não usar `getDisplayMedia` / Screen Capture API do navegador

**Problema:** abre seletor de aba/janela; UX ruim; gravação para ao trocar de página.

**Solução correta:**

- **Screenshot:** `html2canvas` no `document.documentElement`
- **Gravação:** loop de `html2canvas` → desenha em `<canvas>` oculto → `canvas.captureStream(fps)` → `MediaRecorder`

### ERRO 2: Widget dentro de cada página vs layout global

**Problema:** se o widget ficar em cada página, ao navegar a gravação **morre** (componente desmonta).

**Solução:** montar `ReportProblemWidget` no **layout global do app** (não na página de login):

```tsx
// app/layout.tsx ou layout autenticado
export default function AppLayout({ children }) {
  const isLogin = pathname === "/login";
  return (
    <>
      {children}
      {!isLogin && <ReportProblemWidget />}
    </>
  );
}
```

### ERRO 3: Gravação precisa ser singleton global (fora do React state)

**Problema:** state local do componente se perde ao fechar drawer ou navegar.

**Solução:** módulo `report-problem.ts` com variável de módulo:

```typescript
let activeRecordingSession: PageRecordingSession | null = null;

export function beginGlobalPageRecording(): void {
  if (activeRecordingSession) return;
  activeRecordingSession = startPageRecording(onTick);
}

export async function endGlobalPageRecording() {
  const session = activeRecordingSession;
  activeRecordingSession = null;
  return session ? session.stop() : null;
}
```

### ERRO 4: Ordem ao iniciar gravação

**Correto:**

1. `beginGlobalPageRecording()` — inicia sessão global
2. `persistDraft({ open: false })` — salva rascunho
3. `setOpen(false)` — **fecha o drawer** para não gravar o próprio formulário

**Errado:** fechar drawer antes de iniciar gravação → gravação não começa.

### ERRO 5: Screenshot com drawer aberto

**Problema:** captura o drawer por cima da página.

**Solução:**

```typescript
async function handleCapture() {
  setOpen(false);
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  const shot = await captureScreenshot();
  setScreenshot(shot);
  setOpen(true);
}
```

### ERRO 6: Screenshot muito grande (400 no backend)

**Problema:** PNG em alta resolução estoura `SCREENSHOT_MAX_CHARS`.

**Solução:** comprimir no cliente antes de enviar:

```typescript
const SCREENSHOT_MAX_DATA_URL_LENGTH = 115_000;

function compressCanvasToJpeg(source: HTMLCanvasElement) {
  const qualities = [0.8, 0.65, 0.5, 0.38, 0.28];
  const maxWidths = [source.width, 1920, 1600, 1280, 1024, 800];
  // redimensiona + tenta qualidades até caber no limite
  return { mime: "image/jpeg", data: dataUrl };
}
```

### ERRO 7: Screenshot e gravação se excluíam

**Problema:** ao capturar, código fazia `setRecording(null)` e vice-versa.

**Solução:** são anexos independentes — **nunca limpar um ao adicionar o outro**.

### ERRO 8: Widget aparece na captura/gravação

**Solução:** marcar UI do widget com `data-report-problem-ui` e ignorar no html2canvas:

```typescript
html2canvas(document.documentElement, {
  ignoreElements: (el) => el.closest("[data-report-problem-ui]") !== null,
  useCORS: true,
  scale: Math.min(devicePixelRatio, 1.25),
  width: window.innerWidth,
  height: window.innerHeight,
  x: window.scrollX,
  y: window.scrollY,
  scrollX: -window.scrollX,
  scrollY: -window.scrollY,
});
```

### ERRO 9: Lightbox de screenshot torto dentro do drawer

**Problema:** drawer usa `transform: translateX` → `position: fixed` dos filhos fica relativo ao drawer.

**Solução:** `createPortal(..., document.body)` no lightbox.

### ERRO 10: Gravação pixelada

**Parâmetros que funcionaram:**

```typescript
const RECORDING_FPS = 6;
const RECORDING_SCALE_CAP = 2;
const RECORDING_BITRATE = 2_500_000;
const RECORDING_MAX_MS = 60_000;
```

### ERRO 11: ESC fecha drawer durante gravação

```typescript
if (e.key === "Escape" && !isPageRecordingActive()) closeDrawer();
```

Durante gravação, só o botão "Parar gravação" deve encerrar.

---

## Frontend — módulo `report-problem.ts`

### Dependência

```bash
npm install html2canvas
```

### Coletores de contexto técnico

```typescript
export function installReportProblemCollectors() {
  window.addEventListener("error", onWindowError);
  window.addEventListener("unhandledrejection", onUnhandledRejection);
  // Interceptar fetch para registrar status >= 400
}
```

Limites: máx 20 erros JS, 30 requests falhas (FIFO).

### Gravação — algoritmo

```typescript
export function startPageRecording(onTick?: (elapsedMs: number) => void) {
  const scale = Math.min(Math.max(devicePixelRatio, 1.5), 2);
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(window.innerWidth * scale);
  canvas.height = Math.round(window.innerHeight * scale);
  const ctx = canvas.getContext("2d", { alpha: false });

  const stream = canvas.captureStream(6);
  const { recorder, mime } = createMediaRecorder(stream);
  recorder.start(500);

  async function paintFrame() {
    if (stopped || captureInFlight) return;
    captureInFlight = true;
    try {
      const frame = await capturePageCanvas(true);
      ctx.drawImage(frame, 0, 0, canvas.width, canvas.height);
    } finally {
      captureInFlight = false;
      if (!stopped) setTimeout(() => void paintFrame(), delay);
    }
  }
  void paintFrame();

  return { stop: () => Promise com blob → data URL base64 };
}
```

### Rascunho em sessionStorage

```typescript
const DRAFT_STORAGE_KEY = "app-report-problem-draft";
// saveReportDraft / loadReportDraft / clearReportDraft
```

---

## Frontend — componente `ReportProblemWidget`

### UI

- Botão flutuante fixo `bottom-6 right-6` — "Relatar problema"
- Drawer lateral direito (`max-w-md`) com animação
- Campos: título*, descrição*, passos (opcional)
- Botões: "Capturar página" | "Gravar página"
- Checkbox: incluir contexto técnico
- Preview screenshot + indicador de gravação
- Durante gravação: botão vermelho "Parar gravação (Xs)"

### Submit

```typescript
const contexto = incluirContexto ? collectTechnicalContext() : { url: window.location.href };
if (screenshot) contexto.screenshot = screenshot;
if (recording) contexto.screen_recording = recording;

await POST("/api/problemas/feedback", { titulo, descricao, passos, contexto });
```

---

## O que NÃO fazer (resumo dos erros que já passamos)

| Não fazer | Fazer em vez disso |
|-----------|-------------------|
| `navigator.mediaDevices.getDisplayMedia()` | html2canvas + canvas.captureStream |
| Widget em cada página | Widget no layout global |
| State React para sessão de gravação | Singleton global em módulo TS |
| PNG sem compressão | JPEG progressivo até ~115KB |
| Limpar gravação ao capturar screenshot | Anexos independentes |
| Lightbox dentro do drawer | `createPortal` → `document.body` |
| Gravar com drawer aberto | Fechar drawer antes de gravar/capturar |
| Retornar base64 na listagem | Só `tem_screenshot` / `tem_gravacao` |
| Painel admin separado | Conta admin no mesmo app, aba na sidebar |

---

## Checklist de aceite

- [ ] Widget visível em todas as páginas autenticadas exceto login
- [ ] Screenshot captura a página sem o drawer/widget
- [ ] Screenshot comprimido < 115KB data URL
- [ ] Gravação continua ao navegar entre rotas
- [ ] Gravação para só ao clicar "Parar" ou após 60s
- [ ] Screenshot e gravação podem coexistir no mesmo reporte
- [ ] Lightbox funciona (portal no body)
- [ ] POST retorna 201 com `id` e `correlation_id`
- [ ] Rate limit 429 após N reportes/hora
- [ ] Conta admin vê aba "Problemas" na sidebar
- [ ] Conta cliente NÃO vê aba "Problemas"
- [ ] Lista admin sem payload gigante; detalhe com mídia completa
- [ ] `PROBLEMAS_FEEDBACK_ENABLED=false` → 503 no feedback
- [ ] Migration roda no deploy

---

## Referência no Harness (código original)

Adaptar a arquitetura (app único + conta admin), mas a lógica de captura/gravação é a mesma:

- `admin-panel/components/ReportProblemWidget.tsx`
- `admin-panel/lib/report-problem.ts`
- `admin-panel/components/ImageLightbox.tsx`
- `ai/harness_platform/problema_service.py`
- `ai/alembic/versions/005_problemas.py`

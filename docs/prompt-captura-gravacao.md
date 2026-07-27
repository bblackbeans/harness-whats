# PROMPT — Captura de tela e gravação (como está no Harness e como DEVE ser)

> **Problema reportado no outro sistema:** gravação parece travada (frame a frame), screenshot com qualidade ruim, e ao clicar "Parar" fica carregando demais na finalização.
>
> Este documento explica **como a implementação de referência funciona**, **por que é assim**, e **o que está errado** quando parece travado ou lento.

---

## 1. Visão geral — o que NÃO usamos

| Abordagem | Por que NÃO usar |
|-----------|------------------|
| `navigator.mediaDevices.getDisplayMedia()` | Abre seletor de aba; gravação para ao mudar de rota; UX ruim |
| `html2canvas` a 30 FPS | **Trava o navegador** — cada frame leva 200–800ms; fila infinita |
| PNG direto no screenshot | Arquivo enorme → erro 400 no backend |
| Gravar com drawer/modal aberto | Captura o formulário por cima da página |
| `await` no stop sem feedback | Usuário acha que travou |

**O que usamos:** `html2canvas` (screenshot pontual) + loop controlado de frames (gravação) + `canvas.captureStream` + `MediaRecorder` + compressão JPEG + finalização assíncrona com UX clara.

---

## 2. Captura de tela (screenshot) — como DEVE ser

### 2.1 Fluxo correto (ordem importa)

```
1. Usuário clica "Capturar página"
2. FECHAR o drawer do formulário (setOpen(false))
3. Aguardar 2 frames de repaint (requestAnimationFrame × 2)
4. Mostrar indicador leve "capturando..." (opcional, ~1s)
5. html2canvas(document.documentElement) — só viewport visível
6. Comprimir para JPEG até caber em ~115KB
7. Guardar no state (setScreenshot)
8. REABRIR o drawer (setOpen(true))
```

**Código de referência:**

```typescript
async function handleCapture() {
  setError("");
  setOpen(false);  // 1. Fecha drawer
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))); // 2. Repaint
  setCapturing(true);
  try {
    const shot = await captureScreenshot();
    if (shot) setScreenshot(shot);  // NÃO limpar gravação aqui
    setOpen(true);
  } catch (err) {
    setOpen(true);
    setError(err.message);
  } finally {
    setCapturing(false);
  }
}
```

### 2.2 Parâmetros de qualidade do screenshot

```typescript
const SCREENSHOT_MAX_DATA_URL_LENGTH = 115_000; // alinhado ao backend

function captureScale(forRecording = false): number {
  const dpr = window.devicePixelRatio || 1;
  if (forRecording) return Math.min(Math.max(dpr, 1.5), 2);   // vídeo: até 2x
  return Math.min(dpr, 1.25);  // screenshot: até 1.25x — NÃO usar 0.5 ou 1.0 fixo
}
```

**Erro comum:** `scale: 1` ou `scale: 0.75` → imagem borrada em telas Retina.

**Correto:** `scale: Math.min(devicePixelRatio, 1.25)` → nítido sem estourar tamanho.

### 2.3 html2canvas — configuração exata

```typescript
html2canvas(document.documentElement, {
  ignoreElements: (el) => el.closest("[data-report-problem-ui]") !== null,
  useCORS: true,
  logging: false,
  scale: Math.min(window.devicePixelRatio || 1, 1.25),
  width: window.innerWidth,
  height: window.innerHeight,
  windowWidth: window.innerWidth,
  windowHeight: window.innerHeight,
  x: window.scrollX,
  y: window.scrollY,
  scrollX: -window.scrollX,
  scrollY: -window.scrollY,
});
```

**Pontos críticos:**

- `document.documentElement` — não `document.body` (pode cortar)
- `ignoreElements` — exclui botão flutuante e drawer (`data-report-problem-ui`)
- `x/y/scrollX/scrollY` — captura só o **viewport visível**, não a página inteira scrollada (mais rápido e é o que o usuário vê)

### 2.4 Compressão JPEG progressiva (qualidade boa + tamanho ok)

Screenshot **não vai cru** para o servidor. Passa por compressão:

```typescript
function compressCanvasToJpeg(source: HTMLCanvasElement) {
  const qualities = [0.8, 0.65, 0.5, 0.38, 0.28];
  const maxWidths = [source.width, 1920, 1600, 1280, 1024, 800];

  for (const maxW of maxWidths) {
    // Redimensiona se necessário (imageSmoothingQuality: "high")
    for (const quality of qualities) {
      const data = canvas.toDataURL("image/jpeg", quality);
      if (data.length <= 115_000) {
        return { mime: "image/jpeg", data };
      }
    }
  }
  return { mime: "image/jpeg", data: source.toDataURL("image/jpeg", 0.2) };
}
```

**Erro comum:** mandar PNG ou JPEG quality 0.1 direto → ou estoura limite ou fica ilegível.

**Correto:** tentar qualidade alta primeiro (0.8), só reduz se passar de 115KB.

### 2.5 Screenshot — checklist

- [ ] Drawer fechado antes de capturar
- [ ] 2× `requestAnimationFrame` após fechar
- [ ] `scale` até 1.25× DPR
- [ ] Widget ignorado via `data-report-problem-ui`
- [ ] JPEG comprimido ≤ 115KB
- [ ] Não apagar gravação anexada ao capturar screenshot

---

## 3. Gravação de tela — como DEVE ser

### 3.1 Conceito importante: SIM, é frame a frame — mas controlado

A gravação **é** uma sequência de screenshots via `html2canvas`, desenhados num `<canvas>` oculto, gravados pelo `MediaRecorder`.

**Isso é intencional.** Não é gravação nativa da GPU/tela.

**O que NÃO pode acontecer:**

- Rodar o próximo frame **antes** do anterior terminar (fila infinita → trava)
- Rodar a 30 FPS (impossível — html2canvas leva centenas de ms)
- Bloquear a UI principal durante cada frame
- Fazer html2canvas extra ao clicar "Parar"

**O que DEVE acontecer:**

- **6 FPS** fixo — suficiente para mostrar o fluxo do bug
- **Um frame por vez** (`captureInFlight` flag)
- **Delay adaptativo** entre frames
- Gravação em **singleton global** (sobrevive a navegação entre rotas)
- Ao parar: **para o loop imediatamente**, finaliza MediaRecorder, converte blob em background

### 3.2 Constantes testadas em produção

```typescript
const RECORDING_FPS = 6;              // NÃO subir para 15/30
const RECORDING_SCALE_CAP = 2;          // resolução do canvas de gravação
const RECORDING_BITRATE = 2_500_000;    // 2.5 Mbps — evita vídeo pixelado
const RECORDING_MAX_MS = 60_000;        // auto-stop em 60s
```

### 3.3 Arquitetura da gravação

```
┌─────────────────────────────────────────────────────────┐
│  Loop paintFrame (assíncrono, não bloqueante)            │
│    html2canvas → drawImage no canvas oculto              │
│    captureInFlight impede overlap                        │
│    setTimeout(delay adaptativo) → próximo frame          │
├─────────────────────────────────────────────────────────┤
│  canvas.captureStream(6)  →  MediaRecorder (webm vp9/vp8)│
│    recorder.start(500)  — chunks a cada 500ms            │
├─────────────────────────────────────────────────────────┤
│  setInterval 500ms — atualiza contador "Parar (Xs)"      │
└─────────────────────────────────────────────────────────┘
```

### 3.4 Loop de frames — código correto

```typescript
let stopped = false;
let captureInFlight = false;
const frameIntervalMs = 1000 / RECORDING_FPS; // ~166ms entre frames

async function paintFrame() {
  if (stopped || captureInFlight) return;  // ← NÃO empilhar chamadas

  captureInFlight = true;
  const frameStart = Date.now();
  try {
    const frame = await capturePageCanvas(true); // scale até 2x para vídeo
    if (!stopped) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(frame, 0, 0, canvas.width, canvas.height);
    }
  } catch {
    /* ignora frame com falha — NÃO para a gravação */
  } finally {
    captureInFlight = false;
    if (!stopped) {
      const elapsed = Date.now() - frameStart;
      const delay = Math.max(16, frameIntervalMs - elapsed);
      setTimeout(() => void paintFrame(), delay);
    }
  }
}

void paintFrame(); // inicia o loop
```

**Por que parece "travado" no sistema errado:**

| Causa | Sintoma |
|-------|---------|
| Sem `captureInFlight` | Vários html2canvas em paralelo → main thread congela |
| FPS > 10 | Nunca alcança o intervalo → fila cresce infinito |
| `await paintFrame()` em loop síncrono | Bloqueia tudo |
| html2canvas na página inteira scrollada | Cada frame leva 2–5 segundos |
| Drawer aberto durante gravação | Captura formulário, frames pesados |

**Comportamento esperado durante gravação:**

- Página **continua utilizável** (clicar, navegar entre rotas)
- Botão vermelho "Parar gravação (12s)" fixo no canto
- Pode haver **leve lentidão** (html2canvas usa CPU) — normal a 6 FPS
- **Não** deve haver spinner fullscreen nem modal bloqueando

### 3.5 Iniciar gravação — ordem EXATA

```typescript
function handleStartRecord() {
  beginGlobalPageRecording();   // 1. Inicia singleton PRIMEIRO
  persistDraft({ open: false }); // 2. Salva rascunho do form
  setOpen(false);               // 3. Fecha drawer DEPOIS
}
```

**Erro:** `setOpen(false)` antes de `beginGlobalPageRecording()` → sessão não inicia.

### 3.6 Singleton global (gravação sobrevive à navegação)

```typescript
// report-problem.ts — FORA do React
let activeRecordingSession: PageRecordingSession | null = null;

export function beginGlobalPageRecording() {
  if (activeRecordingSession) return;
  activeRecordingSession = startPageRecording((ms) => {
    recordingElapsedMs = ms;
    notifyRecordingState();
  });
}

export async function endGlobalPageRecording() {
  const session = activeRecordingSession;
  activeRecordingSession = null;  // ← UI de gravação some IMEDIATAMENTE
  recordingElapsedMs = 0;
  notifyRecordingState();
  return session ? session.stop() : null;  // ← finalização async depois
}
```

Widget montado no **`layout.tsx`**, não em cada página.

---

## 4. Finalização ao clicar "Parar" — como DEVE ser

### 4.1 O que acontece por dentro (sequência)

```
Usuário clica "Parar gravação"
    ↓
endGlobalPageRecording()
    ├─ activeRecordingSession = null     → botão vermelho SOME na hora
    ├─ notifyRecordingState()            → recordingActive = false
    └─ session.stop()                    → async:
           ├─ stopped = true              → loop paintFrame para
           ├─ clearInterval(tick)
           ├─ recorder.stop()
           ├─ onstop: Blob(chunks)
           ├─ FileReader → data URL base64  ← pode levar 0.5–3s
           └─ resolve({ mime, data, duration_ms })
    ↓
handleStopRecord recebe resultado
    ├─ setRecording(rec)
    └─ setOpen(true)                     → drawer reabre
```

### 4.2 Problema: "fica carregando na finalização"

**Causa provável no sistema errado:**

1. **Spinner fullscreen** durante `await endGlobalPageRecording()` sem o botão vermelho ter sumido antes
2. **Roda html2canvas extra** no stop para "último frame" — adiciona 500ms–2s
3. **Converte base64 na thread principal** com vídeo grande (30s em alta resolução)
4. **Não zera `activeRecordingSession` antes do `stop()`** — UI continua em modo gravação enquanto processa
5. **Abre drawer só depois** do base64 sem nenhum feedback intermediário

### 4.3 UX correta na finalização

**Implementação de referência (Harness):**

```typescript
async function handleStopRecord() {
  // NÃO mostrar spinner fullscreen aqui
  // O botão "Parar" já sumiu porque endGlobalPageRecording limpa a sessão primeiro
  try {
    const rec = await endGlobalPageRecording();
    if (rec) setRecording(rec);
    setOpen(true);
  } catch (err) {
    setOpen(true);
    setError(err.message);
  }
}
```

**Como DEVE parecer para o usuário:**

| Momento | UI |
|---------|-----|
| Clica "Parar" | Botão vermelho **some imediatamente** |
| 0–2s processando | Tela normal do app (sem overlay de loading) |
| Pronto | Drawer reabre com "Gravação anexada (18s)" |

**Melhoria opcional (se quiser feedback):**

```typescript
async function handleStopRecord() {
  setFinalizingRecording(true);  // texto discreto no canto, NÃO fullscreen
  try {
    const rec = await endGlobalPageRecording();
    if (rec) setRecording(rec);
    setOpen(true);
  } finally {
    setFinalizingRecording(false);
  }
}
```

Texto sugerido: *"Finalizando gravação…"* — pequeno, canto inferior, **não** bloqueia a tela.

### 4.4 Finalização no `stop()` — código correto

```typescript
function finish() {
  stopped = true;           // 1. Para loop de frames IMEDIATAMENTE
  clearInterval(tickInterval);

  recorder.onstop = async () => {
    stream.getTracks().forEach(t => t.stop());
    if (chunks.length === 0) { resolve(null); return; }
    const blob = new Blob(chunks, { type: outputMime });
    const dataUrl = await blobToDataUrl(blob);  // FileReader async
    resolve({ mime: outputMime, data: dataUrl, duration_ms });
  };

  if (recorder.state === "recording") recorder.stop();
}
```

**NÃO fazer no stop:**

```typescript
// ERRADO — adiciona 1–3s de espera percebida
await capturePageCanvas(true);
await paintOneLastFrame();
await compressVideo();
```

Só `recorder.stop()` e montar o Blob dos chunks já gravados.

### 4.5 Limitar tamanho do vídeo (evita finalização lenta)

- **60s máximo** de gravação (auto-stop)
- **6 FPS** — vídeo de 60s ≈ 360 frames capturados (não 1800)
- **Bitrate 2.5 Mbps** — arquivo ~15–20 MB máximo antes de base64
- Backend rejeita > ~5 MB base64 — se passar, gravação falha no submit (não no stop)

Se finalização demora > 3s, provavelmente gravaram muito tempo ou FPS alto demais.

---

## 5. Comparativo: ERRADO vs CORRETO

### Screenshot

| Aspecto | ERRADO | CORRETO (Harness) |
|---------|--------|-------------------|
| Scale | `1` fixo ou `0.5` | `min(devicePixelRatio, 1.25)` |
| Formato | PNG | JPEG com compressão progressiva |
| Drawer | Aberto na captura | Fecha → 2 rAF → captura → reabre |
| Área | Página inteira scrollada | Viewport visível (`innerWidth/Height`) |
| Widget na foto | Aparece | `ignoreElements` + `data-report-problem-ui` |

### Gravação

| Aspecto | ERRADO | CORRETO (Harness) |
|---------|--------|-------------------|
| API | `getDisplayMedia` | html2canvas + captureStream |
| FPS | 15–30 | **6** |
| Frames paralelos | Sim (sem lock) | `captureInFlight` — um por vez |
| Onde vive | State React por página | Singleton no módulo TS + layout global |
| Ao parar | Spinner fullscreen + html2canvas extra | Para loop → recorder.stop() → blob |
| UI ao parar | Botão vermelho fica até base64 pronto | Botão some **antes** do base64 |
| Qualidade vídeo | Bitrate baixo / scale 1 | scale até 2x, 2.5 Mbps |

### Finalização

| Aspecto | ERRADO | CORRETO (Harness) |
|---------|--------|-------------------|
| Sessão ativa | Mantém até base64 pronto | `activeRecordingSession = null` **primeiro** |
| Feedback | Modal "Processando..." | Nada ou toast discreto |
| Drawer | Abre só no fim sem aviso | Reabre com badge "Gravação anexada (Xs)" |
| Último frame | Captura extra no stop | Não — usa chunks já gravados |

---

## 6. MediaRecorder — detalhes

```typescript
const mimeCandidates = [
  "video/webm;codecs=vp9",
  "video/webm;codecs=vp8",
  "video/webm",
];

recorder.start(500); // chunk a cada 500ms — não esperar até o fim
```

- `canvas.captureStream(6)` — FPS do stream alinhado ao loop
- `videoBitsPerSecond: 2_500_000`
- `getContext("2d", { alpha: false })` — fundo opaco, melhor compressão

---

## 7. Teste manual — como validar que está certo

### Screenshot

1. Abrir página com texto pequeno (ex.: tabela de candidatos)
2. Clicar "Capturar página"
3. Drawer fecha e reabre em ~1s
4. Preview legível — texto não borrado
5. Arquivo JPEG < 115KB (ver no Network ou tamanho do data URL)

### Gravação

1. Clicar "Gravar página" — drawer fecha, botão vermelho aparece
2. Navegar para outra rota — botão vermelho continua, contador sobe
3. Interagir com a página — possível com leve lag (normal)
4. Clicar "Parar" — botão vermelho **some na hora**
5. Em até ~2s drawer reabre com "Gravação anexada"
6. Reproduzir vídeo no preview — fluxo visível, não slideshow de slides estáticos

### Finalização

1. Gravar ~10s → parar → tempo até drawer reabrir < 2s
2. Gravar ~60s → parar → tempo até drawer reabrir < 4s
3. **Nunca** spinner fullscreen bloqueando a tela inteira

---

## 8. Resumo executivo para o desenvolvedor

> A gravação **é** frame a frame com html2canvas — isso é normal. O segredo é:
> 1. **6 FPS**, um frame por vez (`captureInFlight`)
> 2. **Singleton global** no layout
> 3. Ao parar: **matar sessão na UI primeiro**, converter blob depois
> 4. **Sem** html2canvas extra no stop
> 5. Screenshot: **scale 1.25× DPR**, JPEG comprimido, drawer fechado
>
> Se parece travado: FPS alto demais ou frames em paralelo.
> Se screenshot ruim: scale baixo ou PNG sem compressão.
> Se finalização lenta: spinner desnecessário + não limpar sessão antes + vídeo grande demais.

---

## 9. Arquivo de referência

Implementação completa e testada:

`admin-panel/lib/report-problem.ts` — funções `captureScreenshot`, `startPageRecording`, `compressCanvasToJpeg`, `endGlobalPageRecording`

`admin-panel/components/ReportProblemWidget.tsx` — `handleCapture`, `handleStartRecord`, `handleStopRecord`

---

*Fim do prompt. Aplique exatamente estes parâmetros e fluxos.*

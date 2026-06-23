# Guia de Desenvolvimento

## Pré-requisitos

- Python 3.12+
- Docker + Docker Compose (produção)
- Conta OpenAI com API key
- Chatwoot self-hosted com Agent Bot configurado
- Node.js 20+ (apenas para BMAD skills, opcional)

## Setup local

### 1. Variáveis de ambiente

```bash
cp .env.example .env
```

Editar `.env`:

```env
TENANT_ID=blackbeans
TENANTS_DIR=../tenants          # dev local (relativo a ai/)
CHATWOOT_BASE_URL=https://seu-chatwoot.com
CHATWOOT_BOT_TOKEN=token_do_agent_bot
CHATWOOT_ACCOUNT_ID=1
OPENAI_API_KEY=sk-...
```

### 2. Rodar com script de dev

```bash
chmod +x scripts/dev.sh
./scripts/dev.sh
```

Cria venv em `ai/.venv`, instala deps e sobe uvicorn na porta `8787`.

### 3. Rodar com Docker

```bash
docker compose up --build
```

Monta `tenants/` como read-only e persiste `data/` em volume.

## Verificar se está ok

```bash
curl http://localhost:8787/health
```

Esperado: `chatwoot_configured: true`, `openai_configured: true`, tenant listado.

## Conectar ao Chatwoot

1. Criar Agent Bot em **Configurações → Bots**
2. Webhook URL: `https://SEU-HARNESS/webhooks/chatwoot`
3. Ligar bot ao inbox (Telegram/WhatsApp)
4. Despublicar workflows n8n conflitantes

## Desenvolver um novo tenant

```bash
cp -r tenants/_template tenants/minha_empresa
# editar tenants/minha_empresa/tenant.json (id, name, routing)
# editar tenants/minha_empresa/prompts/agent_system.txt
```

No `.env`: `TENANT_ID=minha_empresa`

## Estrutura de um turno (debug mental)

1. Mensagem chega → `/webhooks/chatwoot`
2. `extract_inbound_message` filtra e parseia
3. `process_inbound` → `run_conversation_turn`
4. Grafo executa 6 nós
5. Resposta via Chatwoot API

Monitorar: `GET /ops/recent`

## Variáveis úteis

| Variável | Default | Descrição |
|---|---|---|
| `PORT` | 8787 | Porta HTTP |
| `TENANT_ID` | — | Força tenant específico |
| `TENANTS_DIR` | `../tenants` | Pasta de configs |
| `HARNESS_DATA_DIR` | `data` | SQLite + ops log |
| `CONTEXT_SUMMARIZE_AFTER` | 12 | Msgs antes de resumir |
| `CONTEXT_KEEP_RECENT` | 6 | Msgs recentes mantidas |
| `INGRESS_MAX_RETRIES` | 3 | Tentativas em falha |

## Testes

Não há suite de testes automatizados ainda. Teste manual:

1. Enviar mensagem no Telegram
2. Verificar resposta
3. Conferir `/ops/recent`
4. Testar conversa longa (resumo)
5. Testar pergunta fora do escopo (`should_reply: false`)

## BMAD Method

Skills instaladas em `.agents/skills/`. Comandos úteis no Cursor:

- `bmad-help` — próximo passo
- `bmad-create-prd` — planejar feature
- `bmad-quick-dev` — implementar rápido

Documentação gerada em `docs/index.md`.

---

_Gerado pelo workflow BMAD `document-project`_

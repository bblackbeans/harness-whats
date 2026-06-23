# Arquitetura — Langchain Automation Harness

## Visão de alto nível

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────────────────┐
│  Telegram   │────▶│   Chatwoot   │────▶│  Harness (FastAPI)          │
│  WhatsApp   │◀────│  Agent Bot   │◀────│  POST /webhooks/chatwoot    │
└─────────────┘     └──────────────┘     └─────────────────────────────┘
                                                    │
                    ┌───────────────────────────────┼───────────────────────┐
                    ▼                               ▼                       ▼
              Ingress layer                  LangGraph pipeline      Tenant config
         (dedupe, retry, async)         (6 nós sequenciais)      (tenants/<id>/)
                    │                               │
                    ▼                               ▼
              SQLite (memória)                  OpenAI API
```

## Camadas do sistema

### 1. Ingress (`ai/main.py`, `ai/ingress/`)

Responsável por receber e validar eventos externos.

- **Endpoint:** `POST /webhooks/chatwoot`
- **Validação:** assinatura HMAC (`CHATWOOT_WEBHOOK_SECRET`)
- **Filtro:** só `message_created` + `incoming`; ignora mensagens de agente/bot
- **Deduplicação:** `ingress/dedupe.py` por `delivery_id` (TTL 24h em memória)
- **Processamento:** `BackgroundTasks` — responde 202 imediatamente
- **Retry:** `ingress/processor.py` — 3 tentativas com sleep crescente

### 2. Integração Chatwoot (`ai/integrations/chatwoot.py`)

- Extrai: telefone/identifier, texto, `conversation_id`, `account_id`, `inbox_id`
- Envia respostas: `POST /api/v1/accounts/{id}/conversations/{id}/messages`
- Suporta templates WhatsApp via `template_params`

### 3. Resolução de tenant (`ai/tenants/`)

Ordem de prioridade (`registry.py`):

1. `TENANT_ID` no `.env` (forçado)
2. Único tenant carregado
3. Match por `chatwoot_inbox_ids`
4. Match por `chatwoot_account_ids`
5. Fallback `_default`

Cada tenant fornece: modelo, temperatura, prompts, limites de contexto.

### 4. Pipeline LangGraph (`ai/harness/graph.py`)

| Nó | Arquivo | Função |
|---|---|---|
| `load_memory` | `agent/nodes.py` | Carrega fatos do SQLite |
| `ingest` | `agent/nodes.py` | Cria `HumanMessage` da mensagem atual |
| `manage_context` | `agent/nodes.py` + `context/policy.py` | Resume + monta `agent_context` |
| `retrieve_knowledge` | `agent/nodes.py` + `knowledge/` | RAG: busca FAQ do tenant |
| `agent` | `agent/nodes.py` | LLM classifica intent e gera reply JSON |
| `persist_memory` | `agent/nodes.py` | Salva novos fatos |
| `send_reply` | `harness/outbound.py` | Envia via Chatwoot se `should_reply` |
| `execute_handoff` | `harness/handoff.py` | Transfere conversa para humano |

**Roteamento:** após `persist_memory` → `send_reply` (se resposta) → `execute_handoff` (se `handoff_to_human`).

### 5. RAG (`ai/knowledge/`)

- Indexa `tenants/<id>/knowledge/*.md` e `*.txt`
- Embeddings OpenAI em `data/rag/{tenant_id}.db`
- Reindex incremental por hash de arquivo
- Ver `POST /ops/reindex`

### 6. Handoff (`ai/handoff/`, `harness/handoff.py`)

- Detecta: keywords, `handoff_to_human` do LLM, ou pergunta sem FAQ
- `toggle_status: open` no Chatwoot
- Nota privada para agentes
- Ignora mensagens quando `conversation.status == open`
- Detalhes: [handoff.md](./handoff.md)

### 7. Agente IA (`agent/nodes.py`, `agent/llm.py`)

- Saída JSON: `intent`, `should_reply`, `reply`, `handoff_to_human`, `new_facts`
- Modelo configurável por tenant (`tenant.json` → `model.name`, `temperature`)
- Fallback sem API key: ecoa "Recebi sua mensagem: ..."

### 6. Contexto (`context/policy.py`)

Monta bloco textual com:
- Empresa (nome do tenant)
- Nome do contato
- Resumo da conversa
- Memória semântica
- Mensagens recentes
- Mensagem atual

Política de resumo: `summarize_after` (default 12), `keep_recent` (default 6).

### 7. Memória (`memory/semantic.py`)

SQLite em `{HARNESS_DATA_DIR}/semantic_memory.db`

Tabela `semantic_facts`: `(tenant_id, phone, fact, created_at)` — PK composta.

### 8. Operações (`ops/lifecycle.py`)

Estados: `received` → `processing` → `replied` | `handed_off` | `ignored` | `failed` | `duplicate`

Log append-only: `data/ops.jsonl` + buffer em memória para `/ops/recent`.

## Fluxo de uma mensagem (sequência)

```
1. Cliente envia no Telegram
2. Chatwoot recebe → webhook para harness
3. main.py valida, deduplica, cria InboundEvent
4. processor.py chama run_conversation_turn()
5. runner resolve tenant, monta HarnessState, invoca grafo
6. load_memory → ingest → manage_context → retrieve_knowledge → agent → persist_memory
7. Se should_reply: send_reply
8. Se handoff_to_human: execute_handoff (toggle open no Chatwoot)
9. lifecycle registra status final (replied / handed_off / ignored)
```

## Multi-tenant

```
tenants/
  _default/       → fallback
  _template/      → cópia para novos clientes (ignorado pelo loader)
  blackbeans/     → cliente ativo
    tenant.json
    prompts/*.txt
    knowledge/    → FAQ para RAG (faq.md, etc.)
```

**Modo A (1 deploy/cliente):** `TENANT_ID=blackbeans`  
**Modo B (multi-cliente):** `chatwoot_inbox_ids` em cada `tenant.json`

## Pendências futuras

| Feature | Status |
|---|---|
| Testes automatizados | Não existem |
| Dedupe persistente | Só em memória |
| Filas (Redis/SQS) | In-process |
| Atribuição automática a agente específico | Não implementado |

## Decisões de design

1. **Chatwoot como hub de canal** — um adapter para Telegram, WhatsApp, etc.
2. **LangGraph vs n8n** — pipeline fixo em código, versionável, testável
3. **JSON estruturado do agente** — permite `should_reply` e classificação de intent
4. **Prompts em arquivos** — editáveis sem redeploy de lógica (só restart/mount)
5. **SQLite** — simplicidade para memória; adequado para escala inicial

---

_Gerado pelo workflow BMAD `document-project`_

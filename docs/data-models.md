# Modelos de Dados — Harness

## Estado do grafo (`HarnessState`)

Definido em `ai/harness/state.py`. Passa entre todos os nós do LangGraph.

| Campo | Tipo | Descrição |
|---|---|---|
| `messages` | `list[BaseMessage]` | Histórico LangChain (com reducer `add_messages`) |
| `tenant_id` | `str` | ID do tenant ativo |
| `phone` | `str` | Telefone ou identifier do contato |
| `contact_name` | `str` | Nome no Chatwoot |
| `conversation_id` | `int` | ID da conversa Chatwoot |
| `account_id` | `int` | ID da conta Chatwoot |
| `inbox_id` | `int \| None` | ID do inbox (roteamento tenant) |
| `message_id` | `str` | ID da mensagem |
| `delivery_id` | `str` | ID de entrega do webhook |
| `inbound_text` | `str` | Texto recebido |
| `conversation_summary` | `str` | Resumo acumulado |
| `semantic_facts` | `list[str]` | Fatos carregados do banco |
| `new_semantic_facts` | `list[str]` | Fatos novos desta interação |
| `agent_context` | `str` | Bloco montado para o LLM |
| `retrieved_knowledge` | `list[str]` | Chunks RAG recuperados |
| `handoff_to_human` | `bool` | Se deve transferir para humano |
| `handoff_reason` | `str` | `keyword`, `agent`, `no_knowledge` |
| `intent` | `str` | Classificação da IA |
| `should_reply` | `bool` | Se deve enviar resposta |
| `outbound_text` | `str` | Texto a enviar |
| `lifecycle_status` | `str` | Status interno do turno |

## Evento de entrada (`InboundEvent`)

Dataclass em `ai/ingress/models.py` — criado no webhook antes do grafo.

## SQLite — `semantic_facts`

**Arquivo:** `{HARNESS_DATA_DIR}/semantic_memory.db`  
**Módulo:** `ai/memory/semantic.py`

```sql
CREATE TABLE semantic_facts (
    tenant_id TEXT NOT NULL,
    phone TEXT NOT NULL,
    fact TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, phone, fact)
);
```

- **Isolamento:** cada tenant tem memória separada
- **Chave do usuário:** `phone` (telefone ou identifier Telegram)
- **Operações:** `recall(tenant_id, phone)`, `store(tenant_id, phone, facts)`
- **Migração:** schema antigo (só `phone`) migra para `tenant_id='default'`

## Log operacional — `ops.jsonl`

**Arquivo:** `{HARNESS_DATA_DIR}/ops.jsonl`  
**Módulo:** `ai/ops/lifecycle.py`

Cada linha é um JSON (`OpsEvent`):
```json
{
  "ts": "ISO8601",
  "delivery_id": "",
  "message_id": "",
  "conversation_id": 0,
  "status": "replied",
  "detail": ""
}
```

## Configuração de tenant (`tenant.json`)

```json
{
  "id": "blackbeans",
  "name": "BlackBeans",
  "language": "pt-BR",
  "model": {
    "name": "gpt-4o-mini",
    "temperature": 0.3,
    "api_key_env": "OPENAI_API_KEY"
  },
  "routing": {
    "chatwoot_account_ids": [],
    "chatwoot_inbox_ids": []
  },
  "context": {
    "summarize_after": 12,
    "keep_recent": 6
  },
  "rag": {
    "enabled": true,
    "top_k": 5
  },
  "handoff": {
    "enabled": true,
    "message": "Vou encaminhar para um atendente...",
    "keywords": ["atendente", "humano"],
    "on_no_knowledge": true,
    "private_note_enabled": true
  }
}
```

## SQLite — RAG (`knowledge_chunks`)

**Arquivo:** `{HARNESS_DATA_DIR}/rag/{tenant_id}.db`  
**Módulo:** `ai/knowledge/store.py`

Chunks com embeddings por tenant, indexados a partir de `tenants/<id>/knowledge/`.

## Checkpoint LangGraph

`MemorySaver` em memória — estado do grafo por `thread_id`:
```
{tenant_id}:cw:{conversation_id}
```

**Nota:** checkpoint não persiste entre restarts do processo.

## Dedupe (memória volátil)

`ingress/dedupe.py` — dict `{delivery_id: timestamp}` com TTL 24h. Não persiste em disco.

---

_Gerado pelo workflow BMAD `document-project`_

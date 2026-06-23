# Inventário de Componentes

## Módulos principais

### `main.py` — Aplicação FastAPI
- Rotas HTTP públicas
- Orquestra background tasks
- Endpoint de dispatch proativo

### `ingress/` — Camada de entrada
| Componente | Responsabilidade |
|---|---|
| `dedupe.py` | Evita reprocessar mesmo webhook |
| `processor.py` | Retry, lifecycle, chama runner |
| `models.py` | `InboundEvent` tipado |

### `harness/` — Motor de conversa
| Componente | Responsabilidade |
|---|---|
| `graph.py` | StateGraph LangGraph compilado |
| `runner.py` | Inicializa estado + invoca grafo |
| `state.py` | Contrato de estado compartilhado |
| `outbound.py` | Envio assíncrono Chatwoot |
| `handoff.py` | Nó `execute_handoff` — transferência humana |

### `knowledge/` — RAG
| Componente | Responsabilidade |
|---|---|
| `indexer.py` | Indexa `tenants/*/knowledge/` |
| `retrieve.py` | Busca semântica top-K |
| `store.py` | SQLite de chunks + embeddings |

### `handoff/` — Regras de transferência
| Componente | Responsabilidade |
|---|---|
| `policy.py` | Keywords, no_knowledge, merge com LLM |

### `agent/` — Inteligência
| Componente | Responsabilidade |
|---|---|
| `nodes.py` | 5 nós do grafo + `generate_dispatch_message` |
| `llm.py` | `get_llm(tenant)` — OpenAI configurável |

### `context/policy.py` — Gestão de contexto
- `should_summarize()` — limiar de mensagens
- `summarize_messages()` — LLM resume histórico
- `trim_messages()` — mantém N recentes
- `build_agent_context()` — monta prompt do usuário

### `memory/semantic.py` — Memória de longo prazo
- SQLite por `(tenant_id, phone, fact)`
- Migração automática de schema legado

### `integrations/chatwoot.py` — Adapter Chatwoot
- `extract_inbound_message()` — parse webhook
- `send_message()` / `send_template()` — outbound
- `verify_webhook_signature()` — HMAC SHA256

### `tenants/` — Sistema multi-cliente
| Componente | Responsabilidade |
|---|---|
| `loader.py` | Lê `tenants/*/tenant.json` e `.txt` |
| `registry.py` | `resolve_tenant(event)` |
| `config.py` | Dataclasses de configuração |

### `ops/lifecycle.py` — Observabilidade
- `record_event()` — append JSONL + deque
- `recent_events()` — API `/ops/recent`

## Nós do grafo LangGraph

```
START
  → load_memory
  → ingest
  → manage_context
  → retrieve_knowledge   (RAG)
  → agent
  → persist_memory
  → [condicional] send_reply
  → [condicional] execute_handoff
  → END
```

## Configuração por tenant (arquivos)

| Arquivo prompt | Usado em |
|---|---|
| `agent_system.txt` | Nó `agent` — resposta ao cliente |
| `facts_system.txt` | Nó `persist_memory` — extrair fatos |
| `summarize_system.txt` | Nó `manage_context` — resumir conversa |
| `dispatch_system.txt` | `POST /dispatch` — mensagens proativas |
| `knowledge/faq.md` | Fonte RAG — indexada em SQLite |

## Dependências externas

| Serviço | Uso |
|---|---|
| Chatwoot | Canal Telegram/WhatsApp + webhook + handoff |
| OpenAI API | LLM + embeddings RAG |
| SQLite | Memória + chunks RAG |

## Componentes planejados (não implementados)

- Fila de mensagens (Redis/RQ)
- Testes unitários/integração

---

_Gerado pelo workflow BMAD `document-project`_

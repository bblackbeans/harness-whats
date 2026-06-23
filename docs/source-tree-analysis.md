# Análise da Árvore de Diretórios

```
lagnchain-automation/
├── ai/                          # Motor do harness (código Python)
│   ├── main.py                  # FastAPI app — webhooks, health, dispatch
│   ├── requirements.txt         # Dependências Python
│   ├── Dockerfile               # Imagem de produção
│   │
│   ├── agent/                   # Nós do agente IA
│   │   ├── llm.py               # Factory OpenAI por tenant
│   │   └── nodes.py             # load_memory, ingest, context, agent, persist
│   │
│   ├── harness/                 # Orquestração LangGraph
│   │   ├── graph.py             # Definição do grafo LangGraph
│   │   ├── runner.py            # run_conversation_turn()
│   │   ├── state.py             # HarnessState (TypedDict)
│   │   ├── outbound.py          # send_reply via Chatwoot
│   │   └── handoff.py           # execute_handoff
│   │
│   ├── knowledge/                 # RAG — indexação e busca
│   │   ├── indexer.py
│   │   ├── retrieve.py
│   │   └── store.py
│   │
│   ├── handoff/
│   │   └── policy.py            # Regras de transferência humana
│   │
│   ├── ingress/                 # Entrada de mensagens
│   │   ├── models.py            # InboundEvent
│   │   ├── processor.py         # Retry + lifecycle
│   │   └── dedupe.py            # Anti-duplicata webhook
│   │
│   ├── integrations/
│   │   └── chatwoot.py          # Webhook parse + API envio
│   │
│   ├── context/
│   │   └── policy.py            # Resumo + build_agent_context
│   │
│   ├── memory/
│   │   └── semantic.py          # SQLite fatos por tenant/usuário
│   │
│   ├── ops/
│   │   └── lifecycle.py         # Log de eventos (ops.jsonl)
│   │
│   └── tenants/                 # Loader multi-tenant (código)
│       ├── config.py            # TenantConfig dataclass
│       ├── loader.py            # Carrega tenant.json + prompts
│       └── registry.py          # resolve_tenant()
│
├── tenants/                     # Config por cliente (dados, não código)
│   ├── _default/                # Fallback genérico
│   ├── _template/               # Modelo para copiar (ignorado pelo loader)
│   └── blackbeans/              # Cliente BlackBeans
│       ├── tenant.json
│       ├── prompts/             # agent, facts, summarize, dispatch
│       └── knowledge/           # FAQ indexada no RAG (faq.md)
│
├── docs/                        # Documentação do projeto (BMAD)
├── scripts/
│   └── dev.sh                   # Dev local com venv
├── docker-compose.yml           # Deploy container
├── .env.example                 # Variáveis de ambiente
│
├── _bmad/                       # BMAD Method — config e workflows
├── .agents/skills/              # Skills BMAD para Cursor
└── data/                        # Volume Docker (gitignored)
    ├── semantic_memory.db
    ├── rag/                     # {tenant_id}.db — chunks RAG
    └── ops.jsonl
```

## Pastas críticas

| Pasta | Propósito | Mexer para... |
|---|---|---|
| `ai/agent/` | Lógica IA | Mudar comportamento do grafo |
| `ai/harness/` | Pipeline | Alterar ordem/etapas |
| `tenants/<id>/prompts/` | Personalidade | Novo cliente / escopo |
| `tenants/<id>/knowledge/` | Base oficial | FAQ / RAG por cliente |
| `ai/integrations/` | Chatwoot | Novo canal sem Chatwoot |

## Pontos de entrada

| Entrada | Arquivo |
|---|---|
| HTTP server | `ai/main.py` → uvicorn |
| Webhook inbound | `POST /webhooks/chatwoot` |
| Turno de conversa | `harness/runner.py` → `run_conversation_turn()` |
| Grafo | `harness/graph.py` → `get_graph()` |

## Artefatos gerados em runtime

| Arquivo | Local |
|---|---|
| Memória semântica | `data/semantic_memory.db` |
| Log operacional | `data/ops.jsonl` |
| Checkpoint LangGraph | Memória do processo (não persiste) |

---

_Gerado pelo workflow BMAD `document-project`_

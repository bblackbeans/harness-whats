# Langchain Automation Harness — Índice de Documentação

**Tipo:** Monólito backend  
**Linguagem:** Python 3.12  
**Arquitetura:** Pipeline LangGraph + FastAPI + Chatwoot  
**Última atualização:** 2026-06-23

## Visão geral

Harness de atendimento por mensagem (Telegram, WhatsApp via Chatwoot) com IA, memória por usuário, **RAG por tenant** e **handoff para humano**. Cada empresa/cliente personaliza prompts, FAQ e regras em `tenants/<id>/` sem alterar o motor em `ai/`.

## Referência rápida

| Item | Valor |
|---|---|
| Stack | FastAPI, LangGraph, LangChain, OpenAI, Chatwoot |
| Entry point | `ai/main.py` (uvicorn :8787) |
| Webhook | `POST /webhooks/chatwoot` |
| Tenant ativo | `TENANT_ID` no `.env` ou roteamento por `inbox_id` |
| Memória | SQLite `data/semantic_memory.db` |
| RAG | SQLite `data/rag/{tenant_id}.db` |
| Deploy | `docker compose up` |

## Documentação

### Core

- [Visão Geral do Projeto](./project-overview.md)
- [Arquitetura](./architecture.md)
- [Árvore de Diretórios](./source-tree-analysis.md)
- [Inventário de Componentes](./component-inventory.md)

### Features

- [Handoff para humano](./handoff.md) — o que é e como funciona
- [Contratos de API](./api-contracts.md)
- [Modelos de Dados](./data-models.md)

### Operação

- [Guia de Desenvolvimento](./development-guide.md)
- [Guia de Deploy](./deployment-guide.md)

## Como começar

```bash
cp .env.example .env
docker compose up --build
curl http://localhost:8787/health
curl -X POST "http://localhost:8787/ops/reindex?tenant_id=blackbeans"
```

## Roadmap

- [x] Canal Chatwoot (Telegram/WhatsApp)
- [x] Multi-tenant (`tenants/`)
- [x] RAG (`tenants/*/knowledge/`)
- [x] Handoff humano no Chatwoot
- [ ] Testes automatizados
- [ ] Dedupe persistente

---

_Gerado e atualizado via BMAD `document-project`_

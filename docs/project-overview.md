# Langchain Automation Harness — Visão Geral do Projeto

**Data:** 2026-06-23  
**Tipo:** Backend / serviço de IA  
**Arquitetura:** Pipeline orientado a eventos com grafo LangGraph

## Resumo executivo

Este projeto é um **harness de atendimento por mensagem** que conecta canais do **Chatwoot** (Telegram, WhatsApp e outros) a um motor de IA baseado em **LangGraph + OpenAI**. Ele recebe mensagens via webhook, processa em etapas (memória, contexto, agente, persistência) e devolve respostas automaticamente.

O diferencial atual é a arquitetura **multi-tenant**: o motor é genérico e cada cliente/empresa configura comportamento via pasta `tenants/<id>/` (prompts, modelo, roteamento) sem reescrever o código.

**Status:** canal Telegram + Chatwoot funcionando em produção (BlackBeans), com **RAG** e **handoff humano** implementados. Próximas evoluções: WhatsApp, testes automatizados.

## Classificação do projeto

| Atributo | Valor |
|---|---|
| Tipo de repositório | Monólito |
| Linguagem principal | Python 3.12 |
| Framework HTTP | FastAPI + Uvicorn |
| Orquestração IA | LangGraph |
| Integração canal | Chatwoot (agent bot) |
| Persistência | SQLite (memória semântica + RAG + ops log) |
| Deploy | Docker Compose |

## Stack tecnológica

| Categoria | Tecnologia | Versão / nota |
|---|---|---|
| Runtime | Python | 3.12 (Dockerfile) |
| API | FastAPI | ≥0.115 |
| Servidor | Uvicorn | ≥0.32 |
| IA | LangChain + LangGraph | ≥0.3 / ≥0.2 |
| LLM | OpenAI (gpt-4o-mini) | via API |
| HTTP cliente | httpx | Chatwoot API |
| Config | python-dotenv, JSON | `.env` + `tenant.json` |
| Container | Docker | python:3.12-slim |

## Funcionalidades principais

1. **Webhook Chatwoot** — recebe `message_created` incoming
2. **Deduplicação** — evita processar o mesmo `delivery_id` duas vezes
3. **Retry** — até 3 tentativas com backoff exponencial
4. **Grafo LangGraph** — memória → ingest → contexto → RAG → agente → persist → envio → handoff
5. **Memória semântica** — fatos duráveis por tenant + usuário (SQLite)
6. **RAG** — busca em `tenants/*/knowledge/` antes do agente responder
7. **Handoff humano** — transfere conversa para agentes no Chatwoot (`status: open`)
8. **Resumo de conversa** — quando passa de 12 mensagens, resume e mantém as 6 recentes
9. **Multi-tenant** — `TENANT_ID` ou roteamento por `inbox_id` do Chatwoot
10. **Disparos proativos** — endpoint `/dispatch` (conversa ou template WhatsApp)
11. **Observabilidade** — `/health`, `/ops/recent`, `/ops/reindex`, log JSONL

## Destaques de arquitetura

- **Separação motor vs conteúdo:** código em `ai/` é estável; personalização em `tenants/`
- **Estado tipado:** `HarnessState` passa entre nós do grafo
- **Thread por conversa:** `thread_id = {tenant_id}:cw:{conversation_id}`
- **Resposta condicional:** IA pode retornar `should_reply: false` (fora do escopo)

## Como começar

```bash
cp .env.example .env
# editar CHATWOOT_* e OPENAI_API_KEY

docker compose up --build
# ou: ./scripts/dev.sh
```

Ver [development-guide.md](./development-guide.md) para detalhes.

## Mapa de documentação

- [index.md](./index.md) — índice mestre
- [architecture.md](./architecture.md) — arquitetura detalhada
- [api-contracts.md](./api-contracts.md) — endpoints HTTP
- [data-models.md](./data-models.md) — SQLite e estado
- [handoff.md](./handoff.md) — transferência para humano

---

_Gerado pelo workflow BMAD `document-project`_

# Epics e Stories — RAG por Tenant

**PRD:** `_bmad-output/planning-artifacts/prds/prd-harness-rag-2026-06-23/prd.md`  
**Data:** 2026-06-23

---

## Epic 1: Indexação da knowledge base (FR-1, FR-2, FR-3)

Indexar arquivos em `tenants/<id>/knowledge/` com chunks e embeddings persistidos por tenant.

### Story 1.1 — Descoberta de arquivos
**Como** operador, **quero** que o harness leia `.md` e `.txt` em `knowledge/` recursivamente, **para** alimentar a base sem config extra.

**Critérios de aceite:**
- [ ] `faq.md` em subpastas é indexado
- [ ] README placeholder vazio é ignorado
- [ ] Arquivos não suportados são ignorados sem crash

**Refs:** FR-1

### Story 1.2 — Chunking e embeddings
**Como** sistema, **quero** dividir documentos e gerar embeddings OpenAI, **para** permitir busca semântica.

**Critérios de aceite:**
- [ ] Chunks com tamanho configurável (~500 chars)
- [ ] Cada chunk guarda `tenant_id`, `source_path`, `chunk_index`, `text`, `embedding`
- [ ] Falha de embedding loga erro e degrada (sem derrubar webhook)

**Refs:** FR-2

### Story 1.3 — Persistência e reindex incremental
**Como** sistema, **quero** persistir índice em SQLite e reindexar só arquivos alterados, **para** sobreviver a restart sem custo desnecessário.

**Critérios de aceite:**
- [ ] Índice em `data/rag/{tenant_id}.db`
- [ ] Mudança de hash do arquivo reindexa só esse arquivo
- [ ] Arquivo removido remove chunks do índice

**Refs:** FR-3

---

## Epic 2: Recuperação na conversa (FR-4, FR-5)

Buscar trechos relevantes e injetar no contexto antes do agente.

### Story 2.1 — Busca semântica top-K
**Como** agente, **quero** recuperar até K chunks por similaridade à mensagem atual, **para** fundamentar a resposta.

**Critérios de aceite:**
- [ ] Busca isolada por `tenant_id`
- [ ] Top-K default 5
- [ ] Índice vazio retorna lista vazia

**Refs:** FR-4

### Story 2.2 — Nó `retrieve_knowledge` no grafo
**Como** arquiteto, **quero** um nó entre `manage_context` e `agent`, **para** separar recuperação de geração.

**Critérios de aceite:**
- [ ] Grafo: `manage_context → retrieve_knowledge → agent`
- [ ] `agent_context` ganha seção "Material oficial recuperado"
- [ ] Chunks duplicados não repetidos na mesma requisição

**Refs:** FR-5

---

## Epic 3: Comportamento do agente (FR-6, FR-7)

Prompts e isolamento multi-tenant.

### Story 3.1 — Prompts com regra de evidência
**Como** cliente, **quero** que o bot só cite fatos do material oficial, **para** evitar alucinação.

**Critérios de aceite:**
- [ ] `_default`, `_template` e `blackbeans` `agent_system.txt` atualizados
- [ ] Instrução explícita: não inventar preço/prazo

**Refs:** FR-6

### Story 3.2 — Isolamento por tenant
**Como** operador multi-cliente, **quero** índices separados, **para** que tenants não vazem conhecimento entre si.

**Critérios de aceite:**
- [ ] DB ou tabelas keyed por `tenant_id`
- [ ] `resolve_tenant()` define qual índice usar

**Refs:** FR-7

---

## Epic 4: Operação (FR-8)

Observabilidade e reindex manual.

### Story 4.1 — Health com stats RAG
**Como** operador, **quero** ver chunks indexados por tenant no `/health`, **para** validar deploy.

**Critérios de aceite:**
- [ ] `rag.enabled` e `rag.chunks_by_tenant` no health
- [ ] Sem expor conteúdo dos chunks

**Refs:** FR-8

### Story 4.2 — FAQ BlackBeans inicial
**Como** usuário BlackBeans, **quero** FAQ real em `knowledge/faq.md`, **para** testar respostas fundamentadas.

**Critérios de aceite:**
- [ ] `tenants/blackbeans/knowledge/faq.md` com serviços e políticas básicas

**Refs:** MVP scope

---

## Ordem de implementação

1. Story 1.1 → 1.2 → 1.3 (módulo `ai/knowledge/`)
2. Story 2.1 → 2.2 (grafo)
3. Story 3.1 → 3.2 (prompts + tenant config)
4. Story 4.1 → 4.2 (health + FAQ)

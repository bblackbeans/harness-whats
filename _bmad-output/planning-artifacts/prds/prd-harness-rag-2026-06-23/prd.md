---
title: RAG por Tenant no Harness
status: final
created: 2026-06-23
updated: 2026-06-23
---

# PRD: Base de Conhecimento (RAG) por Tenant no Harness

*Produto: Langchain Automation Harness — extensão multi-cliente*

## 0. Documento

Este PRD define a **Fase 3** do harness: respostas fundamentadas em material oficial de cada cliente, lida a partir de `tenants/<id>/knowledge/`. Destina-se a PM, desenvolvimento e workflows downstream (`bmad-architecture`, `bmad-create-epics-and-stories`).

**Inputs considerados:** `docs/index.md`, `docs/architecture.md`, conversas de produto, tenant BlackBeans em produção (Telegram + Chatwoot).

**Fora deste PRD:** handoff humano no Chatwoot (Fase 4), painel web de edição de conhecimento, fine-tuning de modelo.

## 1. Visão

Hoje o bot responde com prompt + memória de conversa + conhecimento geral do LLM — o que causa **alucinação** sobre preços, serviços e políticas da empresa. A BlackBeans já funciona no Telegram, mas respostas sobre a empresa podem ser imprecisas.

Queremos que, antes de cada resposta, o harness **busque trechos relevantes** na base oficial do tenant e injete no contexto do agente, com regra explícita: **só responder com base no material recuperado + contexto da conversa**. Se não houver evidência, o bot deve admitir limitação (e, no futuro, acionar handoff humano).

Isso transforma o harness de “chatbot genérico configurável” em **atendimento com conhecimento auditável**, replicável por cliente apenas adicionando arquivos em `knowledge/` — alinhado ao modelo multi-tenant já existente.

## 2. Usuário-alvo

### 2.1 Jobs To Be Done

- **Operador da agência (nós):** replicar bot para novo cliente sem reescrever código — só pasta `tenants/` + arquivos de FAQ.
- **Cliente final (empresa):** ter respostas corretas sobre produto, serviços e políticas no WhatsApp/Telegram.
- **Usuário final (consumidor):** obter informação confiável sem perceber que fala com IA genérica.

### 2.2 Não-usuários (v1)

- Equipe interna editando conhecimento via UI (v1 é arquivo em disco).
- Clientes que precisam de RAG em PDFs escaneados ou vídeos.

### 2.3 Jornadas-chave

**UJ-1. Maria pergunta sobre serviços da BlackBeans no Telegram**

Maria abre o bot `@BBteste09_bot` e pergunta: “Quais serviços vocês oferecem?”. O harness resolve o tenant `blackbeans`, busca em `tenants/blackbeans/knowledge/` trechos sobre serviços, monta o contexto com citações internas e o agente responde em português, curto, sem markdown. Se o FAQ não mencionar um serviço, o bot diz que não tem essa informação e sugere contato humano.

**UJ-2. Kauê adiciona FAQ de um novo cliente**

Kauê copia `tenants/_template/` para `tenants/empresa_x/`, coloca `faq.md` em `knowledge/`, faz deploy com `TENANT_ID=empresa_x`. Na primeira mensagem após deploy, o índice é construído automaticamente e perguntas sobre a empresa passam a usar o novo material.

**UJ-3. Pergunta fora da base**

Usuário pergunta “qual o preço do plano enterprise?”. O FAQ não contém preços. O agente retorna `should_reply: true` com mensagem honesta (“não tenho essa informação; um consultor pode ajudar”) e **não inventa valor**. Realiza política de escopo do prompt.

## 3. Glossário

- **Tenant** — cliente/empresa com pasta em `tenants/<id>/` (config + prompts + knowledge).
- **Knowledge base** — arquivos em `tenants/<id>/knowledge/` (markdown/texto na v1).
- **Chunk** — trecho indexado de um arquivo da knowledge base.
- **RAG** — Retrieval-Augmented Generation: busca + injeção de contexto antes do LLM.
- **Harness** — serviço FastAPI + LangGraph que processa mensagens do Chatwoot.
- **Agent context** — bloco textual montado em `manage_context` para o nó `agent`.
- **Material oficial** — conteúdo em `knowledge/`; única fonte factual permitida além da conversa atual.

## 4. Features

### 4.1 Indexação da knowledge base por tenant

**Descrição:** Ao processar mensagens (ou na inicialização do tenant), o sistema indexa arquivos em `tenants/<id>/knowledge/`, gera embeddings e persiste índice local. Reindexação quando arquivos mudam (hash/mtime). Realiza UJ-2.

**Requisitos funcionais:**

#### FR-1: Descoberta de arquivos de conhecimento

O harness pode listar e ler arquivos suportados (`.md`, `.txt`) em `tenants/<id>/knowledge/`, ignorando README placeholder vazio.

**Consequências (testáveis):**
- Arquivo `faq.md` em `knowledge/` é incluído no índice.
- Subpastas são percorridas recursivamente.
- Arquivos binários são ignorados sem erro fatal.

#### FR-2: Chunking e embedding

O harness divide documentos em chunks com tamanho configurável e gera embeddings via API OpenAI (modelo configurável por tenant ou global).

**Consequências:**
- Cada chunk armazena: `tenant_id`, `source_path`, `chunk_index`, `text`, `embedding`.
- Falha de API de embedding registra erro em log e não derruba o webhook (degrada para modo sem RAG).

#### FR-3: Persistência do índice

O índice persiste em disco sob `HARNESS_DATA_DIR` (ex.: `data/rag/<tenant_id>/`), separado por tenant.

**Consequências:**
- Restart do container não exige reindex completo se índice válido.
- Mudança de mtime/hash do arquivo dispara reindex incremental desse arquivo.

**Notas:** `[ASSUMPTION: embeddings text-embedding-3-small como default]`

---

### 4.2 Recuperação de contexto na conversa

**Descrição:** Antes do nó `agent`, buscar top-K chunks relevantes à `inbound_text` e anexar ao `agent_context`. Realiza UJ-1, UJ-3.

**Requisitos funcionais:**

#### FR-4: Busca semântica por mensagem

Dado `tenant_id` e texto da mensagem atual, o harness retorna até K chunks (default 5) ordenados por similaridade.

**Consequências:**
- Busca usa apenas índice do tenant ativo.
- Latência adicional p95 < 500ms em índice com até 500 chunks (alvo MVP).
- Se índice vazio, `agent_context` indica “nenhum material oficial indexado”.

#### FR-5: Injeção no contexto do agente

`build_agent_context` inclui seção **Material oficial recuperado** com trechos e caminho do arquivo fonte.

**Consequências:**
- Formato legível para o LLM (lista numerada com `fonte: knowledge/faq.md`).
- Não duplica chunks idênticos na mesma requisição.

---

### 4.3 Comportamento do agente com evidência

**Descrição:** Atualizar prompt padrão e guia do tenant para obrigar uso do material recuperado. Realiza UJ-1, UJ-3.

**Requisitos funcionais:**

#### FR-6: Regra de resposta fundamentada

O `agent_system.txt` (default e template) instrui: responder fatos empresariais **somente** com base em “Material oficial recuperado”; se insuficiente, não inventar.

**Consequências:**
- Pergunta sobre preço sem evidência → resposta de limitação, não valor fictício.
- `should_reply` permanece true para mensagem educada de limitação (salvo escopo do prompt diga false).

#### FR-7: Compatibilidade multi-tenant

RAG respeita `resolve_tenant()` existente; índices isolados por `tenant_id`.

**Consequências:**
- Tenant A não recupera chunks de tenant B.
- `TENANT_ID` forçado e roteamento por `inbox_id` continuam funcionando.

---

### 4.4 Operação e observabilidade

**Descrição:** Visibilidade mínima para debug em produção.

**Requisitos funcionais:**

#### FR-8: Health e ops

`/health` indica se RAG está habilitado e quantos chunks indexados por tenant (opcional, sem expor conteúdo).

**Consequências:**
- Log estruturado em indexação: tenant, arquivos processados, chunks criados.
- Falha de RAG não impede resposta (fallback: prompt sem material).

**NFRs da feature:**
- **Confiabilidade:** falha de RAG ≠ falha de webhook.
- **Privacidade:** embeddings e chunks não vazam entre tenants.
- **Manutenção:** atualizar FAQ = editar arquivo + reindex automático.

## 5. Não-objetivos (explícitos)

- Handoff automático para humano no Chatwoot (PRD separado).
- UI administrativa para editar knowledge.
- Suporte a PDF, DOCX, scraping de site na v1.
- Reranking com modelo separado na v1.
- Vector DB externo (Pinecone, Weaviate) na v1 — SQLite ou arquivo local basta.

## 6. Escopo MVP

### 6.1 No escopo

- Indexação `.md` / `.txt` em `tenants/*/knowledge/`
- Embeddings OpenAI + busca top-K
- Injeção em `agent_context` entre `manage_context` e `agent`
- Persistência de índice em `data/rag/`
- Atualização de prompts default + `_template` + `blackbeans`
- FAQ inicial BlackBeans em `knowledge/faq.md`

### 6.2 Fora do MVP

| Item | Motivo |
|---|---|
| Handoff humano | Feature separada; RAG entrega valor antes |
| PDF/DOCX | Complexidade de parsing |
| Painel web | Arquivos bastam para agência |
| API de upload | Deploy via Git/volume montado |
| Reranker | Otimização v2 se qualidade insuficiente |

## 7. Métricas de sucesso

**Primárias**
- **SM-1:** ≥ 90% das perguntas com resposta em FAQ contêm informação presente no material recuperado (amostra manual 20 perguntas). Valida FR-4, FR-5, FR-6.
- **SM-2:** 0 respostas com preço/prazo inventado em teste de 10 perguntas fora do FAQ. Valida FR-6.

**Secundárias**
- **SM-3:** Tempo extra p95 < 1s por mensagem com RAG ativo. Valida FR-4.

**Contra-métricas**
- **SM-C1:** Não maximizar taxa de resposta a qualquer custo — `should_reply: false` ou admissão de ignorância é sucesso quando sem evidência. Contrabalança SM-1.

## 8. Perguntas abertas

1. K ideal de chunks (3 vs 5 vs 8) — validar com BlackBeans após MVP.
2. Reindex: só no startup ou também watch em dev?
3. Modelo de embedding: global ou por tenant em `tenant.json`?

## 9. Índice de premissas

- `[ASSUMPTION]` Embeddings via `text-embedding-3-small` e mesma `OPENAI_API_KEY` do agente.
- `[ASSUMPTION]` Apenas markdown e texto plano na v1.
- `[ASSUMPTION]` Índice local em SQLite/arquivo é suficiente para dezenas de clientes com FAQ pequeno.
- `[ASSUMPTION]` Handoff humano será PRD seguinte, não bloqueante.

---

_PRD gerado via BMAD `bmad-prd` (intent: create). Fast path com base em `docs/` e contexto brownfield._

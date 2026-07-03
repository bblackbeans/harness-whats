---
title: Plataforma SaaS de Agentes de IA
status: final
created: 2026-07-01
updated: 2026-07-01
---

# PRD: Plataforma SaaS de Agentes de IA

**Produto:** Langchain Automation Harness — Evolução SaaS  
**Depende de:** Harness multi-tenant (pastas), RAG, Handoff Chatwoot

## 0. Document Purpose

PRD para stakeholders, PM e workflows downstream (UX, arquitetura, épicos). Vocabulário ancorado no Glossário. Features com FRs numerados globalmente.

## 1. Visão

Transformar o harness de atendimento com IA (Chatwoot + LangGraph) em uma **plataforma SaaS multi-tenant** operada em infraestrutura única. Cada empresa (tenant) possui agente, contexto, FAQ, modelos de IA e métricas isolados logicamente, sem instalações separadas de Chatwoot ou Harness.

O administrador da plataforma ativa novos clientes em minutos via painel web — sem criar pastas, reiniciar serviços ou alterar código. O painel admin (Next.js + Untitled UI) centraliza gestão de tenants, configuração de LLMs e base de conhecimento.

## 2. Target User

### 2.1 Jobs To Be Done

- **Admin da plataforma:** criar e configurar clientes rapidamente; controlar quais modelos cada cliente usa; monitorar custos e uso.
- **Operador comercial:** vender assinaturas com planos parametrizados (futuro).
- **Cliente final (tenant):** receber atendimento IA personalizado via WhatsApp/Telegram sem saber da infraestrutura compartilhada.

### 2.2 Non-Users (v1)

- Clientes finais editando configurações (painel self-service → Epic 8, pós-MVP).
- Operadores de campanhas WhatsApp em massa (disparos → fora de escopo).

### 2.3 Key User Journeys

**UJ-1. Ricardo ativa um novo cliente em 10 minutos.**

Ricardo, admin da plataforma, faz login no painel admin. Clica "Novo tenant", preenche nome da empresa, IDs de inbox Chatwoot, escolhe GPT-4o-mini na lista de modelos permitidos, cola o prompt do agente e salva. O tenant fica ativo. Na primeira mensagem WhatsApp do cliente, o harness resolve o tenant pelo inbox_id e responde com a config do banco.

**UJ-2. Ricardo troca o modelo de um cliente.**

Ricardo abre o tenant BlackBeans, altera o modelo de `gpt-4o-mini` para `gpt-4o` na combobox, salva. Próxima conversa usa o novo modelo sem deploy.

**UJ-3. Ricardo adiciona FAQ sem SSH.**

Ricardo faz upload de `faq.md` no painel, clica "Reindexar". O RAG do tenant é atualizado e o bot passa a usar o novo conteúdo.

## 3. Glossário

- **Tenant** — Cliente lógico da plataforma; unidade de isolamento de config, prompts, conhecimento e métricas.
- **Harness** — Motor FastAPI + LangGraph que processa mensagens e orquestra o agente.
- **Admin da plataforma** — Usuário com role `super_admin`; gerencia todos os tenants.
- **LLM Provider** — Provedor de IA (OpenAI, Anthropic, etc.) com API key armazenada na infraestrutura.
- **Modelo permitido** — Associação entre tenant e modelo LLM que o admin autorizou.
- **Usage Event** — Registro de chamada LLM com tokens e custo estimado.

## 4. Features

### 4.1 Gestão dinâmica de tenants

**Description:** Substitui pastas `tenants/<id>/` por persistência em PostgreSQL. O harness carrega config em runtime. Realiza UJ-1.

#### FR-1: CRUD de tenants via API admin
Admin pode criar, ler, atualizar, ativar/desativar e remover tenants.

**Consequences:**
- Tenant criado persiste em DB com defaults (prompts, handoff, rag).
- Tenant desativado: harness não resolve para novas conversas.
- Remoção é soft-delete ou hard com confirmação.

#### FR-2: Resolução automática de tenant no webhook
Harness identifica tenant por `chatwoot_inbox_ids` ou `chatwoot_account_ids` sem `TENANT_ID` fixo no `.env`.

**Consequences:**
- Mensagem em inbox mapeado carrega config do DB.
- Inbox não mapeado usa fallback `_default` ou erro logado.

#### FR-3: Hot-reload de configuração
Alterações no painel refletem na próxima mensagem sem restart.

**Consequences:**
- Cache invalidado após PUT/POST admin.
- Latência adicional < 50ms na primeira mensagem pós-update.

### 4.2 Painel administrativo

**Description:** Interface Next.js com Untitled UI para operação da plataforma. Realiza UJ-1, UJ-2, UJ-3.

#### FR-4: Autenticação admin
Login com email/senha; JWT com refresh token; sessão no painel.

#### FR-5: Dashboard de tenants
Lista tenants com status (ativo/inativo), modelo atual, consumo resumido.

#### FR-6: Wizard de criação/edição de tenant
Formulário multi-step: dados → routing Chatwoot → modelo → prompts.

#### FR-7: Editor de prompts
Tabs para `agent_system`, `facts_system`, `summarize_system`.

### 4.3 Gestão de LLMs

**Description:** API keys centralizadas; modelos atribuídos por tenant. Realiza UJ-2.

#### FR-8: Cadastro de provedores LLM
Admin cadastra provedor (nome, tipo, API key criptografada).

#### FR-9: Catálogo de modelos
Modelos vinculados a provedor (id, nome, custo input/output por 1M tokens).

#### FR-10: Modelos permitidos por tenant
Admin associa subset de modelos a cada tenant; um é default.

#### FR-11: Factory multi-provider no harness
`get_llm(tenant)` resolve modelo do DB; OpenAI no MVP; interface extensível.

### 4.4 Base de conhecimento

**Description:** Upload e gestão de documentos por tenant via painel. Realiza UJ-3.

#### FR-12: Upload de documentos
PDF, DOCX, MD, TXT por tenant via API admin.

#### FR-13: Reindexação RAG sob demanda
Endpoint substitui `POST /ops/reindex` com escopo por tenant.

#### FR-14: UI de fontes de conhecimento
Lista documentos, status de indexação, remoção.

### 4.5 Monitoramento de custos

**Description:** Visibilidade operacional para venda e controle.

#### FR-15: Registro de usage events
Toda chamada LLM registra tenant, modelo, tokens in/out, timestamp.

#### FR-16: Dashboard de custos
Custo por tenant, diário/mensal, por modelo no painel admin.

### 4.6 Autenticação e segurança

#### FR-17: RBAC básico
Roles: `super_admin` (MVP); `tenant_admin` (futuro).

#### FR-18: Proteção de endpoints admin
Todos `/admin/api/*` exigem JWT válido.

#### FR-19: API keys LLM nunca expostas ao cliente
Tenants referenciam `model_id`; chaves só no servidor.

## 5. Non-Goals (Explicit)

- Disparos WhatsApp em massa / campanhas
- Billing Stripe integrado (MVP)
- Painel self-service do cliente final (Epic 8)
- Múltiplas instalações Chatwoot
- Planos comerciais com enforcement (Epic 7, pós-MVP imediato)

## 6. MVP Scope

### 6.1 In Scope

- PostgreSQL para tenants, prompts, settings
- DbTenantLoader com fallback filesystem
- API admin: auth JWT + CRUD tenants + prompts
- Painel Next.js + Untitled UI: login, dashboard, wizard tenant
- LLM registry (OpenAI primeiro)
- Migração blackbeans existente

### 6.2 Out of Scope for MVP

- Upload de documentos via painel (Epic 5)
- Dashboard de custos completo (Epic 6 — hook básico ok)
- Painel do cliente (Epic 8)
- Anthropic/Gemini providers (interface pronta, implementação fase 2)

## 7. Success Metrics

| Métrica | Meta MVP |
|---------|----------|
| Tempo para ativar novo tenant | < 15 min |
| Restart necessário para novo cliente | 0 |
| Tenants simultâneos suportados | ≥ 10 |
| Uptime harness pós-migração | Sem regressão em blackbeans |

## 8. NFRs

- **Segurança:** JWT HS256; senhas bcrypt; API keys Fernet at-rest
- **Performance:** Admin API p95 < 500ms; cache tenant TTL 60s
- **Compatibilidade:** Fallback filesystem durante migração
- **Observabilidade:** Audit log de alterações admin

## 9. Open Questions

- [ASSUMPTION] Postgres via docker-compose no mesmo servidor
- [ASSUMPTION] Um único super_admin seed no primeiro deploy
- Planos comerciais: definir após MVP operacional

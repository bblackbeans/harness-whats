# Epics e Stories — Plataforma SaaS

**PRD:** `prd-saas-platform-2026-07-01/prd.md`  
**Architecture:** `architecture/saas-platform/ARCHITECTURE-SPINE.md`  
**Status:** Sprint 1 em implementação

---

## Epic 1: Fundação de dados e migração

### Story 1.1 — Schema Postgres + Alembic

**Como** desenvolvedor, **quero** schema PostgreSQL versionado, **para** persistir tenants dinamicamente.

**AC:**
- [ ] Tabelas: `admin_users`, `tenants`, `tenant_prompts`, `llm_providers`, `llm_models`, `tenant_allowed_models`, `usage_events`
- [ ] Alembic configurado com `DATABASE_URL`
- [ ] Migration inicial aplicável via `alembic upgrade head`
- [ ] docker-compose inclui serviço `postgres`

### Story 1.2 — Script migração blackbeans → DB

**AC:**
- [ ] Script lê `tenants/blackbeans/` e insere no DB
- [ ] Prompts e tenant.json mapeados corretamente
- [ ] Idempotente (skip se tenant existe)

### Story 1.3 — DbTenantLoader com fallback filesystem

**AC:**
- [ ] `get_tenant(id)` consulta DB primeiro
- [ ] `resolve_tenant(event)` usa inbox_ids do DB
- [ ] Fallback para loader filesystem se DB indisponível ou tenant não encontrado
- [ ] Retorna `TenantConfig` compatível com harness existente

### Story 1.4 — Cache com invalidação

**AC:**
- [ ] Cache TTL 60s por tenant_id
- [ ] `invalidate_tenant_cache(id)` chamado em writes admin
- [ ] `list_tenants()` popula do DB

---

## Epic 2: API Admin e autenticação

### Story 2.1 — Auth JWT

**AC:**
- [ ] POST `/admin/api/auth/login` retorna access + refresh token
- [ ] Senhas bcrypt; seed admin via env `ADMIN_EMAIL` / `ADMIN_PASSWORD`
- [ ] Dependency `get_current_admin` valida JWT
- [ ] Expiração access 1h, refresh 7d

### Story 2.2 — CRUD tenants

**AC:**
- [ ] GET/POST `/admin/api/tenants`
- [ ] GET/PUT `/admin/api/tenants/{id}`
- [ ] PATCH `/admin/api/tenants/{id}/active`
- [ ] DELETE soft (active=false) ou hard com query param
- [ ] Payload espelha estrutura tenant.json

### Story 2.3 — CRUD prompts

**AC:**
- [ ] GET `/admin/api/tenants/{id}/prompts`
- [ ] PUT `/admin/api/tenants/{id}/prompts/{name}`
- [ ] Nomes: agent_system, facts_system, summarize_system

### Story 2.4 — Config JSON tenant

**AC:**
- [ ] Settings JSON: routing, context, rag, handoff
- [ ] PUT merge parcial suportado

### Story 2.5 — Audit log

**AC:**
- [ ] Log append em arquivo ou tabela `audit_events`
- [ ] Registra admin_id, action, tenant_id, timestamp

---

## Epic 3: Registro LLMs (parcial MVP)

### Story 3.1 — Tabelas LLM

**AC:** Tabelas criadas na migration 1.1

### Story 3.2 — Factory multi-provider

**AC:**
- [ ] `get_llm(tenant)` resolve model_id do DB
- [ ] OpenAI funcional; fallback env `OPENAI_API_KEY`

### Story 3.3 — API admin LLM (defer Sprint 2)

### Story 3.4 — UI modelos (defer Sprint 2)

---

## Epic 4: Painel Admin Next.js + Untitled UI

### Story 4.1 — Scaffold Next.js + Untitled UI

**AC:**
- [ ] `admin-panel/` com App Router
- [ ] theme.css Untitled UI
- [ ] Página login funcional
- [ ] API client com base URL configurável

### Story 4.2 — Dashboard

**AC:**
- [ ] Sidebar layout
- [ ] Tabela tenants com badges
- [ ] 3 metric cards (total, ativos, inativos)

### Story 4.3 — Wizard criar/editar tenant

**AC:**
- [ ] 4 steps: dados, routing, modelo, prompts
- [ ] POST/PUT para API
- [ ] Redirect após sucesso

### Story 4.4 — Editor prompts (Sprint 2)

### Story 4.5 — Gestão LLM UI (Sprint 2)

### Story 4.6 — Toggle ativo + modal (Sprint 2)

---

## Epic 5-8: Pós-MVP

Ver PRD seção Non-Goals e plano original.

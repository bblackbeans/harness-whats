# Sprint 4 — Painel do Cliente (Epic 8)

**Goal:** Self-service para tenant_admin com escopo restrito ao próprio tenant.

## Stories

### 8.1 — Auth tenant_admin
- Tabela `tenant_users` com escopo por `tenant_id`
- JWT com `role=tenant_admin` e `tenant_id` no payload
- Login em `/portal/api/auth/login`

### 8.2 — Subset self-service
- Prompts (GET/PUT)
- Conhecimento (list/upload/delete/reindex)
- Métricas próprias (`/portal/api/usage`)

### 8.3 — Troca de modelo com aprovação
- Tabela `model_change_requests`
- Cliente solicita em `/portal/api/model-requests`
- Admin aprova/rejeita em `/admin/api/model-requests/*`

## UI
- Portal: `/portal/login`, `/portal`, `/portal/prompts`, `/portal/knowledge`, `/portal/model`
- Admin: usuários portal na edição do tenant; `/settings/model-requests`

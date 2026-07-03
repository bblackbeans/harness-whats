---
story_key: sprint-2-saas-platform
status: done
baseline_commit: ""
---

# Story: Sprint 2 — LLM, Audit, Conhecimento

## Objetivo

Completar épicos 2.5, 3, 4.4-4.6 e 5 do plano SaaS.

## Tasks

- [x] Migration 002 audit_events
- [x] harness_platform: crypto, llm_service, llm_registry, audit_service, usage_service, knowledge_service
- [x] Admin API: /llm/*, /audit, /usage/summary, /tenants/{id}/knowledge/*
- [x] get_llm via DB + seed OpenAI models
- [x] log_llm_usage em run_agent
- [x] knowledge_dir dinâmico para tenants DB
- [x] Painel: editor prompts tabs, modal toggle, settings/llm, upload conhecimento
- [x] Dashboard: custo + audit feed

## File List

- ai/harness_platform/crypto.py
- ai/harness_platform/audit.py
- ai/harness_platform/audit_service.py
- ai/harness_platform/usage_service.py
- ai/harness_platform/llm_registry.py
- ai/harness_platform/llm_service.py
- ai/harness_platform/knowledge_service.py
- ai/alembic/versions/002_audit_events.py
- ai/admin/routes.py (extended)
- ai/agent/llm.py
- ai/agent/nodes.py
- ai/tenants/config.py
- admin-panel/app/settings/llm/page.tsx
- admin-panel/app/tenants/[id]/page.tsx
- admin-panel/components/Modal.tsx

## Completion Notes

Sprint 2 entregue. Reiniciar harness após deploy para carregar novas rotas. Postgres migration 002 obrigatória.

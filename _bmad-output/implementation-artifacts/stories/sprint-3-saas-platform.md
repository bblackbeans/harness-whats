---
story_key: sprint-3-saas-platform
status: done
---

# Story: Sprint 3 — Métricas e Planos

## Entregue

- Migration 003: `plans`, `tenant_subscriptions`
- `plan_service.py` + seed Starter/Pro/Enterprise
- `usage_service.py`: resumo mensal, diário, por modelo, por tenant
- `limit_enforcement.py`: bloqueio hard no ingress
- API: `/plans`, `/tenants/{id}/plan`, `/usage/daily`, `/usage/by-model`
- Painel: `/usage`, `/settings/plans`, plano no tenant edit

## Critério de done

Admin associa plano Pro ao tenant; métricas aparecem em /usage; modo hard bloqueia mensagens ao exceder limite.

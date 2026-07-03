---
title: Admin Panel Experience Spine
status: final
---

# Experience Spine — Painel Admin

## Foundation

Single-surface responsive web admin. Untitled UI React on Next.js 15 App Router. Audience: platform super_admin only (MVP).

## Information Architecture

| Surface | Route | Purpose |
|---------|-------|---------|
| Login | `/login` | Auth |
| Dashboard | `/` | Tenants overview + metrics |
| New tenant | `/tenants/new` | Wizard criação |
| Edit tenant | `/tenants/[id]` | Config + prompts |
| LLM (fase 2) | `/settings/llm` | Providers |

Sidebar: Dashboard, Tenants, Settings (collapsed on mobile → drawer).

## Voice and Tone

| Do | Don't |
|----|-------|
| "Tenant criado" | "Sucesso! 🎉" |
| "3 tenants ativos" | "Você tem 3 tenants ativos no momento." |
| "Falha ao salvar" | "Oops, algo deu errado" |

## State Patterns

| State | Treatment |
|-------|-----------|
| Loading dashboard | Skeleton rows (4) |
| Empty tenants | "Nenhum tenant. Crie o primeiro." + CTA |
| API error | Toast vermelho + retry |
| Unauthenticated | Redirect `/login` |

## Key Flows

**Create tenant:** Dashboard → Novo → Step 1 dados → Step 2 Chatwoot IDs → Step 3 modelo → Step 4 prompts → Salvar → redirect detail.

**Toggle active:** Detail → Switch → Modal confirm → PATCH → toast.

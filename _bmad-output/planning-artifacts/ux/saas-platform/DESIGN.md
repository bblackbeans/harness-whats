---
title: Admin Panel Design — Untitled UI
status: final
created: 2026-07-01
source: https://www.untitledui.com/figma
---

# DESIGN.md — Painel Admin Harness

## Foundation

**Untitled UI Free** como source of truth visual. Implementação via [Untitled UI React](https://www.untitledui.com/react) (MIT, componentes free) + Tailwind CSS v4 + `@untitledui/icons`.

Dark mode: CSS variables do `theme.css` oficial. Brand color: `brand` (default Untitled UI).

## Typography & Spacing

Herdar tokens do starter kit. Headlines: `display-sm` / `text-lg font-semibold`. Body: `text-sm text-secondary`. Spacing: grid 4px (Tailwind scale).

## Components (free scope MVP)

| Component | Usage |
|-----------|-------|
| Sidebar navigation | Layout persistente |
| Table | Lista de tenants |
| Badge | Status ativo/inativo |
| Button (primary/secondary) | Ações |
| Modal | Confirmar desativar tenant |
| Tabs | Editor de prompts |
| Input / Textarea | Forms wizard |
| Select / Combobox | Modelo LLM |
| Switch | Toggle ativo |
| Metrics card | Dashboard resumo |
| Alert | Erros de API |

## Color Semantics

- **Success/Active:** badge verde — tenant ativo
- **Warning:** limite de uso próximo (fase 2)
- **Error:** falha API, tenant inativo bloqueado
- **Neutral:** métricas, labels secundários

## Screens

1. **Login** — centered card, logo Harness, email + password
2. **Dashboard** — sidebar + 3 metric cards + tabela tenants
3. **Tenant wizard** — 4 steps com progress indicator
4. **Tenant detail** — settings sections + prompt tabs
5. **LLM models** — table providers + assign to tenant (fase 2 UI)

## Accessibility

React Aria primitives do Untitled UI. Focus visible em todos os controles. Labels em todos os inputs.

---
title: Handoff Humano no Chatwoot
status: final
created: 2026-06-23
updated: 2026-06-23
---

# PRD: Handoff para Atendente Humano (Chatwoot)

**Produto:** Langchain Automation Harness — Fase 4  
**Depende de:** RAG por tenant (Fase 3), integração Chatwoot Agent Bot

## 1. Visão

Quando o bot não sabe responder, o cliente pede um humano, ou a pergunta exige decisão comercial, a conversa deve **sair do bot** e aparecer na fila de agentes humanos no Chatwoot — sem o cliente ficar preso em respostas genéricas.

No Chatwoot, conversas com Agent Bot começam em `pending`. O handoff oficial é `POST toggle_status` com `status: open` usando o token do bot, o que dispara `bot_handoff!` no Chatwoot.

## 2. Jornadas

**UJ-1.** Maria pergunta preço enterprise. FAQ não tem preço. Bot responde que não tem a informação e oferece humano. Maria diz "quero falar com atendente". Bot confirma, envia mensagem de transferência e abre a conversa para humanos.

**UJ-2.** Conversa já em handoff (`status: open`). Cliente manda nova mensagem. Bot **não responde** — humano assume.

## 3. Glossário

- **Handoff** — transferência da conversa do bot para fila humana no Chatwoot.
- **Pending** — status Chatwoot enquanto o bot atende.
- **Open** — status após handoff; agentes humanos veem na inbox.

## 4. Features e FRs

### 4.1 Detecção de handoff

#### FR-1: Campo `handoff_to_human` no JSON do agente
LLM retorna `handoff_to_human: boolean` junto com intent/reply.

#### FR-2: Palavras-chave configuráveis por tenant
Se mensagem contém termos como "atendente", "humano", força handoff.

#### FR-3: Handoff por ausência de conhecimento (opcional)
Se `on_no_knowledge: true` e material recuperado vazio + pergunta factual → handoff.

### 4.2 Execução no Chatwoot

#### FR-4: Toggle status para `open`
Chamar API Chatwoot após decisão de handoff.

#### FR-5: Mensagem ao cliente antes do handoff
Enviar texto configurável (`handoff.message`) se ainda não enviada pelo agente.

#### FR-6: Nota privada para agentes (opcional)
Mensagem `private: true` com resumo: intent, última pergunta, motivo do handoff.

### 4.3 Proteção pós-handoff

#### FR-7: Ignorar mensagens em conversas `open`
Webhook não processa se `conversation.status == open` (humano no controle).

### 4.4 Configuração multi-tenant

#### FR-8: Bloco `handoff` em `tenant.json`
`enabled`, `message`, `keywords`, `on_no_knowledge`, `private_note_enabled`.

## 5. Não-objetivos v1

- Atribuição automática a agente específico (assignee_id) — opcional futuro
- SLA / fila prioritária
- Reativar bot automaticamente após resolução

## 6. MVP

- Detecção: LLM + keywords
- Toggle `open` + mensagem cliente
- Nota privada com resumo
- Filtro `open` no ingress
- Config em tenant + prompts atualizados

## 7. Métricas

- **SM-1:** 100% dos pedidos explícitos de humano resultam em `status: open` no Chatwoot.
- **SM-2:** 0 respostas automáticas do bot após handoff na mesma conversa.

---

_PRD BMAD — handoff humano_

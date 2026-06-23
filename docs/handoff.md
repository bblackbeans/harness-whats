# Handoff — Transferência para Atendente Humano

## O que é handoff?

**Handoff** (em português: *passagem de bastão*) é o momento em que a conversa **sai do bot** e vai para um **atendente humano** no Chatwoot.

Pense assim:

```
Cliente ←→ Bot (IA)          →  durante o atendimento automático
Cliente ←→ Atendente humano  →  após o handoff
```

O bot não “some” do sistema — ele **entrega a conversa** para a fila de agentes humanos, que passam a ver e responder no painel do Chatwoot.

---

## Por que existe?

O bot é ótimo para dúvidas frequentes e respostas com base no FAQ (RAG). Mas há situações em que um humano é necessário:

- Cliente pede explicitamente: *"quero falar com um atendente"*
- Pergunta sobre **preço, prazo ou contrato** que não está no FAQ
- Assunto sensível ou fora do escopo do bot
- IA reconhece que não tem informação suficiente

Sem handoff, o bot improvisaria ou ficaria repetindo “não sei” — o cliente ficaria preso.

---

## Como funciona no Chatwoot?

No Chatwoot, conversas com **Agent Bot** seguem este ciclo de status:

| Status | Quem atende |
|---|---|
| `pending` | Bot (IA) — conversa nova ou sob controle do bot |
| `open` | Humanos — após handoff, aparece na inbox dos agentes |
| `resolved` | Conversa encerrada |

O handoff oficial do Chatwoot é a API:

```
POST /conversations/{id}/toggle_status
{ "status": "open" }
```

Quando o **token do Agent Bot** faz isso saindo de `pending`, o Chatwoot dispara internamente o `bot_handoff!` — a conversa entra na fila humana.

---

## Como o harness decide fazer handoff?

Três gatilhos (configuráveis por tenant em `tenant.json` → `handoff`):

### 1. Palavras-chave
Se a mensagem contém termos como `atendente`, `humano`, `consultor` → handoff imediato.

### 2. Decisão da IA
O LLM retorna no JSON: `"handoff_to_human": true` quando entende que deve transferir.

### 3. Sem conhecimento (RAG vazio)
Se `on_no_knowledge: true` e a pergunta parece ser sobre preço/prazo/orçamento, mas o FAQ não tem resposta → handoff.

---

## O que acontece na prática (passo a passo)

```
1. Cliente: "Qual o preço do plano enterprise?"
2. Harness busca FAQ → não acha preço
3. Bot responde: "Não tenho essa informação, vou encaminhar..."
4. Harness chama toggle_status → open
5. Harness envia nota PRIVADA para agentes com resumo
6. Agente humano vê a conversa no Chatwoot e assume
7. Próximas mensagens do cliente → bot IGNORA (status já é open)
```

---

## Configuração por tenant

Em `tenants/<id>/tenant.json`:

```json
"handoff": {
  "enabled": true,
  "message": "Vou encaminhar você para um consultor. Aguarde um momento.",
  "keywords": ["atendente", "humano", "pessoa", "consultor"],
  "on_no_knowledge": true,
  "private_note_enabled": true
}
```

| Campo | Função |
|---|---|
| `enabled` | Liga/desliga handoff |
| `message` | Texto enviado ao cliente se o bot não tiver respondido |
| `keywords` | Lista de termos que forçam handoff |
| `on_no_knowledge` | Handoff quando FAQ não responde pergunta factual |
| `private_note_enabled` | Nota interna para agentes com resumo |

---

## No grafo LangGraph

```
agent → persist_memory
           ↓
      send_reply (se tiver resposta)
           ↓
      execute_handoff (se handoff_to_human)
           ↓
         END
```

Arquivos principais:
- `ai/handoff/policy.py` — regras de detecção
- `ai/harness/handoff.py` — nó `execute_handoff`
- `ai/integrations/chatwoot.py` — `handoff_conversation()`, `send_private_note()`

---

## Como testar

1. No Telegram: *"Quero falar com um atendente"*
2. No Chatwoot: conversa deve mudar para **open** e aparecer para agentes
3. Mandar outra mensagem: bot **não** deve responder
4. `GET /ops/recent` → status `handed_off`

---

## PRD e epics (BMAD)

- PRD: `_bmad-output/planning-artifacts/prds/prd-harness-handoff-2026-06-23/prd.md`
- Stories: `_bmad-output/planning-artifacts/epics-and-stories/handoff-epics-and-stories.md`

---

_Atualizado em 2026-06-23_

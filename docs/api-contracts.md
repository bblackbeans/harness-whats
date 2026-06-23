# Contratos de API — Harness

**Base URL:** `http://localhost:8787` (ou URL de produção)  
**Formato:** JSON

## Endpoints

### `GET /health`

Verifica status do serviço e tenants carregados.

**Resposta 200:**
```json
{
  "status": "ok",
  "tenant_id": "blackbeans",
  "tenants": [
    {
      "id": "blackbeans",
      "name": "BlackBeans",
      "model": "gpt-4o-mini",
      "inbox_ids": []
    }
  ],
  "chatwoot_configured": true,
  "openai_configured": true,
  "architecture": { "...": "..." }
}
```

---

### `GET /ops/recent?limit=50`

Lista eventos recentes do ciclo de vida das mensagens.

**Query:** `limit` (default 50)

**Resposta 200:**
```json
{
  "events": [
    {
      "ts": "2026-06-23T12:00:00+00:00",
      "delivery_id": "...",
      "message_id": "123",
      "conversation_id": 1,
      "status": "replied",
      "detail": "question"
    }
  ]
}
```

**Status possíveis:** `received`, `processing`, `replied`, `handed_off`, `ignored`, `failed`, `duplicate`

---

### `POST /ops/reindex?tenant_id=blackbeans`

Reindexa FAQ/RAG do tenant. Sem `tenant_id`, reindexa todos.

**Resposta 200:**
```json
{
  "reindexed": [
    { "tenant_id": "blackbeans", "indexed": 12, "skipped": 0, "errors": 0, "files": ["knowledge/faq.md"] }
  ]
}
```

---

### `POST /webhooks/chatwoot`

Webhook principal — Chatwoot Agent Bot aponta para esta URL.

**Headers esperados:**
- `X-Chatwoot-Signature` (se `CHATWOOT_WEBHOOK_SECRET` configurado)
- `X-Chatwoot-Timestamp`
- `X-Chatwoot-Delivery` (usado para dedupe)

**Body:** payload JSON do Chatwoot (`event: message_created`)

**Respostas:**

| Código | Condição | Body |
|---|---|---|
| 202 | Mensagem aceita | `{"accepted": true, "conversation_id": N}` |
| 200 | Evento ignorado | `{"ignored": true}` |
| 200 | Duplicata | `{"duplicate": true}` |
| 401 | Assinatura inválida | `{"detail": "..."}` |

**Eventos ignorados:**
- Não é `message_created`
- Não é `incoming`
- Sender é `user` ou `agent_bot`
- `conversation.status == open` (já em handoff — humano atende)
- Conteúdo vazio

---

### `POST /dispatch`

Disparo proativo de mensagens para múltiplas conversas.

**Body:**
```json
{
  "mode": "conversation",
  "message": "Olá {nome}, tudo bem?",
  "tenant_id": "blackbeans",
  "account_id": 1,
  "contacts": [
    {
      "conversation_id": 42,
      "variables": { "nome": "Kauê" }
    }
  ]
}
```

**Modos:**

| mode | Campos obrigatórios | Uso |
|---|---|---|
| `conversation` | `message` | Texto personalizado por IA ou template simples |
| `template` | `template_name`, `message` | Template WhatsApp Cloud (não funciona no Telegram) |

**Resposta 200:**
```json
[
  { "conversation_id": 42, "ok": true, "error": null }
]
```

---

## API externa consumida — Chatwoot

### Enviar mensagem
```
POST {CHATWOOT_BASE_URL}/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages
Header: api_access_token: {CHATWOOT_BOT_TOKEN}
Body: { "content": "...", "message_type": "outgoing", "private": false }
```

### Handoff para humano
```
POST .../conversations/{conversation_id}/toggle_status
Body: { "status": "open" }
```

### Nota privada (agentes)
```
POST .../messages
Body: { "content": "...", "message_type": "outgoing", "private": true }
```

---

## Contrato de saída do agente IA

O LLM deve retornar JSON:

```json
{
  "intent": "greeting | question | support | sales | other",
  "should_reply": true,
  "reply": "Texto da resposta em português",
  "handoff_to_human": false,
  "new_facts": ["fato durável sobre o usuário"]
}
```

---

_Gerado pelo workflow BMAD `document-project`_

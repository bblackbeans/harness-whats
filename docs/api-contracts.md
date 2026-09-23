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

Disparo proativo de mensagens para múltiplas conversas (via Chatwoot → WhatsApp Cloud / Meta).

Cada contato precisa de `conversation_id` **ou** `phone` (+ `inbox_id` / `chatwoot_inbox_ids` do tenant). Com telefone, o harness cria/obtém contato e conversa no Chatwoot antes de enviar.

**Body (conversa existente):**
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

**Body (por telefone + template Meta):**
```json
{
  "mode": "template",
  "template_name": "boas_vindas",
  "language": "pt_BR",
  "message": "boas_vindas",
  "tenant_id": "clinica-bem-estar",
  "inbox_id": 12,
  "contacts": [
    {
      "phone": "5511999999999",
      "name": "Maria",
      "processed_params": { "1": "Maria" }
    }
  ]
}
```

**Modos:**

| mode | Campos obrigatórios | Uso |
|---|---|---|
| `conversation` | `message` | Texto livre — só dentro da janela de 24h após o cliente escrever |
| `template` | `template_name` | Template WhatsApp Cloud aprovado (fora de 24h / primeiro contato) |

**Pré-requisito de canal:** inbox **WhatsApp Cloud (API oficial Meta)** no Chatwoot + templates aprovados no Meta Business Manager. Evolution/QR não serve para template oficial.

**Resposta 200:**
```json
[
  { "conversation_id": 42, "phone": "5511999999999", "ok": true, "error": null }
]
```

### Campanhas CRM (`/admin/api/tenants/{id}/crm/campaigns` e portal)

| Método | Rota | Uso |
|---|---|---|
| GET | `/campaigns` | Listar campanhas |
| POST | `/campaigns` | Criar (template/texto + `contact_ids` / `phones`) |
| GET | `/campaigns/{id}` | Detalhe + destinatários |
| POST | `/campaigns/{id}/send` | Enviar agora |
| POST | `/campaigns/{id}/schedule` | Agendar (`{"scheduled_at": "..."}`) |
| POST | `/campaigns/{id}/cancel` | Cancelar |

O scheduler interno (poll no processo FastAPI) dispara campanhas com `status=scheduled` quando `scheduled_at` chega.

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

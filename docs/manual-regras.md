# Manual de Regras — Harness por Tenant

Guia prático para entender e ajustar o comportamento do bot (BlackBeans ou outro cliente).

---

## 1. Onde personalizar (sem mexer no código)

Cada cliente fica em `tenants/<id>/`:

| Arquivo | O que controla |
|---|---|
| `tenant.json` | Modelo, RAG, handoff, contexto |
| `prompts/agent_system.txt` | Personalidade e regras da IA |
| `prompts/facts_system.txt` | O que salvar na memória do cliente |
| `prompts/summarize_system.txt` | Como resumir conversas longas |
| `knowledge/faq.md` | Base oficial (RAG) — preços, serviços, contato |

Depois de editar o FAQ: `POST /ops/reindex?tenant_id=<id>`

---

## 2. Fluxo de uma mensagem

```
Cliente (Telegram/WhatsApp)
    → Chatwoot
    → Webhook harness
    → [se status = open] IGNORA (humano atende)
    → Memória + contexto + RAG
    → IA responde (JSON)
    → Envia resposta no Chatwoot
    → [se handoff] passa para humano
```

---

## 3. Status no Chatwoot

| Status | Quem atende | Bot responde? |
|---|---|---|
| `pending` | Bot (IA) | Sim |
| `open` | Humano | Não |
| `resolved` | Encerrada | Não (até voltar a `pending`) |

### Devolver ao bot

- **Clique Resolver** no Chatwoot → harness reativa o bot na **mesma conversa** (`resume_bot_on_resolve`)
- Aparece: *"marcada como pendente por harness-whats"*
- Não precisa curl

### Quando o bot fica mudo

Sempre que a conversa estiver `open` (handoff ou humano respondeu no painel).  
**Solução:** clique **Resolver** para o bot voltar.

---

## 4. Quando o bot faz HANDOFF (passa pro humano)

Ordem de avaliação (em `ai/handoff/policy.py` + prompt):

### 4.1 Palavras-chave — handoff imediato

Config: `tenant.json` → `handoff.keywords`

Padrão BlackBeans: `atendente`, `humano`, `pessoa`, `consultor`

**Ajustar:** edite a lista `keywords` no `tenant.json`.

---

### 4.2 Perguntas que NUNCA fazem handoff

**Gerais** (bot responde sozinho, sem FAQ):
- data/hora: "que dia", "qual hora"…
- cumprimentos: "bom dia", "tudo bem"…
- identidade: "quem é você"

**Informativas** (contato da empresa):
- "contato", "email", "telefone", "site", "whatsapp"…

**Ajustar:** listas `_GENERAL_REPLY_SIGNALS` e `_INFORMATIONAL_SIGNALS` em `ai/handoff/policy.py`.

---

### 4.3 Perguntas comerciais — handoff se FAQ não tiver resposta

Só dispara se `on_no_knowledge: true` E mensagem contém termos como:
- quanto, preço, valor, prazo, orçamento, contrato, proposta, cotação, plano

E o RAG **não** recuperou chunks do FAQ.

**Ajustar:**
- Adicione/remova termos em `_COMMERCIAL_SIGNALS` (`policy.py`)
- Ou desligue: `"on_no_knowledge": false` no `tenant.json`

---

### 4.4 Decisão da IA (`handoff_to_human: true`)

O LLM pode pedir handoff no JSON, mas o código **só aceita** se for pergunta **comercial**.

Perguntas de contato/data/etc. → IA pede handoff → **ignorado**.

**Ajustar:** edite `prompts/agent_system.txt` (regras de quando `handoff_to_human = true`).

---

### 4.5 Proteção: bot já respondeu

Se o bot gerou uma resposta (`reply` não vazio), **não** faz handoff `no_knowledge` no mesmo turno.

Evita: responder "posso ajudar com contato" e transferir pro humano na hora.

---

## 5. O que a IA pode e não pode inventar

No `agent_system.txt`:

| Tipo | Regra |
|---|---|
| Fatos da empresa (serviços, preços, políticas) | **Só** do FAQ (RAG) |
| Data, hora, cumprimentos | Responde sozinha |
| Preço/orçamento sem FAQ | Handoff ou "não tenho essa info" |
| Fora do escopo | `should_reply: false` (não responde) |

**Ajustar:** reescreva o `agent_system.txt` do tenant.

---

## 6. RAG (FAQ)

- Fonte: `tenants/<id>/knowledge/*.md`
- Indexação: SQLite em `data/rag/<id>.db`
- Na mensagem: busca top-K chunks similares → injeta no contexto da IA

Config em `tenant.json`:

```json
"rag": {
  "enabled": true,
  "top_k": 5
}
```

**Dica:** quanto mais completo o FAQ (contato, serviços, o que NÃO informar), menos handoff errado.

---

## 7. Memória do cliente

| Tipo | Onde | Persiste? |
|---|---|---|
| Fatos ("cliente quer orçamento") | SQLite `semantic_memory` | Sim |
| Resumo da conversa longa | Grafo LangGraph | Enquanto container rodar |
| Histórico completo Chatwoot | Painel Chatwoot | Sim (bot não relê tudo) |

Config contexto:

```json
"context": {
  "summarize_after": 12,
  "keep_recent": 6
}
```

---

## 8. Config completa `handoff` no tenant.json

```json
"handoff": {
  "enabled": true,
  "message": "Texto ao cliente quando for encaminhar",
  "keywords": ["atendente", "humano"],
  "on_no_knowledge": true,
  "private_note_enabled": true,
  "auto_resume_on_resolved": true,
  "resume_bot_on_resolve": true
}
```

| Campo | Função |
|---|---|
| `enabled` | Liga/desliga handoff |
| `message` | Mensagem pro cliente se bot não tiver respondido |
| `keywords` | Palavras que forçam handoff |
| `on_no_knowledge` | Handoff em pergunta comercial sem FAQ |
| `private_note_enabled` | Nota interna pros agentes no Chatwoot |
| `auto_resume_on_resolved` | Cliente escreve em conversa resolved → bot reativa |
| `resume_bot_on_resolve` | Clicar Resolver → bot volta (mesma conversa) |

---

## 9. Cenários rápidos (cola)

| Cliente diz | Bot deve |
|---|---|
| "Oi" | Cumprimentar |
| "Que dia é hoje?" | Responder a data |
| "Como entro em contato?" | Usar FAQ (site/email) |
| "Quanto custa?" sem FAQ | Handoff ou avisar + handoff |
| "Quero um atendente" | Handoff imediato |
| Humano respondeu no painel | Parar até Resolver |
| Clicou Resolver | Bot volta na mesma conversa |

---

## 10. Onde mexer no código (se precisar)

| Quer mudar | Arquivo |
|---|---|
| Regras de handoff (listas de palavras) | `ai/handoff/policy.py` |
| Texto da nota privada | `ai/harness/handoff.py` |
| Ordem do pipeline | `ai/harness/graph.py` |
| Ignorar mensagens em `open` | `ai/integrations/chatwoot.py` |
| Auto-resume ao Resolver | `ai/handoff/resume.py` |

---

## 11. Variáveis de ambiente importantes

| Variável | Função |
|---|---|
| `TENANT_ID` | Cliente ativo (ex: `blackbeans`) |
| `CHATWOOT_BASE_URL` | URL exata do Chatwoot |
| `CHATWOOT_BOT_TOKEN` | Token do Agent Bot |
| `CHATWOOT_ACCOUNT_ID` | ID da conta |
| `OPENAI_API_KEY` | LLM + embeddings RAG |
| `RAG_ENABLED` | Liga/desliga RAG global |

---

_Atualizado em 2026-06-26_

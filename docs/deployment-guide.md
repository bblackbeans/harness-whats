# Guia de Deploy

## Docker Compose (recomendado)

```bash
# .env na raiz do projeto
docker compose up -d --build
```

**Serviço:** `harness`  
**Porta:** `${PORT:-8787}:8787`  
**Volumes:**
- `harness_data:/app/data` — SQLite + logs
- `./tenants:/app/tenants:ro` — configs por cliente

### Variáveis obrigatórias em produção

```env
TENANT_ID=blackbeans
TENANTS_DIR=/app/tenants
CHATWOOT_BASE_URL=https://chatwoot.seudominio.com
CHATWOOT_BOT_TOKEN=...
CHATWOOT_ACCOUNT_ID=...
OPENAI_API_KEY=sk-...
```

Opcional: `CHATWOOT_WEBHOOK_SECRET` para validar assinatura.

## Easypanel / VPS

1. Deploy do repositório como serviço Docker
2. Expor porta 8787 (ou reverse proxy HTTPS)
3. Montar volume para `data/` (persistência de memória)
4. Montar `tenants/` como volume read-only
5. URL pública do harness → webhook do Agent Bot no Chatwoot

**Importante:** Chatwoot precisa alcançar `https://seu-harness/webhooks/chatwoot`.

## Chatwoot (lado canal)

### Telegram
- Inbox Telegram com token do @BotFather
- Agent Bot `harness-whats` (ou nome escolhido) ligado ao inbox
- Webhook do bot → URL do harness

### WhatsApp (futuro)
- Inbox WhatsApp Cloud no Chatwoot
- Mesmo agent bot ou bot separado por cliente
- Templates via `POST /dispatch` mode `template`

## Multi-tenant em um deploy

Deixar `TENANT_ID` vazio e configurar em cada `tenant.json`:

```json
"routing": {
  "chatwoot_inbox_ids": [42]
}
```

Cada inbox do Chatwoot mapeia para um tenant.

## Multi-tenant com deploys separados

Um container por cliente:
- Mesma imagem Docker
- `.env` diferente (`TENANT_ID`, tokens Chatwoot)
- Pasta `tenants/<cliente>/` montada ou embutida

## Health check

```bash
curl https://seu-harness/health
```

Usar em monitoramento (Uptime Kuma, etc.).

## Backup

Arquivos a preservar:
- `data/semantic_memory.db` — memória dos usuários
- `data/ops.jsonl` — histórico operacional
- `tenants/` — configs e prompts (já no Git)

## Atualização

```bash
git pull
docker compose up -d --build
```

Prompts em `tenants/` podem ser atualizados sem rebuild se montados como volume — restart do container basta.

## Segurança

- Nunca commitar `.env`
- Usar `CHATWOOT_WEBHOOK_SECRET` em produção
- HTTPS obrigatório na URL pública
- `CHATWOOT_BOT_TOKEN` com permissões mínimas do agent bot

---

_Gerado pelo workflow BMAD `document-project`_

# Addendum — Decisões técnicas (RAG Harness)

*Conteúdo que complementa o PRD mas é detalhe de implementação.*

## Onde encaixar no grafo LangGraph

Opção recomendada: **novo nó `retrieve_knowledge`** entre `manage_context` e `agent`:

```
manage_context → retrieve_knowledge → agent → ...
```

Alternativa rejeitada: busca dentro de `run_agent` — mistura recuperação com geração e dificulta testes.

## Armazenamento do índice

**Proposta v1:** SQLite em `data/rag/{tenant_id}.db` com tabela:

```sql
CREATE TABLE knowledge_chunks (
  tenant_id TEXT,
  source_path TEXT,
  chunk_index INTEGER,
  content_hash TEXT,
  text TEXT,
  embedding BLOB,  -- ou JSON array
  PRIMARY KEY (tenant_id, source_path, chunk_index)
);
```

**Alternativa v2:** ChromaDB ou LanceDB se escala exigir.

## Chunking

- Tamanho alvo: ~500 tokens, overlap 50 tokens
- Separadores: `\n\n`, depois `\n`, depois `. `
- Biblioteca: `langchain-text-splitters` (já no ecossistema LangChain)

## Config em `tenant.json` (extensão futura)

```json
"rag": {
  "enabled": true,
  "top_k": 5,
  "embedding_model": "text-embedding-3-small",
  "chunk_size": 500
}
```

MVP pode usar defaults globais em `.env`; extensão por tenant na v1.1.

## Prompt — trecho sugerido para `agent_system.txt`

```
Material oficial recuperado:
{retrieved_knowledge}

Regras sobre material oficial:
- Fatos sobre a empresa, produtos, preços e políticas: use SOMENTE o material acima.
- Se o material não contiver a resposta, diga que não possui essa informação.
- Nunca invente valores, prazos ou compromissos.
```

## FAQ inicial BlackBeans (exemplo)

Arquivo: `tenants/blackbeans/knowledge/faq.md` — a preencher com conteúdo real da empresa antes de go-live RAG.

## Integração com deploy

- Volume `tenants/` já montado read-only no Docker
- Após editar `knowledge/`, restart ou endpoint futuro `POST /ops/reindex?tenant=blackbeans`
- MVP: reindex no primeiro request após detectar mudança de hash

---

_Addendum vinculado ao PRD `prd-harness-rag-2026-06-23`_

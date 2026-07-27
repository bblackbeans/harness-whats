"""Compila .flow/.json em roteiro operacional + checklist via LLM."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from agent.llm import get_llm, log_llm_usage
from tenants import get_tenant

logger = logging.getLogger(__name__)

_COMPILER_SYSTEM = """Você é um compilador de fluxos de atendimento (estilo HyperFlow) para um roteiro operacional de IA.

Recebe um arquivo .flow ou .json exportado e deve extrair a lógica de negócio.

Formato HyperFlow típico: objeto com `flow.nodes` (ou `nodes` na raiz). Cada nó tem
`id`, `type` e frequentemente `data.name` / `data.label` / `name`. Ignore campos de layout
(width, height, position, selected). NÃO trate linhas de JSON bruto como etapas.

Retorne APENAS JSON válido (sem markdown) com esta estrutura:
{
  "import_summary": {
    "titulo": "string",
    "etapas_resumo": ["1. ...", "2. ..."],
    "campos_detectados": ["nome", "cpf"],
    "integracoes_detectadas": ["API X"],
    "handoff": true,
    "observacoes": "string"
  },
  "roteiro": {
    "objetivo": "string",
    "etapas": [
      {
        "id": "ask_nome",
        "titulo": "Perguntar nome",
        "obrigatoria": true,
        "campos": ["nome"],
        "validacao": {"tipo": "texto_nao_vazio"},
        "tools": [{"type": "save_field", "params": {"key": "nome"}, "condicao": "sempre"}],
        "quando_api": null,
        "quando_arquivo": null,
        "quando_handoff": false
      }
    ],
    "campos_obrigatorios": ["nome"],
    "campos_opcionais": [],
    "ferramentas": ["save_field", "http_request", "send_file", "handoff"],
    "encerramento": "string",
    "handoff_quando": "string"
  },
  "checklist": [
    {"id": "ask_nome", "titulo": "Perguntar nome"},
    {"id": "save_dados", "titulo": "Salvar dados"}
  ],
  "base_prompt": "Instruções curtas em português para a IA seguir este roteiro de forma natural."
}

Tipos de tool: save_field, add_tag, http_request, send_file, handoff.
Validações comuns: texto_nao_vazio, email, cpf, numero, telefone.
IDs de etapa: snake_case curto e estável.
Mapeie nós de automação HyperFlow para etapas operacionais claras (ex.: "Enviar pesquisa de satisfação",
"Encerrar atendimento", "Responder webhook 200"). Não invente etapas conversacionais que não existam;
se o fluxo for só automação (webhook/API), descreva as ações reais do arquivo.
"""

_NODE_TYPE_LABELS = {
    "start": "Início / gatilho",
    "trigger": "Gatilho",
    "webhook": "Webhook",
    "finishattendance": "Encerrar atendimento",
    "finish_attendance": "Encerrar atendimento",
    "endattendance": "Encerrar atendimento",
    "satisfactionresearch": "Pesquisa de satisfação",
    "satisfaction_research": "Pesquisa de satisfação",
    "satisfaction": "Pesquisa de satisfação",
    "research": "Pesquisa de satisfação",
    "json": "Resposta JSON",
    "sendmessage": "Enviar mensagem",
    "send_message": "Enviar mensagem",
    "message": "Enviar mensagem",
    "http": "Chamada HTTP",
    "httprequest": "Chamada HTTP",
    "http_request": "Chamada HTTP",
    "handoff": "Transferir para humano",
    "transfer": "Transferir para humano",
    "gpt": "Resposta com IA",
    "llm": "Resposta com IA",
    "wait": "Aguardar",
    "condition": "Condição / ramificação",
    "branch": "Condição / ramificação",
}

_SKIP_NODE_TYPES = {
    "note",
    "comment",
    "annotation",
    "group",
    "sticky",
}


def _decode_source(raw_bytes: bytes, filename: str) -> str:
    name = (filename or "").lower()
    text = ""
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            text = raw_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw_bytes.decode("utf-8", errors="replace")

    if name.endswith(".json") or name.endswith(".flow") or text.strip().startswith(("{", "[")):
        try:
            parsed = json.loads(text)
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            pass
    return text


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _dig_nodes(data: dict) -> list:
    """Localiza lista de nós em formatos HyperFlow / genéricos."""
    candidates: list[Any] = [
        data.get("nodes"),
        data.get("steps"),
        data.get("etapas"),
        _as_dict(data.get("flow")).get("nodes"),
        _as_dict(data.get("flow")).get("steps"),
        _as_dict(data.get("definition")).get("nodes"),
        _as_dict(data.get("data")).get("nodes"),
        _as_dict(data.get("graph")).get("nodes"),
        _as_dict(_as_dict(data.get("flow")).get("data")).get("nodes"),
    ]
    for nodes in candidates:
        if isinstance(nodes, list) and nodes:
            return nodes
    return []


def _node_type(node: dict) -> str:
    raw = (
        node.get("type")
        or node.get("nodeType")
        or _as_dict(node.get("data")).get("type")
        or _as_dict(node.get("data")).get("nodeType")
        or ""
    )
    return str(raw).strip()


def _node_title(node: dict, index: int) -> str:
    data = _as_dict(node.get("data"))
    params = _as_dict(node.get("params"))
    for key in (
        "title",
        "titulo",
        "name",
        "label",
        "displayName",
        "description",
    ):
        for src in (node, data, params, _as_dict(data.get("config"))):
            val = src.get(key)
            if isinstance(val, str) and val.strip() and len(val.strip()) < 200:
                # Evita títulos que são só JSON syntax
                if val.strip() not in {"{", "}", "[", "]", ","}:
                    return val.strip()[:120]

    # Labels aninhados comuns no HyperFlow (badges / templates)
    for key in ("templateName", "template", "action", "method", "path"):
        val = data.get(key) or params.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()[:120]

    ntype = _node_type(node)
    key = re.sub(r"[^a-z0-9_]", "", ntype.lower())
    if key in _NODE_TYPE_LABELS:
        return _NODE_TYPE_LABELS[key]
    if ntype:
        # camelCase → palavras
        spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", ntype).replace("_", " ").strip()
        if spaced:
            return spaced[:120]
    return f"Etapa {index + 1}"


def _slugify(text: str, fallback: str) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFD", text)
    ascii_text = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_text.lower()).strip("_")[:40]
    return slug or fallback


def _tools_for_node(node: dict) -> list[dict]:
    ntype = re.sub(r"[^a-z0-9_]", "", _node_type(node).lower())
    tools: list[dict] = []
    if ntype in {"http", "httprequest", "http_request", "webhook", "json", "graphql"}:
        tools.append({"type": "http_request", "params": {}, "condicao": "sempre"})
    if ntype in {"handoff", "transfer", "finishattendance", "finish_attendance", "endattendance"}:
        tools.append({"type": "handoff", "params": {}, "condicao": "sempre"})
    if ntype in {"sendmessage", "send_message", "message", "satisfactionresearch", "satisfaction_research", "satisfaction"}:
        tools.append({"type": "send_file", "params": {}, "condicao": "opcional"})
    return tools


def _extract_etapas_from_nodes(nodes: list) -> tuple[list[dict], list[str], list[str]]:
    etapas: list[dict] = []
    campos: list[str] = []
    integracoes: list[str] = []
    used_ids: set[str] = set()

    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        ntype = _node_type(node)
        ntype_key = re.sub(r"[^a-z0-9_]", "", ntype.lower())
        if ntype_key in _SKIP_NODE_TYPES:
            continue

        titulo = _node_title(node, i)
        # Pula nós sem conteúdo útil (só layout)
        if not ntype and titulo.startswith("Etapa ") and not node.get("id"):
            continue

        raw_id = str(node.get("id") or "")
        sid = _slugify(titulo, f"step_{i + 1}")
        if raw_id and re.match(r"^[a-zA-Z][\w-]{2,40}$", raw_id):
            sid = _slugify(raw_id, sid)
        if sid in used_ids:
            sid = f"{sid}_{i + 1}"
        used_ids.add(sid)

        data = _as_dict(node.get("data"))
        campos_node = (
            node.get("campos")
            or node.get("fields")
            or data.get("campos")
            or data.get("fields")
            or []
        )
        if isinstance(campos_node, list):
            campos.extend(str(c) for c in campos_node if c)
        else:
            campos_node = []

        tools = node.get("tools") if isinstance(node.get("tools"), list) else _tools_for_node(node)
        if any(t.get("type") == "http_request" for t in tools if isinstance(t, dict)):
            integracoes.append(titulo)

        etapas.append(
            {
                "id": sid,
                "titulo": titulo,
                "obrigatoria": bool(node.get("obrigatoria", True)),
                "campos": campos_node if isinstance(campos_node, list) else [],
                "validacao": node.get("validacao") or {},
                "tools": tools,
                "hyperflow_type": ntype or None,
            }
        )

    return etapas, campos, integracoes


def _looks_like_json_syntax_title(titulo: str) -> bool:
    t = titulo.strip()
    if t in {"{", "}", "[", "]", ",", ":", "{", "}"}:
        return True
    if re.match(r'^"[^"]+"\s*:\s*\{?\s*$', t):
        return True
    if re.match(r'^"(width|height|position|selected|dragging)"', t):
        return True
    return False


def _heuristic_compile(source_text: str, filename: str) -> dict[str, Any]:
    """Fallback sem LLM: extrai nós HyperFlow / JSON estruturado."""
    try:
        data = json.loads(source_text)
    except json.JSONDecodeError:
        data = None

    etapas: list[dict] = []
    checklist: list[dict] = []
    campos: list[str] = []
    integracoes: list[str] = []
    observacoes = "Compilação heurística (LLM indisponível ou falhou)."

    if isinstance(data, dict):
        nodes = _dig_nodes(data)
        if nodes:
            etapas, campos, integracoes = _extract_etapas_from_nodes(nodes)
            observacoes = (
                "Compilação heurística a partir dos nós do arquivo (formato HyperFlow/JSON). "
                "Revise as etapas e publique quando estiver ok."
            )
        elif isinstance(data.get("roteiro"), dict) and isinstance(data["roteiro"].get("etapas"), list):
            # Já é um roteiro nosso
            etapas = [e for e in data["roteiro"]["etapas"] if isinstance(e, dict)]
            observacoes = "Arquivo já estava no formato de roteiro Harness."

    if not etapas and isinstance(data, list):
        etapas, campos, integracoes = _extract_etapas_from_nodes(data)

    # Texto puro com passos numerados — nunca use linhas de JSON
    if not etapas and data is None:
        lines = [ln.strip() for ln in source_text.splitlines() if ln.strip()]
        numbered = [ln for ln in lines if re.match(r"^\d+[\).\-\s]", ln)][:20]
        for i, ln in enumerate(numbered[:20]):
            sid = f"step_{i + 1}"
            titulo = re.sub(r"^\d+[\).\-\s]+", "", ln)[:120]
            if _looks_like_json_syntax_title(titulo):
                continue
            etapas.append(
                {
                    "id": sid,
                    "titulo": titulo,
                    "obrigatoria": True,
                    "campos": [],
                    "validacao": {},
                    "tools": [],
                }
            )

    # Filtra títulos lixo caso algo escape
    etapas = [e for e in etapas if not _looks_like_json_syntax_title(str(e.get("titulo") or ""))]

    if not etapas:
        etapas = [
            {
                "id": "revisar_fluxo",
                "titulo": "Revisar fluxo importado manualmente",
                "obrigatoria": True,
                "campos": [],
                "validacao": {},
                "tools": [],
            }
        ]
        observacoes = (
            "Não foi possível extrair etapas automaticamente do arquivo. "
            "Use o editor de etapas ou recompile com LLM disponível."
        )

    checklist = [{"id": e["id"], "titulo": e["titulo"]} for e in etapas]
    flow_title = filename.rsplit(".", 1)[0] if filename else "Flow importado"
    if isinstance(data, dict):
        for key in ("name", "title", "titulo"):
            val = data.get(key) or _as_dict(data.get("flow")).get(key)
            if isinstance(val, str) and val.strip():
                flow_title = val.strip()
                break

    return {
        "import_summary": {
            "titulo": flow_title,
            "etapas_resumo": [f"{i + 1}. {e['titulo']}" for i, e in enumerate(etapas)],
            "campos_detectados": list(dict.fromkeys(campos)),
            "integracoes_detectadas": list(dict.fromkeys(integracoes)),
            "handoff": any(
                "humano" in str(e["titulo"]).lower()
                or "transfer" in str(e["titulo"]).lower()
                or "encerrar" in str(e["titulo"]).lower()
                or "handoff" in str(e.get("hyperflow_type") or "").lower()
                for e in etapas
            ),
            "observacoes": observacoes,
        },
        "roteiro": {
            "objetivo": f"Executar o fluxo: {flow_title}",
            "etapas": [{k: v for k, v in e.items() if k != "hyperflow_type"} for e in etapas],
            "campos_obrigatorios": list(dict.fromkeys(campos)),
            "campos_opcionais": [],
            "ferramentas": list(
                dict.fromkeys(
                    ["save_field", "http_request", "send_file", "handoff"]
                    + [
                        t.get("type")
                        for e in etapas
                        for t in (e.get("tools") or [])
                        if isinstance(t, dict) and t.get("type")
                    ]
                )
            ),
            "encerramento": "Encerrar quando todas as etapas obrigatórias forem concluídas.",
            "handoff_quando": "Quando o cliente pedir atendente ou a etapa indicar transferência.",
        },
        "checklist": checklist,
        "base_prompt": (
            "Siga o roteiro obrigatório abaixo. Converse de forma natural, "
            "mas não pule etapas obrigatórias nem deixe de executar as ações indicadas."
        ),
        "source_raw": source_text,
        "source_filename": filename,
    }


def _normalize_compiled(result: dict[str, Any], source_text: str, filename: str) -> dict[str, Any]:
    roteiro = result.get("roteiro") if isinstance(result.get("roteiro"), dict) else {}
    checklist = result.get("checklist") if isinstance(result.get("checklist"), list) else []
    etapas = roteiro.get("etapas") if isinstance(roteiro.get("etapas"), list) else []

    # Se o LLM devolveu lixo (títulos JSON), cai no heurístico
    bad = [
        e
        for e in etapas
        if isinstance(e, dict) and _looks_like_json_syntax_title(str(e.get("titulo") or ""))
    ]
    if bad and len(bad) >= max(1, len(etapas) // 2):
        logger.warning("Compilação LLM com títulos inválidos; usando heurística HyperFlow")
        return _heuristic_compile(source_text, filename)

    if not checklist and etapas:
        checklist = [
            {"id": e.get("id"), "titulo": e.get("titulo") or e.get("id")}
            for e in etapas
            if isinstance(e, dict) and e.get("id")
        ]
    return {
        "import_summary": result.get("import_summary")
        if isinstance(result.get("import_summary"), dict)
        else {},
        "roteiro": roteiro,
        "checklist": checklist,
        "base_prompt": str(result.get("base_prompt") or ""),
        "source_raw": source_text,
        "source_filename": filename,
    }


def compile_flow_source(
    *,
    tenant_id: str,
    source_bytes: bytes,
    filename: str,
) -> dict[str, Any]:
    source_text = _decode_source(source_bytes, filename)
    if len(source_text) > 120_000:
        source_text = source_text[:120_000] + "\n…[truncado]"

    # Sempre tenta extrair nós estruturados primeiro (barato e confiável no HyperFlow)
    heuristic = _heuristic_compile(source_text, filename)
    heuristic_etapas = (heuristic.get("roteiro") or {}).get("etapas") or []
    has_real_nodes = bool(heuristic_etapas) and not all(
        e.get("id") == "revisar_fluxo" for e in heuristic_etapas if isinstance(e, dict)
    )

    tenant = get_tenant(tenant_id)
    llm = get_llm(tenant)
    if not llm:
        return heuristic

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _COMPILER_SYSTEM),
            (
                "human",
                "Arquivo: {filename}\n\n"
                "Nós já detectados (heurística — use como base, refine se necessário):\n"
                "{heuristic_summary}\n\n"
                "Conteúdo:\n```\n{content}\n```",
            ),
        ]
    )
    chain = prompt | llm | JsonOutputParser()
    try:
        result = chain.invoke(
            {
                "filename": filename,
                "content": source_text,
                "heuristic_summary": json.dumps(
                    heuristic.get("import_summary") or {}, ensure_ascii=False
                ),
            }
        )
        log_llm_usage(tenant, tenant.model.name, max(1, len(source_text) // 4), 800)
    except Exception as error:
        logger.warning("Falha ao compilar flow com LLM: %s", error)
        return heuristic

    if not isinstance(result, dict):
        return heuristic

    normalized = _normalize_compiled(result, source_text, filename)
    # Se LLM falhou em extrair e heurística tem nós reais, prefira heurística
    llm_etapas = (normalized.get("roteiro") or {}).get("etapas") or []
    if has_real_nodes and (
        not llm_etapas
        or all(_looks_like_json_syntax_title(str(e.get("titulo") or "")) for e in llm_etapas if isinstance(e, dict))
    ):
        return heuristic
    return normalized

import json
import logging
import os
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from agent.llm import get_llm, log_llm_usage
from context.policy import build_agent_context, format_flow_context_block
from harness.state import HarnessState
from harness_platform.contact_service import get_contact_by_phone, list_custom_fields, save_contact_fields
from harness_platform.db import SessionLocal
from harness_platform.flow_service import (
    apply_checklist_updates,
    get_or_create_flow_run,
    resolve_agent_and_flow,
)
from harness_platform.orchestrator_service import (
    ROLE_SPECIALIST,
    builtins_prompt_lines,
    get_agent_row,
    list_specialists,
    patch_sticky_fields,
    read_sticky_agent_id,
    route_with_orchestrator,
)
from harness_platform.agent_tool_service import (
    agent_tools_prompt_block,
    execute_agent_http_tool,
    get_agent_tool_by_slug,
    resolve_agent_tools_for_runtime,
)
from harness_platform.integration_service import (
    execute_http_tool,
    get_http_tool_by_slug,
    list_http_tools,
    tools_prompt_block,
)
from harness_platform.sendable_file_service import files_prompt_block, list_sendable_files
from knowledge.retrieve import format_knowledge_block, retrieve_knowledge_chunks
from handoff.policy import resolve_handoff
from memory.semantic import recall, store
from ops.lifecycle import Lifecycle, record_event
from tenants import get_tenant, load_prompt

logger = logging.getLogger(__name__)


def _record_ops(state: HarnessState, status: str, detail: str = "") -> None:
    try:
        record_event(
            delivery_id=str(state.get("delivery_id") or ""),
            message_id=str(state.get("message_id") or ""),
            conversation_id=int(state.get("conversation_id") or 0),
            status=status,
            detail=detail,
            tenant_id=str(state.get("tenant_id") or ""),
            account_id=state.get("account_id"),
            inbox_id=state.get("inbox_id"),
        )
    except Exception:
        logger.exception("Falha ao gravar ops event status=%s", status)


def _filter_files_by_refs(files: list[str], file_refs: set[str] | None, all_files: list[dict]) -> list[str]:
    if not files:
        return []
    if file_refs is None or "*" in (file_refs or set()):
        return files
    allowed_ids = {str(r) for r in file_refs}
    allowed_names: set[str] = set()
    for f in all_files:
        fid = str(f.get("id") or "")
        if fid in allowed_ids:
            if f.get("original_name"):
                allowed_names.add(str(f["original_name"]).lower())
            if f.get("filename"):
                allowed_names.add(str(f["filename"]).lower())
    out: list[str] = []
    for ref in files:
        r = str(ref).strip()
        if not r:
            continue
        if r in allowed_ids or r.lower() in allowed_names:
            out.append(r)
            continue
        # partial name match against allowlisted files only
        rl = r.lower()
        for f in all_files:
            fid = str(f.get("id") or "")
            if fid not in allowed_ids:
                continue
            on = str(f.get("original_name") or "").lower()
            fn = str(f.get("filename") or "").lower()
            if rl in on or rl in fn or on in rl or fn in rl:
                out.append(fid)
                break
    return out


def _crm_field_keys(tenant_id: str) -> set[str]:
    keys = {"nome", "name", "email", "phone", "telefone", "cpf", "plano"}
    db = SessionLocal()
    try:
        for cf in list_custom_fields(db, tenant_id):
            key = cf.get("key")
            if key:
                keys.add(str(key))
    except Exception:
        logger.exception("Falha ao listar custom fields tenant=%s", tenant_id)
    finally:
        db.close()
    return keys


def _infer_field_updates(inbound_text: str, reply: str, updates: dict) -> dict:
    """Completa field_updates quando a IA confirma o dado na reply mas esquece o JSON."""
    out = {str(k): v for k, v in (updates or {}).items() if v is not None and str(v).strip() != ""}
    text = (inbound_text or "").strip()
    reply_l = (reply or "").lower()
    digits = re.sub(r"\D", "", text)

    has_cpf_key = any(k.lower() == "cpf" for k in out)
    if not has_cpf_key and len(digits) == 11 and "cpf" in reply_l:
        if any(w in reply_l for w in ("anot", "registr", "salv", "recebi", "obrigad")):
            out["cpf"] = digits

    if not any(k.lower() in {"nome", "name"} for k in out):
        # "Me chamo X" / "meu nome é X"
        m = re.search(
            r"(?:me\s+chamo|meu\s+nome\s*[ée]\s*|sou\s+o?\s*|sou\s+a\s+)([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s]{1,60})",
            text,
            flags=re.IGNORECASE,
        )
        if m and any(w in reply_l for w in ("anot", "nome", "registr", "salv")):
            out["nome"] = m.group(1).strip()
    return out


def _filter_field_updates(updates: dict, *, allowed_keys: set[str], save_field_allowed: bool) -> dict:
    if not updates:
        return {}
    if save_field_allowed:
        return {str(k): v for k, v in updates.items() if v is not None and str(v).strip() != ""}
    # Sem tool save_field explícita: ainda persiste chaves de CRM do tenant
    return {
        str(k): v
        for k, v in updates.items()
        if str(k) in allowed_keys and v is not None and str(v).strip() != ""
    }

_DEFAULT_AGENT_PROMPT = (
    "Você é um assistente virtual de atendimento por mensagem. "
    "Responda em português do Brasil de forma natural e útil."
)
_AGENT_JSON_INSTRUCTIONS = (
    "\n\n---\n"
    "Formato de saída obrigatório: responda APENAS com JSON válido (sem markdown), "
    'com as chaves "intent" (string), "should_reply" (boolean), '
    '"reply" (string — mensagem enviada ao cliente), '
    '"new_facts" (array de strings), '
    '"field_updates" (objeto opcional: chave→valor para salvar no perfil do contato, '
    'ex.: {"cpf":"123","nome":"Maria","empreendimento":"Aurora"}), '
    '"http_tool_calls" (array opcional de slugs de APIs a executar agora), '
    '"files_to_send" (array opcional de nomes de arquivos da biblioteca para enviar), '
    '"checklist_updates" (objeto opcional: step_id → "completed"|"pending"|"skipped"), '
    '"handoff_to_human" (boolean, opcional), '
    '"transfer_to_agent" (objeto opcional: {"agent_id": N} ou {"name": "..."}), '
    '"return_to_orchestrator" (boolean, opcional — reclassifica no próximo turno). '
    "Não peça novamente dados que já existem no perfil persistente. "
    "Quando o cliente informar um dado de campo, salve em field_updates. "
    "Se o cliente pedir OUTRO setor, use transfer_to_agent com o id/nome da lista "
    "(o sistema troca o agente e ele atende neste mesmo turno — não diga 'aguarde o setor'). "
    "Nunca diga que vai transferir para o agente que você já é. "
    "Nunca diga 'um momento'/'aguarde' sem executar uma tool HTTP neste mesmo turno. "
    "Se não houver tool de abrir chamado/ticket, confirme o registro na reply, "
    "salve field_updates e faça a próxima pergunta útil ou encerre — não trave o atendimento. "
    "Se houver ROTEIRO OPERACIONAL, atualize o checklist ao concluir cada etapa."
)
_DEFAULT_FACTS_PROMPT = (
    'Extraia fatos duráveis sobre o usuário. Retorne JSON: {"facts": ["..."]}'
)
_DEFAULT_DISPATCH_PROMPT = (
    "Personalize a mensagem de disparo usando o template e variáveis. "
    "Mantenha tom natural, curto, sem markdown."
)


def _tenant_from_state(state: HarnessState):
    return get_tenant(state.get("tenant_id", "default"))


def load_semantic_memory(state: HarnessState) -> HarnessState:
    tenant = _tenant_from_state(state)
    facts = recall(tenant.id, state["phone"])
    profile: dict = {}
    agent_id = None
    flow_id = None
    flow_run_id = None
    agent_prompt = ""
    flow_roteiro: dict = {}
    flow_checklist: list = []
    flow_checklist_state: dict = {}
    flow_base_prompt = ""
    allowed_tools: dict = {}

    db = SessionLocal()
    try:
        profile = get_contact_by_phone(db, tenant.id, state["phone"]) or {}
        if not profile and state.get("chatwoot_contact_id"):
            from harness_platform.contact_service import get_contact_by_chatwoot_id

            profile = get_contact_by_chatwoot_id(db, tenant.id, int(state["chatwoot_contact_id"])) or {}
        if not profile and (state.get("contact_name") or state.get("phone") or state.get("chatwoot_contact_id")):
            from harness_platform.contact_service import upsert_contact

            try:
                profile = upsert_contact(
                    db,
                    tenant.id,
                    state["phone"],
                    name=state.get("contact_name") or "",
                    chatwoot_contact_id=state.get("chatwoot_contact_id"),
                    last_conversation_id=state.get("conversation_id"),
                )
            except ValueError:
                profile = {}
        elif profile and (state.get("conversation_id") or state.get("contact_name")):
            from harness_platform.contact_service import upsert_contact

            try:
                profile = upsert_contact(
                    db,
                    tenant.id,
                    state["phone"] or profile.get("phone") or "",
                    name=state.get("contact_name") or None,
                    chatwoot_contact_id=state.get("chatwoot_contact_id"),
                    last_conversation_id=state.get("conversation_id"),
                )
            except ValueError:
                pass

        conversation_id = state.get("conversation_id")
        resolved_agent_id: int | None = None
        resolution_source = ""

        # 1) Override explícito (dispatch/webhook)
        if state.get("override_agent_id") or state.get("override_flow_id"):
            agent, flow = resolve_agent_and_flow(
                db,
                tenant.id,
                agent_id=state.get("override_agent_id"),
                flow_id=state.get("override_flow_id"),
            )
            if agent:
                resolved_agent_id = agent.id
                resolution_source = "override"
        else:
            prefs = (profile or {}).get("fields") or {}
            # 2) Preferência legada
            pref_flow = prefs.get("_preferred_flow_id")
            pref_agent = prefs.get("_preferred_agent_id")
            sticky_id = read_sticky_agent_id(profile, conversation_id)

            if sticky_id:
                sticky_row = get_agent_row(db, tenant.id, sticky_id)
                if (
                    sticky_row
                    and sticky_row.active
                    and getattr(sticky_row, "role", ROLE_SPECIALIST) == ROLE_SPECIALIST
                ):
                    resolved_agent_id = sticky_row.id
                    resolution_source = "sticky"
                else:
                    sticky_id = None

            if resolved_agent_id is None and (pref_flow or pref_agent):
                agent, flow = resolve_agent_and_flow(
                    db,
                    tenant.id,
                    agent_id=int(pref_agent) if pref_agent else None,
                    flow_id=int(pref_flow) if pref_flow else None,
                )
                if agent:
                    resolved_agent_id = agent.id
                    resolution_source = "preferencia"

            # 3) Orquestrador no início (sem sticky)
            if resolved_agent_id is None:
                chosen = route_with_orchestrator(
                    db,
                    tenant.id,
                    inbound_text=state.get("inbound_text") or "",
                    specialists=list_specialists(db, tenant.id),
                )
                if chosen:
                    resolved_agent_id = chosen.id
                    resolution_source = "orquestrador"
                    profile = patch_sticky_fields(
                        db,
                        tenant.id,
                        state["phone"],
                        agent_id=chosen.id,
                        conversation_id=int(conversation_id) if conversation_id else None,
                    ) or profile

            # Grava sticky se veio de override/preferência sem sticky
            if resolved_agent_id and not sticky_id and not state.get("override_agent_id"):
                # já gravado no orquestrador; se veio de preferência, sticky também
                if pref_agent or pref_flow:
                    profile = patch_sticky_fields(
                        db,
                        tenant.id,
                        state["phone"],
                        agent_id=resolved_agent_id,
                        conversation_id=int(conversation_id) if conversation_id else None,
                    ) or profile

        agent, flow = resolve_agent_and_flow(
            db,
            tenant.id,
            agent_id=resolved_agent_id,
            flow_id=state.get("override_flow_id"),
        )
        if agent and state.get("override_agent_id"):
            profile = patch_sticky_fields(
                db,
                tenant.id,
                state["phone"],
                agent_id=agent.id,
                conversation_id=int(conversation_id) if conversation_id else None,
            ) or profile

        if agent:
            agent_id = agent.id
            identity = (
                f"\n\n[IDENTIDADE DO TURNO]\n"
                f'Você é o agente "{agent.name}" (id={agent.id}). '
                "Você JÁ está atendendo este cliente agora — aja neste papel. "
                "Não diga que vai transferir para o seu próprio setor nem peça para "
                "aguardar você mesmo. Atenda direto conforme suas instruções."
            )
            agent_prompt = (agent.system_prompt or "") + identity
            allowed_tools = resolve_agent_tools_for_runtime(db, tenant.id, agent.id)
            source_label = {
                "orquestrador": "orquestrador",
                "sticky": "conversa (sticky)",
                "preferencia": "preferência",
                "override": "override",
            }.get(resolution_source, resolution_source or "padrão")
            _record_ops(
                state,
                Lifecycle.AGENT_SELECTED,
                f"{agent.name} (#{agent.id}) via {source_label}",
            )
        if flow and state.get("conversation_id"):
            flow_id = flow.id
            flow_roteiro = flow.roteiro or {}
            flow_checklist = flow.checklist or []
            flow_base_prompt = flow.base_prompt or ""
            run = get_or_create_flow_run(
                db,
                tenant.id,
                flow,
                conversation_id=int(state["conversation_id"]),
                phone=state.get("phone") or "",
            )
            flow_run_id = run.id
            flow_checklist_state = run.checklist_state or {}
            if not flow_checklist and isinstance(flow_roteiro, dict):
                flow_checklist = [
                    {"id": e.get("id"), "titulo": e.get("titulo") or e.get("id")}
                    for e in (flow_roteiro.get("etapas") or [])
                    if isinstance(e, dict) and e.get("id")
                ]
    finally:
        db.close()

    return {
        **state,
        "semantic_facts": facts,
        "contact_profile": profile or {},
        "agent_id": agent_id,
        "flow_id": flow_id,
        "flow_run_id": flow_run_id,
        "agent_system_prompt": agent_prompt,
        "flow_roteiro": flow_roteiro,
        "flow_checklist": flow_checklist,
        "flow_checklist_state": flow_checklist_state,
        "flow_base_prompt": flow_base_prompt,
        "allowed_tools": allowed_tools or {},
        "transfer_to_agent": None,
        "return_to_orchestrator": False,
    }


def manage_context(state: HarnessState) -> HarnessState:
    from context.policy import should_summarize, summarize_messages, trim_messages

    tenant = _tenant_from_state(state)
    messages = state.get("messages", [])
    summary = state.get("conversation_summary", "")

    if should_summarize(messages, tenant):
        summary = summarize_messages(messages, summary, tenant)
        messages = trim_messages(messages, tenant)

    custom_fields: list[dict] = []
    http_block = ""
    files_block = ""
    tools_extra = ""
    allowed = state.get("allowed_tools") or {}
    db = SessionLocal()
    try:
        custom_fields = list_custom_fields(db, tenant.id)

        if allowed.get("from_defined"):
            tools_extra = agent_tools_prompt_block(allowed.get("tools") or [])
            defined_kinds = {t.get("kind") for t in (allowed.get("tools") or [])}
            if "save_field" in (allowed.get("builtins") or set()) and "save_field" not in defined_kinds:
                tools_extra += (
                    "\n\n### Salvar campo [save_field]\n"
                    "Regras: sempre que o cliente informar nome, cpf, email, plano ou outro campo do perfil, "
                    "inclua em field_updates neste mesmo turno.\n"
                    "Ação: preencha field_updates com os dados coletados."
                )
            if "transfer_agent" in (allowed.get("builtins") or set()):
                specs = list_specialists(db, tenant.id)
                if specs:
                    tools_extra += "\n\nAgentes para transfer_to_agent:\n" + "\n".join(
                        f"- id={a.id} name={a.name}" + (" (padrão)" if a.is_default else "")
                        for a in specs
                        if a.id != state.get("agent_id")
                    )
            if "send_file" in (allowed.get("builtins") or set()):
                all_files = list_sendable_files(db, tenant.id)
                file_refs = allowed.get("file_refs")
                if file_refs is None or "*" in (file_refs or set()):
                    filtered_files = all_files
                else:
                    filtered_files = [
                        f
                        for f in all_files
                        if str(f.get("id")) in file_refs
                        or str(f.get("original_name") or "") in file_refs
                        or str(f.get("filename") or "") in file_refs
                    ]
                files_block = files_prompt_block(filtered_files)
            http_block = ""
        else:
            all_http = list_http_tools(db, tenant.id, active_only=True)
            http_slugs = allowed.get("http_slugs")
            if http_slugs is None:
                filtered_http = all_http
            else:
                filtered_http = [t for t in all_http if t.get("slug") in http_slugs]
            http_block = tools_prompt_block(filtered_http)

            all_files = list_sendable_files(db, tenant.id)
            file_refs = allowed.get("file_refs")
            if file_refs is None or "*" in (file_refs or set()):
                filtered_files = all_files
            else:
                filtered_files = [
                    f
                    for f in all_files
                    if str(f.get("id")) in file_refs
                    or str(f.get("original_name") or "") in file_refs
                    or str(f.get("filename") or "") in file_refs
                ]
            if "send_file" in (allowed.get("builtins") or set()) or file_refs is None:
                files_block = files_prompt_block(filtered_files)
            else:
                files_block = ""

            builtins_block = builtins_prompt_lines(allowed)
            if "transfer_agent" in (allowed.get("builtins") or set()):
                specs = list_specialists(db, tenant.id)
                if specs:
                    builtins_block += "\nAgentes para transfer_to_agent:\n" + "\n".join(
                        f"- id={a.id} name={a.name}" + (" (padrão)" if a.is_default else "")
                        for a in specs
                        if a.id != state.get("agent_id")
                    )
            if builtins_block:
                tools_extra = f"\n\nFerramentas permitidas neste agente:\n{builtins_block}"
    finally:
        db.close()

    flow_block = format_flow_context_block(
        roteiro=state.get("flow_roteiro") or {},
        checklist=state.get("flow_checklist") or [],
        checklist_state=state.get("flow_checklist_state") or {},
        base_prompt=state.get("flow_base_prompt") or "",
    )

    return {
        **state,
        "messages": messages,
        "conversation_summary": summary,
        "agent_context": build_agent_context(
            inbound_text=state["inbound_text"],
            contact_name=state.get("contact_name", ""),
            conversation_summary=summary,
            semantic_facts=state.get("semantic_facts", []),
            recent_messages=messages,
            tenant=tenant,
            contact_profile=state.get("contact_profile") or {},
            custom_fields=custom_fields,
            http_tools_block=(http_block + ("\n\n" + tools_extra if tools_extra else "")).strip(),
            files_block=files_block,
            flow_block=flow_block,
        ),
    }


def ingest_message(state: HarnessState) -> HarnessState:
    return {
        **state,
        "messages": [HumanMessage(content=state["inbound_text"])],
    }


def retrieve_knowledge(state: HarnessState) -> HarnessState:
    tenant = _tenant_from_state(state)
    chunks = retrieve_knowledge_chunks(tenant, state["inbound_text"])
    knowledge_block = format_knowledge_block(chunks)
    base_context = state.get("agent_context", "")
    agent_context = f"{base_context}\n\n{knowledge_block}" if base_context else knowledge_block

    return {
        **state,
        "retrieved_knowledge": [chunk["text"] for chunk in chunks],
        "agent_context": agent_context,
    }


def run_agent(state: HarnessState) -> HarnessState:
    tenant = _tenant_from_state(state)
    llm = get_llm(tenant)
    text = state["inbound_text"]
    persona_prompt = (
        (state.get("agent_system_prompt") or "").strip()
        or load_prompt(tenant, "agent_system", _DEFAULT_AGENT_PROMPT)
    )
    # Instruções JSON vão no SystemMessage direto (sem ChatPromptTemplate),
    # senão chaves {cpf}/{agent_id}/… quebram o template do LangChain.
    system_prompt = persona_prompt + _AGENT_JSON_INSTRUCTIONS

    if not llm:
        logger.error("LLM indisponível para tenant=%s", tenant.id)
        handoff, reason = resolve_handoff(
            inbound_text=text,
            retrieved_knowledge=state.get("retrieved_knowledge", []),
            tenant=tenant,
            llm_handoff=False,
        )
        return {
            **state,
            "intent": "other",
            "should_reply": True,
            "outbound_text": (
                "No momento não consigo processar com IA. "
                "Verifique o provedor LLM no painel ou OPENAI_API_KEY no servidor."
            ),
            "handoff_to_human": handoff,
            "handoff_reason": reason or "llm_unavailable",
            "new_semantic_facts": [],
        }

    context_text = state.get("agent_context", text)
    model_ref = tenant.model.name
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=context_text),
    ]
    parser = JsonOutputParser()
    try:
        raw = llm.invoke(messages)
        result = parser.invoke(raw)
        if not isinstance(result, dict):
            raise ValueError(f"Resposta do agente não é objeto JSON: {type(result)}")
        reply_text = str(result.get("reply") or "")
        log_llm_usage(
            tenant,
            model_ref,
            max(1, len(context_text) // 4),
            max(1, len(reply_text) // 4),
        )
    except Exception as error:
        logger.warning(
            "Falha ao parsear JSON do agente tenant=%s: %s",
            tenant.id,
            error,
        )
        try:
            raw = llm.invoke(messages)
            content = str(getattr(raw, "content", raw)).strip()
            result = {
                "intent": "other",
                "should_reply": bool(content),
                "reply": content,
                "handoff_to_human": False,
                "new_facts": [],
            }
            if content:
                log_llm_usage(
                    tenant,
                    model_ref,
                    max(1, len(context_text) // 4),
                    max(1, len(content) // 4),
                )
        except Exception as inner:
            logger.exception("Falha na chamada LLM tenant=%s", tenant.id)
            result = {
                "intent": "other",
                "should_reply": True,
                "reply": "Desculpe, tive um problema ao processar sua mensagem. Pode tentar de novo?",
                "handoff_to_human": False,
                "new_facts": [],
                "handoff_reason": str(inner),
            }

    llm_handoff = bool(result.get("handoff_to_human", False))
    reply = str(result.get("reply") or "")
    allowed = state.get("allowed_tools") or {}
    builtins = allowed.get("builtins") or set()
    from_defined = bool(allowed.get("from_defined"))
    has_allowlist = from_defined or (bool(allowed) and "builtins" in allowed)
    if has_allowlist and "handoff" not in builtins:
        llm_handoff = False

    handoff, reason = resolve_handoff(
        inbound_text=text,
        retrieved_knowledge=state.get("retrieved_knowledge", []),
        tenant=tenant,
        llm_handoff=llm_handoff,
        bot_reply=reply,
    )
    if has_allowlist and "handoff" not in builtins:
        handoff = False

    field_updates = result.get("field_updates") if isinstance(result.get("field_updates"), dict) else {}
    field_updates = _infer_field_updates(text, reply, field_updates)
    crm_keys = _crm_field_keys(tenant.id)
    field_updates = _filter_field_updates(
        field_updates,
        allowed_keys=crm_keys,
        save_field_allowed=not has_allowlist or "save_field" in builtins,
    )

    http_calls = [str(s) for s in (result.get("http_tool_calls") or []) if s]
    if from_defined:
        allowed_http = set((allowed.get("http_by_slug") or {}).keys())
        http_calls = [s for s in http_calls if s in allowed_http]
    else:
        http_slugs = allowed.get("http_slugs")
        if http_slugs is not None:
            http_calls = [s for s in http_calls if s in http_slugs]

    files = [str(s) for s in (result.get("files_to_send") or []) if s]
    if has_allowlist and "send_file" not in builtins:
        files = []
    elif files and (allowed.get("file_refs") is not None):
        db_files = SessionLocal()
        try:
            all_files = list_sendable_files(db_files, tenant.id)
        finally:
            db_files.close()
        files = _filter_files_by_refs(files, allowed.get("file_refs"), all_files)

    checklist_updates = (
        result.get("checklist_updates") if isinstance(result.get("checklist_updates"), dict) else {}
    )
    new_facts = [str(f) for f in result.get("new_facts", []) if f]

    transfer_payload = result.get("transfer_to_agent")
    return_orch = bool(result.get("return_to_orchestrator", False))
    if has_allowlist and "transfer_agent" not in builtins:
        transfer_payload = None
        return_orch = False

    base = {
        **state,
        "intent": str(result.get("intent", "other")),
        "new_semantic_facts": new_facts,
        "field_updates": field_updates,
        "http_tool_calls": http_calls,
        "files_to_send": files,
        "checklist_updates": checklist_updates,
        "transfer_to_agent": transfer_payload,
        "return_to_orchestrator": return_orch,
    }

    if handoff:
        return {
            **base,
            "should_reply": False,
            "outbound_text": "",
            "handoff_to_human": True,
            "handoff_reason": reason,
        }

    return {
        **base,
        "should_reply": bool(result.get("should_reply", True)),
        "outbound_text": str(result.get("reply") or ""),
        "handoff_to_human": handoff,
        "handoff_reason": reason,
    }


def persist_contact_and_tools(state: HarnessState) -> HarnessState:
    """Salva field_updates, dispara HTTP tools, sticky transfer e checklist do Flow."""
    tenant = _tenant_from_state(state)
    profile = state.get("contact_profile") or {}
    updates = state.get("field_updates") or {}
    checklist_state = dict(state.get("flow_checklist_state") or {})
    transfer_rerun = False
    switched_agent_id = state.get("agent_id")
    switched_prompt = state.get("agent_system_prompt") or ""
    switched_tools = state.get("allowed_tools") or {}
    transfer_depth = int(state.get("transfer_depth") or 0)
    db = SessionLocal()
    try:
        if updates:
            keys = ", ".join(sorted(str(k) for k in updates.keys()))
            try:
                phone_key = state.get("phone") or (profile.get("phone") if profile else "") or ""
                saved = save_contact_fields(
                    db,
                    tenant.id,
                    phone_key,
                    dict(updates),
                    chatwoot_contact_id=state.get("chatwoot_contact_id"),
                    last_conversation_id=state.get("conversation_id"),
                )
                if saved:
                    profile = saved
                _record_ops(state, Lifecycle.TOOL_EXECUTED, f"Salvar campos: {keys}")
            except ValueError as err:
                # Sem telefone no webhook: não derruba o turno inteiro
                _record_ops(state, Lifecycle.FAILED, f"Salvar campos ({keys}): {err}")

        # Transferência entre agentes / volta ao orquestrador
        conv_id = state.get("conversation_id")
        if state.get("return_to_orchestrator"):
            profile = (
                patch_sticky_fields(
                    db,
                    tenant.id,
                    state["phone"],
                    agent_id=None,
                    conversation_id=int(conv_id) if conv_id else None,
                    clear=True,
                )
                or profile
            )
            _record_ops(state, Lifecycle.TOOL_EXECUTED, "Volta ao orquestrador")
        else:
            transfer = state.get("transfer_to_agent")
            target_id = None
            if isinstance(transfer, dict):
                if transfer.get("agent_id") is not None:
                    try:
                        target_id = int(transfer["agent_id"])
                    except (TypeError, ValueError):
                        target_id = None
                elif transfer.get("name"):
                    name = str(transfer["name"]).strip().lower()
                    for spec in list_specialists(db, tenant.id):
                        if spec.name.lower() == name or name in spec.name.lower():
                            target_id = spec.id
                            break
            elif isinstance(transfer, (int, str)) and str(transfer).strip():
                try:
                    target_id = int(transfer)
                except (TypeError, ValueError):
                    name = str(transfer).strip().lower()
                    for spec in list_specialists(db, tenant.id):
                        if spec.name.lower() == name or name in spec.name.lower():
                            target_id = spec.id
                            break
            if target_id and target_id != state.get("agent_id"):
                row = get_agent_row(db, tenant.id, target_id)
                if row and row.active and getattr(row, "role", ROLE_SPECIALIST) == ROLE_SPECIALIST:
                    profile = (
                        patch_sticky_fields(
                            db,
                            tenant.id,
                            state["phone"],
                            agent_id=row.id,
                            conversation_id=int(conv_id) if conv_id else None,
                        )
                        or profile
                    )
                    _record_ops(
                        state,
                        Lifecycle.TOOL_EXECUTED,
                        f"Transferir agente → {row.name} (#{row.id})",
                    )
                    _record_ops(
                        state,
                        Lifecycle.AGENT_SELECTED,
                        f"{row.name} (#{row.id}) via transferência",
                    )
                    # Reexecuta o turno com o agente destino (não envia "aguarde o SAC")
                    if transfer_depth < 2:
                        identity = (
                            f"\n\n[IDENTIDADE DO TURNO]\n"
                            f'Você é o agente "{row.name}" (id={row.id}). '
                            "Você JÁ está atendendo este cliente agora — aja neste papel. "
                            "Não diga que vai transferir para o seu próprio setor nem peça para "
                            "aguardar você mesmo. Atenda direto conforme suas instruções."
                        )
                        switched_agent_id = row.id
                        switched_prompt = (row.system_prompt or "") + identity
                        switched_tools = resolve_agent_tools_for_runtime(db, tenant.id, row.id)
                        transfer_rerun = True
                        transfer_depth += 1

        tools_entries = []
        agent_id = state.get("agent_id")
        for slug in state.get("http_tool_calls") or []:
            result = None
            agent_tool = None
            if agent_id:
                agent_tool = get_agent_tool_by_slug(db, tenant.id, int(agent_id), slug)
            import asyncio

            async def _run(coro):
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures

                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                            return pool.submit(asyncio.run, coro).result(timeout=35)
                    return loop.run_until_complete(coro)
                except RuntimeError:
                    return asyncio.run(coro)

            if agent_tool and agent_tool.kind == "http":
                try:
                    result = _run(execute_agent_http_tool(agent_tool, profile))
                except Exception as error:
                    logger.warning("Agent HTTP tool %s falhou: %s", slug, error)
                    result = {"ok": False, "error": str(error), "slug": slug}
                tools_entries.append({"type": "agent_http", "slug": slug, "result": result})
            else:
                tool = get_http_tool_by_slug(db, tenant.id, slug)
                if not tool:
                    logger.warning("HTTP tool slug=%s não encontrada tenant=%s", slug, tenant.id)
                    continue
                try:
                    result = _run(execute_http_tool(tool, profile))
                except Exception as error:
                    result = {"ok": False, "error": str(error), "slug": slug}
                tools_entries.append({"type": "http_request", "slug": slug, "result": result})
            if result and not result.get("ok"):
                logger.warning("HTTP tool %s falhou: %s", slug, result)
            status = "ok" if result and result.get("ok") else f"erro: {result.get('error') if result else 'falha'}"
            _record_ops(state, Lifecycle.TOOL_EXECUTED, f"HTTP '{slug}': {status}")

        run_id = state.get("flow_run_id")
        checklist_updates = state.get("checklist_updates") or {}
        if run_id and (checklist_updates or updates or tools_entries):
            from harness_platform.models import FlowRun

            run = db.query(FlowRun).filter(FlowRun.id == run_id).first()
            if run:
                inferred = dict(checklist_updates)
                roteiro = state.get("flow_roteiro") or {}
                fields = (profile.get("fields") or {}) if isinstance(profile, dict) else {}
                for etapa in roteiro.get("etapas") or []:
                    if not isinstance(etapa, dict):
                        continue
                    campos = etapa.get("campos") or []
                    sid = str(etapa.get("id") or "")
                    if not sid or not campos:
                        continue
                    ok = True
                    for c in campos:
                        if c in {"nome", "name"}:
                            ok = ok and bool(profile.get("name") or fields.get(c))
                        elif c == "email":
                            ok = ok and bool(profile.get("email") or fields.get(c))
                        elif c in {"phone", "telefone"}:
                            ok = ok and bool(profile.get("phone") or fields.get(c))
                        else:
                            ok = ok and bool(fields.get(c) or updates.get(c))
                    if ok and inferred.get(sid) != "skipped":
                        inferred[sid] = "completed"
                current = ""
                merged_state = {**checklist_state, **inferred}
                for etapa in roteiro.get("etapas") or []:
                    if not isinstance(etapa, dict):
                        continue
                    sid = str(etapa.get("id") or "")
                    if merged_state.get(sid, "pending") == "pending":
                        current = sid
                        break
                run = apply_checklist_updates(
                    db,
                    run,
                    inferred,
                    variables=updates or None,
                    tools_log_entry={"http": tools_entries} if tools_entries else None,
                    current_step_id=current,
                )
                checklist_state = run.checklist_state or checklist_state
    finally:
        db.close()

    out = {
        **state,
        "contact_profile": profile,
        "flow_checklist_state": checklist_state,
        "transfer_to_agent": None,
        "transfer_rerun": transfer_rerun,
        "transfer_depth": transfer_depth,
        "agent_id": switched_agent_id,
        "agent_system_prompt": switched_prompt,
        "allowed_tools": switched_tools,
    }
    if transfer_rerun:
        # Descarta a reply do agente origem; o destino responde neste turno
        out["should_reply"] = False
        out["outbound_text"] = ""
        out["files_to_send"] = []
        out["http_tool_calls"] = []
        out["field_updates"] = {}
    return out


def persist_semantic_memory(state: HarnessState) -> HarnessState:
    tenant = _tenant_from_state(state)
    facts = state.get("new_semantic_facts", [])
    if not facts and state.get("outbound_text"):
        llm = get_llm(tenant)
        if llm:
            facts_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", load_prompt(tenant, "facts_system", _DEFAULT_FACTS_PROMPT)),
                    ("human", "Mensagem: {text}\nResposta: {reply}"),
                ]
            )
            chain = facts_prompt | llm | JsonOutputParser()
            try:
                extracted = chain.invoke(
                    {"text": state["inbound_text"], "reply": state["outbound_text"]}
                )
                facts = [str(f) for f in extracted.get("facts", []) if f]
            except Exception:
                facts = []

    if facts:
        store(tenant.id, state["phone"], facts)
        merged = list(dict.fromkeys(state.get("semantic_facts", []) + facts))
        return {**state, "semantic_facts": merged, "new_semantic_facts": facts}

    return state


def generate_dispatch_message(
    template: str,
    variables: dict,
    tenant_id: str | None = None,
) -> str:
    from harness_platform.template_vars import render_template

    tenant = get_tenant(tenant_id or os.getenv("TENANT_ID", "default"))
    rendered = render_template(template, variables)
    llm = get_llm(tenant)
    if not llm:
        return rendered or template

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", load_prompt(tenant, "dispatch_system", _DEFAULT_DISPATCH_PROMPT)),
            ("human", "Template:\n{template}\n\nVariáveis:\n{variables}"),
        ]
    )
    chain = prompt | llm
    return str(
        chain.invoke(
            {"template": rendered or template, "variables": json.dumps(variables, ensure_ascii=False)}
        ).content
    )

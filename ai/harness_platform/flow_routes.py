"""Rotas Agents / Flows / Runs — montadas no admin e no portal."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from harness_platform.db import get_db
from harness_platform.flow_compiler import compile_flow_source
from harness_platform.flow_service import (
    create_agent,
    create_flow,
    delete_agent,
    delete_flow,
    get_agent,
    get_flow,
    get_flow_run,
    list_agents,
    list_flow_runs,
    list_flows,
    publish_flow,
    update_agent,
    update_flow,
)
from harness_platform.agent_tool_service import (
    create_agent_tool,
    delete_agent_tool,
    get_agent_tool,
    list_agent_tools,
    update_agent_tool,
)
from harness_platform.orchestrator_service import (
    ensure_orchestrator,
    list_agent_tool_bindings,
    set_agent_tool_bindings,
)
from harness_platform.schemas import (
    AgentCreate,
    AgentToolBindingsUpdate,
    AgentToolCreate,
    AgentToolUpdate,
    AgentUpdate,
    FlowCreate,
    FlowUpdate,
)


def build_flow_routes(*, get_tenant_id, prefix: str = "") -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["flows"])

    # --- Agents ---

    @router.get("/agents")
    def api_list_agents(
        role: str | None = None,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        return {"agents": list_agents(db, tenant_id, role=role)}

    @router.get("/orchestrator")
    def api_get_orchestrator(
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        row = ensure_orchestrator(db, tenant_id)
        from harness_platform.flow_service import agent_to_dict

        return agent_to_dict(row)

    @router.put("/orchestrator")
    def api_update_orchestrator(
        body: AgentUpdate,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        row = ensure_orchestrator(db, tenant_id)
        try:
            return update_agent(db, tenant_id, row.id, body.model_dump(exclude_unset=True))
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.post("/agents", status_code=status.HTTP_201_CREATED)
    def api_create_agent(
        body: AgentCreate,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            return create_agent(db, tenant_id, body.model_dump())
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get("/agents/{agent_id}")
    def api_get_agent(
        agent_id: int,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        agent = get_agent(db, tenant_id, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agente não encontrado")
        return agent

    @router.put("/agents/{agent_id}")
    def api_update_agent(
        agent_id: int,
        body: AgentUpdate,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            return update_agent(db, tenant_id, agent_id, body.model_dump(exclude_unset=True))
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
    def api_delete_agent(
        agent_id: int,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            delete_agent(db, tenant_id, agent_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get("/agents/{agent_id}/tools")
    def api_list_agent_tools(
        agent_id: int,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        if not get_agent(db, tenant_id, agent_id):
            raise HTTPException(status_code=404, detail="Agente não encontrado")
        return {"bindings": list_agent_tool_bindings(db, tenant_id, agent_id)}

    @router.put("/agents/{agent_id}/tools")
    def api_set_agent_tools(
        agent_id: int,
        body: AgentToolBindingsUpdate,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            bindings = set_agent_tool_bindings(
                db,
                tenant_id,
                agent_id,
                [b.model_dump() for b in body.bindings],
            )
            return {"bindings": bindings}
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    # --- Agent tools (editáveis: regras + endpoint) ---

    @router.get("/tools")
    def api_list_tools(
        agent_id: int | None = None,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        return {"tools": list_agent_tools(db, tenant_id, agent_id=agent_id)}

    @router.post("/tools", status_code=status.HTTP_201_CREATED)
    def api_create_tool(
        body: AgentToolCreate,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            return create_agent_tool(db, tenant_id, body.model_dump())
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get("/tools/{tool_id}")
    def api_get_tool(
        tool_id: int,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        tool = get_agent_tool(db, tenant_id, tool_id)
        if not tool:
            raise HTTPException(status_code=404, detail="Tool não encontrada")
        return tool

    @router.put("/tools/{tool_id}")
    def api_update_tool(
        tool_id: int,
        body: AgentToolUpdate,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            return update_agent_tool(db, tenant_id, tool_id, body.model_dump(exclude_unset=True))
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.delete("/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
    def api_delete_tool(
        tool_id: int,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            delete_agent_tool(db, tenant_id, tool_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    # --- Flows ---

    @router.get("/flows")
    def api_list_flows(
        agent_id: int | None = None,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        return {"flows": list_flows(db, tenant_id, agent_id=agent_id)}

    @router.post("/flows", status_code=status.HTTP_201_CREATED)
    def api_create_flow(
        body: FlowCreate,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            return create_flow(db, tenant_id, body.model_dump())
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get("/flows/{flow_id}")
    def api_get_flow(
        flow_id: int,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        flow = get_flow(db, tenant_id, flow_id, include_source=True)
        if not flow:
            raise HTTPException(status_code=404, detail="Flow não encontrado")
        return flow

    @router.put("/flows/{flow_id}")
    def api_update_flow(
        flow_id: int,
        body: FlowUpdate,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            return update_flow(db, tenant_id, flow_id, body.model_dump(exclude_unset=True))
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.post("/flows/{flow_id}/publish")
    def api_publish_flow(
        flow_id: int,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            return publish_flow(db, tenant_id, flow_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.delete("/flows/{flow_id}", status_code=status.HTTP_204_NO_CONTENT)
    def api_delete_flow(
        flow_id: int,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            delete_flow(db, tenant_id, flow_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.post("/flows/import", status_code=status.HTTP_201_CREATED)
    async def api_import_flow(
        file: UploadFile = File(...),
        agent_id: int | None = Form(None),
        name: str = Form(""),
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        filename = file.filename or "flow.json"
        lower = filename.lower()
        if not (lower.endswith(".flow") or lower.endswith(".json") or lower.endswith(".txt")):
            raise HTTPException(status_code=400, detail="Use arquivo .flow, .json ou .txt")
        content = await file.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Arquivo excede 5MB")
        try:
            compiled = compile_flow_source(
                tenant_id=tenant_id, source_bytes=content, filename=filename
            )
            flow_name = (name or "").strip() or (
                (compiled.get("import_summary") or {}).get("titulo")
                or filename.rsplit(".", 1)[0]
            )
            return create_flow(
                db,
                tenant_id,
                {
                    "name": flow_name,
                    "agent_id": agent_id,
                    "description": "Importado de " + filename,
                    "base_prompt": compiled.get("base_prompt") or "",
                    "status": "draft",
                    "source_filename": compiled.get("source_filename") or filename,
                    "source_raw": compiled.get("source_raw") or "",
                    "import_summary": compiled.get("import_summary") or {},
                    "roteiro": compiled.get("roteiro") or {},
                    "checklist": compiled.get("checklist") or [],
                },
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.post("/flows/{flow_id}/recompile")
    def api_recompile_flow(
        flow_id: int,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        flow = get_flow(db, tenant_id, flow_id, include_source=True)
        if not flow:
            raise HTTPException(status_code=404, detail="Flow não encontrado")
        raw = (flow.get("source_raw") or "").encode("utf-8")
        if not raw.strip():
            raise HTTPException(status_code=400, detail="Flow sem source_raw para recompilar")
        compiled = compile_flow_source(
            tenant_id=tenant_id,
            source_bytes=raw,
            filename=flow.get("source_filename") or "flow.json",
        )
        try:
            return update_flow(
                db,
                tenant_id,
                flow_id,
                {
                    "base_prompt": compiled.get("base_prompt") or flow.get("base_prompt"),
                    "import_summary": compiled.get("import_summary") or {},
                    "roteiro": compiled.get("roteiro") or {},
                    "checklist": compiled.get("checklist") or [],
                },
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    # --- Runs ---

    @router.get("/flow-runs")
    def api_list_runs(
        flow_id: int | None = None,
        limit: int = 50,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        return {"runs": list_flow_runs(db, tenant_id, flow_id=flow_id, limit=limit)}

    @router.get("/flow-runs/{run_id}")
    def api_get_run(
        run_id: int,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        run = get_flow_run(db, tenant_id, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run não encontrado")
        return run

    @router.get("/flows/{flow_id}/runs")
    def api_list_flow_runs_nested(
        flow_id: int,
        limit: int = 50,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        if not get_flow(db, tenant_id, flow_id):
            raise HTTPException(status_code=404, detail="Flow não encontrado")
        return {"runs": list_flow_runs(db, tenant_id, flow_id=flow_id, limit=limit)}

    return router

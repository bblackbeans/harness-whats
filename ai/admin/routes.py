from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from admin.auth import authenticate_admin, create_access_token, create_refresh_token, ensure_seed_admin
from admin.deps import get_current_admin
from harness_platform.db import get_db
from harness_platform.models import AdminUser
from harness_platform.schemas import (
    AssignPlanRequest,
    LoginRequest,
    LlmModelCreate,
    LlmModelUpdate,
    LlmProviderCreate,
    LlmProviderUpdate,
    PlanCreate,
    PlanUpdate,
    PromptUpdate,
    TenantCreate,
    TenantModelsUpdate,
    TenantResponse,
    TenantUpdate,
    TenantUserCreate,
    TokenResponse,
)
from harness_platform.plan_service import (
    assign_plan,
    create_plan,
    get_tenant_subscription,
    list_plans,
    plan_to_dict,
    update_plan,
)
from harness_platform.usage_service import (
    check_tenant_limits,
    tenant_usage_month,
    usage_by_model,
    usage_daily,
    usage_summary_by_tenant,
)
from harness_platform.audit_service import list_audit_events, log_audit
from harness_platform.knowledge_service import (
    delete_knowledge_file,
    list_knowledge_files,
    save_knowledge_file,
)
from harness_platform.llm_service import (
    create_model,
    create_provider,
    get_tenant_allowed_models,
    list_models,
    list_providers,
    provider_api_key_preview,
    set_tenant_models,
    update_model,
    update_provider,
)
from harness_platform.tenant_service import (
    PROMPT_NAMES,
    create_tenant,
    delete_tenant,
    get_tenant_db,
    list_tenants_db,
    set_tenant_active,
    tenant_to_config,
    tenant_to_response,
    update_prompt,
    update_tenant,
)
from harness_platform.portal_service import (
    approve_model_change_request,
    create_tenant_user,
    list_model_change_requests,
    list_tenant_users,
    reject_model_change_request,
)
from knowledge import sync_tenant_index
from tenants.registry import reload_tenants

router = APIRouter(prefix="/admin/api", tags=["admin"])


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    ensure_seed_admin(db)
    user = authenticate_admin(db, body.email, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")
    return TokenResponse(
        access_token=create_access_token(user.email, user.role),
        refresh_token=create_refresh_token(user.email),
    )


@router.get("/auth/me")
def me(admin: AdminUser = Depends(get_current_admin)):
    return {"email": admin.email, "role": admin.role}


@router.get("/tenants", response_model=list[TenantResponse])
def list_tenants_endpoint(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    tenants = list_tenants_db(db)
    return [tenant_to_response(t) for t in tenants]


@router.post("/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_tenant_endpoint(
    body: TenantCreate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    try:
        tenant = create_tenant(db, body)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if body.portal_user:
        try:
            create_tenant_user(
                db,
                tenant_id=tenant.id,
                email=body.portal_user.email,
                password=body.portal_user.password,
                name=body.portal_user.name or body.portal_user.email,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
    log_audit(db, admin_email=admin.email, action="tenant.create", tenant_id=tenant.id)
    reload_tenants()
    return tenant_to_response(tenant)


@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
def get_tenant_endpoint(
    tenant_id: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    tenant = get_tenant_db(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return tenant_to_response(tenant)


@router.put("/tenants/{tenant_id}", response_model=TenantResponse)
def update_tenant_endpoint(
    tenant_id: str,
    body: TenantUpdate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    try:
        tenant = update_tenant(db, tenant_id, body)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    log_audit(db, admin_email=admin.email, action="tenant.update", tenant_id=tenant_id)
    reload_tenants()
    return tenant_to_response(tenant)


@router.patch("/tenants/{tenant_id}/active", response_model=TenantResponse)
def toggle_tenant_active(
    tenant_id: str,
    active: bool,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    try:
        tenant = set_tenant_active(db, tenant_id, active)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    log_audit(
        db,
        admin_email=admin.email,
        action="tenant.activate" if active else "tenant.deactivate",
        tenant_id=tenant_id,
    )
    reload_tenants()
    return tenant_to_response(tenant)


@router.delete("/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant_endpoint(
    tenant_id: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    try:
        delete_tenant(db, tenant_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    reload_tenants()


@router.get("/tenants/{tenant_id}/prompts")
def get_prompts(
    tenant_id: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    tenant = get_tenant_db(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return tenant_to_response(tenant)["prompts"]


@router.put("/tenants/{tenant_id}/prompts/{name}")
def put_prompt(
    tenant_id: str,
    name: str,
    body: PromptUpdate,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    if name not in PROMPT_NAMES:
        raise HTTPException(status_code=400, detail=f"Prompt inválido. Use: {PROMPT_NAMES}")
    try:
        update_prompt(db, tenant_id, name, body.content)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    reload_tenants()
    return {"ok": True, "name": name}


# --- LLM Registry ---


@router.get("/llm/providers")
def llm_providers(db: Session = Depends(get_db), _: AdminUser = Depends(get_current_admin)):
    providers = list_providers(db)
    return [
        {
            "id": p.id,
            "name": p.name,
            "provider_type": p.provider_type,
            "active": p.active,
            "api_key_preview": provider_api_key_preview(p),
        }
        for p in providers
    ]


@router.post("/llm/providers", status_code=status.HTTP_201_CREATED)
def llm_create_provider(
    body: LlmProviderCreate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    provider = create_provider(db, name=body.name, provider_type=body.provider_type, api_key=body.api_key)
    log_audit(db, admin_email=admin.email, action="llm.provider.create", detail=body.name)
    return {"id": provider.id, "name": provider.name}


@router.put("/llm/providers/{provider_id}")
def llm_update_provider(
    provider_id: int,
    body: LlmProviderUpdate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    try:
        provider = update_provider(
            db,
            provider_id,
            name=body.name,
            api_key=body.api_key,
            active=body.active,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    log_audit(db, admin_email=admin.email, action="llm.provider.update", detail=str(provider_id))
    return {"id": provider.id, "name": provider.name, "active": provider.active}


@router.get("/llm/models")
def llm_models(
    provider_id: int | None = None,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    models = list_models(db, provider_id)
    return [
        {
            "id": m.id,
            "provider_id": m.provider_id,
            "model_id": m.model_id,
            "display_name": m.display_name,
            "cost_per_1m_input": m.cost_per_1m_input,
            "cost_per_1m_output": m.cost_per_1m_output,
        }
        for m in models
    ]


@router.post("/llm/models", status_code=status.HTTP_201_CREATED)
def llm_create_model(
    body: LlmModelCreate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    model = create_model(
        db,
        provider_id=body.provider_id,
        model_id=body.model_id,
        display_name=body.display_name,
        cost_per_1m_input=body.cost_per_1m_input,
        cost_per_1m_output=body.cost_per_1m_output,
        temperature_default=body.temperature_default,
    )
    log_audit(db, admin_email=admin.email, action="llm.model.create", detail=body.model_id)
    return {"id": model.id, "model_id": model.model_id}


@router.put("/llm/models/{model_id}")
def llm_update_model(
    model_id: int,
    body: LlmModelUpdate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    try:
        model = update_model(
            db,
            model_id,
            provider_id=body.provider_id,
            display_name=body.display_name,
            model_ref=body.model_id,
            cost_per_1m_input=body.cost_per_1m_input,
            cost_per_1m_output=body.cost_per_1m_output,
            temperature_default=body.temperature_default,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    log_audit(db, admin_email=admin.email, action="llm.model.update", detail=str(model_id))
    return {"id": model.id, "model_id": model.model_id, "display_name": model.display_name}


@router.get("/tenants/{tenant_id}/models")
def tenant_models(
    tenant_id: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    return get_tenant_allowed_models(db, tenant_id)


@router.put("/tenants/{tenant_id}/models")
def tenant_models_update(
    tenant_id: str,
    body: TenantModelsUpdate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    set_tenant_models(db, tenant_id, body.model_ids, body.default_model_id)
    log_audit(db, admin_email=admin.email, action="tenant.models.update", tenant_id=tenant_id)
    reload_tenants()
    return {"ok": True}


# --- Knowledge ---


@router.get("/tenants/{tenant_id}/knowledge")
def knowledge_list(
    tenant_id: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    tenant = get_tenant_db(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    config = tenant_to_config(tenant)
    return {"files": list_knowledge_files(config)}


@router.post("/tenants/{tenant_id}/knowledge")
async def knowledge_upload(
    tenant_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    tenant = get_tenant_db(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    config = tenant_to_config(tenant)
    content = await file.read()
    try:
        name = save_knowledge_file(config, file.filename or "upload.md", content)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    log_audit(db, admin_email=admin.email, action="knowledge.upload", tenant_id=tenant_id, detail=name)
    return {"ok": True, "name": name}


@router.delete("/tenants/{tenant_id}/knowledge/{filename}")
def knowledge_delete(
    tenant_id: str,
    filename: str,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    tenant = get_tenant_db(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    config = tenant_to_config(tenant)
    try:
        delete_knowledge_file(config, filename)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    log_audit(db, admin_email=admin.email, action="knowledge.delete", tenant_id=tenant_id, detail=filename)
    return {"ok": True}


@router.post("/tenants/{tenant_id}/knowledge/reindex")
def knowledge_reindex(
    tenant_id: str,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    tenant = get_tenant_db(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    config = tenant_to_config(tenant)
    stats = sync_tenant_index(config)
    log_audit(db, admin_email=admin.email, action="knowledge.reindex", tenant_id=tenant_id)
    return stats


# --- Audit & Usage ---


@router.get("/audit")
def audit_list(
    limit: int = 50,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    events = list_audit_events(db, limit=limit)
    return [
        {
            "id": e.id,
            "admin_email": e.admin_email,
            "action": e.action,
            "tenant_id": e.tenant_id,
            "detail": e.detail,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]


@router.get("/usage/summary")
def usage_summary(db: Session = Depends(get_db), _: AdminUser = Depends(get_current_admin)):
    return usage_summary_by_tenant(db)


@router.get("/usage/daily")
def usage_daily_endpoint(
    tenant_id: str | None = None,
    days: int = 30,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    return usage_daily(db, tenant_id=tenant_id, days=days)


@router.get("/usage/by-model")
def usage_by_model_endpoint(
    tenant_id: str | None = None,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    return usage_by_model(db, tenant_id=tenant_id)


@router.get("/tenants/{tenant_id}/usage")
def tenant_usage_endpoint(
    tenant_id: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    return {
        "usage": tenant_usage_month(db, tenant_id),
        "limits": check_tenant_limits(db, tenant_id),
    }


# --- Plans ---


@router.get("/plans")
def plans_list(db: Session = Depends(get_db), _: AdminUser = Depends(get_current_admin)):
    return [plan_to_dict(p) for p in list_plans(db)]


@router.post("/plans", status_code=status.HTTP_201_CREATED)
def plans_create(
    body: PlanCreate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    plan = create_plan(db, slug=body.slug, name=body.name, description=body.description, limits=body.limits)
    log_audit(db, admin_email=admin.email, action="plan.create", detail=body.slug)
    return plan_to_dict(plan)


@router.put("/plans/{plan_id}")
def plans_update(
    plan_id: int,
    body: PlanUpdate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    try:
        plan = update_plan(
            db,
            plan_id,
            name=body.name,
            description=body.description,
            limits=body.limits,
            active=body.active,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    log_audit(db, admin_email=admin.email, action="plan.update", detail=str(plan_id))
    return plan_to_dict(plan)


@router.put("/tenants/{tenant_id}/plan")
def tenant_assign_plan(
    tenant_id: str,
    body: AssignPlanRequest,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    if not get_tenant_db(db, tenant_id):
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    try:
        sub = assign_plan(db, tenant_id, body.plan_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    log_audit(db, admin_email=admin.email, action="tenant.plan.assign", tenant_id=tenant_id, detail=str(body.plan_id))
    return {"ok": True, "plan_id": sub.plan_id}


@router.get("/tenants/{tenant_id}/plan")
def tenant_plan_get(
    tenant_id: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    sub = get_tenant_subscription(db, tenant_id)
    if not sub:
        return {"plan": None, "limits": check_tenant_limits(db, tenant_id)}
    return {
        "plan": plan_to_dict(sub.plan),
        "limits": check_tenant_limits(db, tenant_id),
    }


# --- Tenant portal users ---


@router.get("/tenants/{tenant_id}/users")
def tenant_users_list(
    tenant_id: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    if not get_tenant_db(db, tenant_id):
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    users = list_tenant_users(db, tenant_id)
    return [
        {"id": u.id, "email": u.email, "name": u.name, "active": u.active, "created_at": u.created_at}
        for u in users
    ]


@router.post("/tenants/{tenant_id}/users", status_code=status.HTTP_201_CREATED)
def tenant_users_create(
    tenant_id: str,
    body: TenantUserCreate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    try:
        user = create_tenant_user(
            db,
            tenant_id=tenant_id,
            email=body.email,
            password=body.password,
            name=body.name,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    log_audit(db, admin_email=admin.email, action="tenant.user.create", tenant_id=tenant_id, detail=body.email)
    return {"id": user.id, "email": user.email, "name": user.name}


# --- Model change requests ---


@router.get("/model-requests")
def model_requests_list(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    reqs = list_model_change_requests(db, status=status)
    return [
        {
            "id": r.id,
            "tenant_id": r.tenant_id,
            "requested_by": r.requested_by,
            "requested_model_id": r.requested_model_id,
            "reason": r.reason,
            "status": r.status,
            "created_at": r.created_at,
            "reviewed_by": r.reviewed_by,
            "reviewed_at": r.reviewed_at,
        }
        for r in reqs
    ]


@router.post("/model-requests/{request_id}/approve")
def model_requests_approve(
    request_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    try:
        req = approve_model_change_request(db, request_id, admin.email)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    log_audit(
        db,
        admin_email=admin.email,
        action="model_request.approve",
        tenant_id=req.tenant_id,
        detail=str(request_id),
    )
    reload_tenants()
    return {"ok": True, "status": req.status}


@router.post("/model-requests/{request_id}/reject")
def model_requests_reject(
    request_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    try:
        req = reject_model_change_request(db, request_id, admin.email)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    log_audit(
        db,
        admin_email=admin.email,
        action="model_request.reject",
        tenant_id=req.tenant_id,
        detail=str(request_id),
    )
    return {"ok": True, "status": req.status}

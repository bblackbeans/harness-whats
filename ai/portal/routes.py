from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from admin.auth import create_refresh_token, create_tenant_access_token
from harness_platform.db import get_db
from harness_platform.knowledge_service import delete_knowledge_file, list_knowledge_files, save_knowledge_file
from harness_platform.models import TenantUser
from harness_platform.portal_service import authenticate_tenant_user
from harness_platform.schemas import LoginRequest, PromptUpdate
from harness_platform.tenant_service import (
    PROMPT_NAMES,
    get_tenant_db,
    tenant_to_config,
    tenant_to_response,
    update_prompt,
)
from harness_platform.usage_service import check_tenant_limits, tenant_usage_month
from knowledge import sync_tenant_index
from portal.deps import get_current_tenant_user
from tenants.registry import reload_tenants

router = APIRouter(prefix="/portal/api", tags=["portal"])


@router.post("/auth/login")
def portal_login(body: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_tenant_user(db, body.email, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")
    return {
        "access_token": create_tenant_access_token(user.email, user.tenant_id),
        "refresh_token": create_refresh_token(user.email),
        "token_type": "bearer",
        "tenant_id": user.tenant_id,
    }


@router.get("/me")
def portal_me(user: TenantUser = Depends(get_current_tenant_user), db: Session = Depends(get_db)):
    tenant = get_tenant_db(db, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return {
        "email": user.email,
        "name": user.name,
        "tenant": tenant_to_response(tenant),
    }


@router.get("/usage")
def portal_usage(user: TenantUser = Depends(get_current_tenant_user), db: Session = Depends(get_db)):
    return {
        "usage": tenant_usage_month(db, user.tenant_id),
        "limits": check_tenant_limits(db, user.tenant_id),
    }


@router.get("/prompts")
def portal_get_prompts(user: TenantUser = Depends(get_current_tenant_user), db: Session = Depends(get_db)):
    tenant = get_tenant_db(db, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return tenant_to_response(tenant)["prompts"]


@router.put("/prompts/{name}")
def portal_put_prompt(
    name: str,
    body: PromptUpdate,
    user: TenantUser = Depends(get_current_tenant_user),
    db: Session = Depends(get_db),
):
    if name not in PROMPT_NAMES:
        raise HTTPException(status_code=400, detail=f"Prompt inválido. Use: {PROMPT_NAMES}")
    try:
        update_prompt(db, user.tenant_id, name, body.content)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    reload_tenants()
    return {"ok": True}


@router.get("/knowledge")
def portal_knowledge_list(user: TenantUser = Depends(get_current_tenant_user), db: Session = Depends(get_db)):
    tenant = get_tenant_db(db, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    config = tenant_to_config(tenant)
    return {"files": list_knowledge_files(config)}


@router.post("/knowledge")
async def portal_knowledge_upload(
    file: UploadFile = File(...),
    user: TenantUser = Depends(get_current_tenant_user),
    db: Session = Depends(get_db),
):
    tenant = get_tenant_db(db, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    config = tenant_to_config(tenant)
    content = await file.read()
    try:
        name = save_knowledge_file(config, file.filename or "upload.md", content)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"ok": True, "name": name}


@router.delete("/knowledge/{filename}")
def portal_knowledge_delete(
    filename: str,
    user: TenantUser = Depends(get_current_tenant_user),
    db: Session = Depends(get_db),
):
    tenant = get_tenant_db(db, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    config = tenant_to_config(tenant)
    delete_knowledge_file(config, filename)
    return {"ok": True}


@router.post("/knowledge/reindex")
def portal_knowledge_reindex(user: TenantUser = Depends(get_current_tenant_user), db: Session = Depends(get_db)):
    tenant = get_tenant_db(db, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    config = tenant_to_config(tenant)
    return sync_tenant_index(config)

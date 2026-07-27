"""Rotas compartilhadas de CRM / integrações / arquivos — montadas no admin e no portal."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from harness_platform.contact_service import (
    create_custom_field,
    delete_contact,
    delete_custom_field,
    get_contact,
    list_contacts,
    list_custom_fields,
    update_contact,
    update_custom_field,
    upsert_contact,
)
from harness_platform.db import get_db
from harness_platform.integration_service import (
    create_http_tool,
    create_inbound_webhook,
    delete_http_tool,
    delete_inbound_webhook,
    list_http_tools,
    list_inbound_webhooks,
    regenerate_webhook_secret,
    update_http_tool,
    update_inbound_webhook,
)
from harness_platform.schemas import (
    ContactCreate,
    ContactUpdate,
    CustomFieldCreate,
    CustomFieldUpdate,
    HttpToolCreate,
    HttpToolUpdate,
    InboundWebhookCreate,
    InboundWebhookUpdate,
    SendableFileUpdate,
)
from harness_platform.sendable_file_service import (
    delete_sendable_file,
    list_sendable_files,
    save_sendable_file,
    update_sendable_file,
)


def _public_base(request: Request) -> str:
    env = os.getenv("PUBLIC_BASE_URL", "").strip()
    if env:
        return env.rstrip("/")
    return str(request.base_url).rstrip("/")


def build_crm_routes(
    *,
    get_tenant_id,
    prefix: str = "",
) -> APIRouter:
    """get_tenant_id: Depends callable that returns tenant_id str."""
    router = APIRouter(prefix=prefix, tags=["crm"])

    # --- Custom fields ---

    @router.get("/fields")
    def api_list_fields(tenant_id: str = Depends(get_tenant_id), db: Session = Depends(get_db)):
        return {"fields": list_custom_fields(db, tenant_id)}

    @router.post("/fields", status_code=status.HTTP_201_CREATED)
    def api_create_field(
        body: CustomFieldCreate,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            return create_custom_field(
                db,
                tenant_id,
                key=body.key,
                label=body.label,
                field_type=body.field_type,
                required=body.required,
                sort_order=body.sort_order,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.put("/fields/{field_id}")
    def api_update_field(
        field_id: int,
        body: CustomFieldUpdate,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            return update_custom_field(db, tenant_id, field_id, body.model_dump(exclude_unset=True))
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.delete("/fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
    def api_delete_field(
        field_id: int,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            delete_custom_field(db, tenant_id, field_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    # --- Contacts ---

    @router.get("/contacts")
    def api_list_contacts(
        q: str = "",
        limit: int = 100,
        offset: int = 0,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        return {"contacts": list_contacts(db, tenant_id, q=q, limit=limit, offset=offset)}

    @router.post("/contacts", status_code=status.HTTP_201_CREATED)
    def api_create_contact(
        body: ContactCreate,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            return upsert_contact(
                db,
                tenant_id,
                body.phone,
                name=body.name,
                email=body.email,
                fields=body.fields,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get("/contacts/{contact_id}")
    def api_get_contact(
        contact_id: int,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        contact = get_contact(db, tenant_id, contact_id)
        if not contact:
            raise HTTPException(status_code=404, detail="Contato não encontrado")
        return contact

    @router.put("/contacts/{contact_id}")
    def api_update_contact(
        contact_id: int,
        body: ContactUpdate,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            return update_contact(db, tenant_id, contact_id, body.model_dump(exclude_unset=True))
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
    def api_delete_contact(
        contact_id: int,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            delete_contact(db, tenant_id, contact_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    # --- Inbound webhooks ---

    @router.get("/webhooks")
    def api_list_webhooks(
        request: Request,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        return {"webhooks": list_inbound_webhooks(db, tenant_id, public_base=_public_base(request))}

    @router.post("/webhooks", status_code=status.HTTP_201_CREATED)
    def api_create_webhook(
        body: InboundWebhookCreate,
        request: Request,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            return create_inbound_webhook(
                db, tenant_id, body.model_dump(), public_base=_public_base(request)
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.put("/webhooks/{webhook_id}")
    def api_update_webhook(
        webhook_id: int,
        body: InboundWebhookUpdate,
        request: Request,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            return update_inbound_webhook(
                db,
                tenant_id,
                webhook_id,
                body.model_dump(exclude_unset=True),
                public_base=_public_base(request),
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.post("/webhooks/{webhook_id}/regenerate-secret")
    def api_regen_secret(
        webhook_id: int,
        request: Request,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            return regenerate_webhook_secret(
                db, tenant_id, webhook_id, public_base=_public_base(request)
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.delete("/webhooks/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
    def api_delete_webhook(
        webhook_id: int,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            delete_inbound_webhook(db, tenant_id, webhook_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    # --- HTTP tools ---

    @router.get("/http-tools")
    def api_list_http_tools(tenant_id: str = Depends(get_tenant_id), db: Session = Depends(get_db)):
        return {"tools": list_http_tools(db, tenant_id)}

    @router.post("/http-tools", status_code=status.HTTP_201_CREATED)
    def api_create_http_tool(
        body: HttpToolCreate,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            return create_http_tool(db, tenant_id, body.model_dump())
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.put("/http-tools/{tool_id}")
    def api_update_http_tool(
        tool_id: int,
        body: HttpToolUpdate,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            return update_http_tool(db, tenant_id, tool_id, body.model_dump(exclude_unset=True))
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.delete("/http-tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
    def api_delete_http_tool(
        tool_id: int,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            delete_http_tool(db, tenant_id, tool_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    # --- Sendable files ---

    @router.get("/files")
    def api_list_files(tenant_id: str = Depends(get_tenant_id), db: Session = Depends(get_db)):
        return {"files": list_sendable_files(db, tenant_id)}

    @router.post("/files", status_code=status.HTTP_201_CREATED)
    async def api_upload_file(
        file: UploadFile = File(...),
        description: str = Form(""),
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        content = await file.read()
        try:
            return save_sendable_file(
                db,
                tenant_id,
                original_name=file.filename or "arquivo",
                content=content,
                description=description,
                mime_type=file.content_type,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.put("/files/{file_id}")
    def api_update_file(
        file_id: int,
        body: SendableFileUpdate,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            return update_sendable_file(db, tenant_id, file_id, body.description)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
    def api_delete_file(
        file_id: int,
        tenant_id: str = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        try:
            delete_sendable_file(db, tenant_id, file_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    return router

import json
import os
import time
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from harness_platform.models import Problema, Tenant, TenantUser
from harness_platform.schemas import ProblemaFeedbackCreate, ProblemaUpdate

PROBLEMAS_FEEDBACK_ENABLED = os.getenv("PROBLEMAS_FEEDBACK_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
PROBLEMAS_RATE_LIMIT_PER_HOUR = int(os.getenv("PROBLEMAS_RATE_LIMIT_PER_HOUR", "10"))

SCREENSHOT_MAX_CHARS = 120_000
VIDEO_MAX_CHARS = 7_000_000
VIDEO_MAX_DURATION_MS = 120_000
CONTEXTO_MAX_CHARS = 65_536

VALID_STATUS = {"novo", "em_analise", "resolvido", "descartado"}

_rate_limit: dict[int, list[float]] = {}


def feedback_enabled() -> bool:
    return PROBLEMAS_FEEDBACK_ENABLED


def _check_rate_limit(usuario_id: int) -> None:
    now = time.time()
    window = 3600.0
    hits = [t for t in _rate_limit.get(usuario_id, []) if now - t < window]
    if len(hits) >= PROBLEMAS_RATE_LIMIT_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Limite de {PROBLEMAS_RATE_LIMIT_PER_HOUR} reportes por hora atingido.",
        )
    hits.append(now)
    _rate_limit[usuario_id] = hits


def _validate_screenshot(data: dict) -> None:
    raw = str(data.get("data", ""))
    if not raw.startswith("data:image/"):
        raise HTTPException(status_code=400, detail="Screenshot inválido: deve ser data URL de imagem")
    if len(raw) > SCREENSHOT_MAX_CHARS:
        raise HTTPException(status_code=400, detail="Screenshot muito grande")


def _validate_recording(data: dict) -> None:
    mime = str(data.get("mime", "")).lower()
    if mime not in {"video/webm", "video/mp4"}:
        raise HTTPException(status_code=400, detail="Gravação inválida: use video/webm ou video/mp4")
    raw = str(data.get("data", ""))
    if len(raw) > VIDEO_MAX_CHARS:
        raise HTTPException(status_code=400, detail="Gravação muito grande (máx. ~5 MB)")
    duration = int(data.get("duration_ms") or 0)
    if duration > VIDEO_MAX_DURATION_MS:
        raise HTTPException(status_code=400, detail="Gravação muito longa (máx. 120s)")


def _sanitize_contexto(contexto: dict) -> dict:
    if not contexto:
        return {}
    cleaned = dict(contexto)
    screenshot = cleaned.get("screenshot")
    if isinstance(screenshot, dict):
        _validate_screenshot(screenshot)
    recording = cleaned.get("screen_recording")
    if isinstance(recording, dict):
        _validate_recording(recording)
    # Valida tamanho do resto (sem mídia pesada duplicada na conta)
    slim = {k: v for k, v in cleaned.items() if k not in {"screenshot", "screen_recording"}}
    if len(json.dumps(slim, ensure_ascii=False)) > CONTEXTO_MAX_CHARS:
        raise HTTPException(status_code=400, detail="Contexto técnico muito grande")
    return cleaned


def create_problema_feedback(
    db: Session,
    *,
    user: TenantUser,
    body: ProblemaFeedbackCreate,
) -> Problema:
    if not feedback_enabled():
        raise HTTPException(status_code=503, detail="Reporte de problemas desabilitado")

    _check_rate_limit(user.id)

    contexto = _sanitize_contexto(body.contexto or {})
    if body.passos:
        contexto["passos"] = body.passos.strip()

    correlation_id = (body.correlation_id or "").strip() or str(uuid.uuid4())

    problema = Problema(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        usuario_id=user.id,
        titulo=body.titulo.strip(),
        descricao=body.descricao.strip(),
        passos=body.passos.strip(),
        origem="feedback",
        status="novo",
        url=str(contexto.get("url", ""))[:2048],
        correlation_id=correlation_id,
        contexto_json=contexto,
    )
    db.add(problema)
    db.commit()
    db.refresh(problema)
    return problema


def _problema_to_dict(db: Session, problema: Problema, *, include_context: bool = True) -> dict:
    tenant = db.query(Tenant).filter(Tenant.id == problema.tenant_id).first()
    usuario = None
    if problema.usuario_id:
        usuario = db.query(TenantUser).filter(TenantUser.id == problema.usuario_id).first()

    ctx = problema.contexto_json or {}
    return {
        "id": problema.id,
        "tenant_id": problema.tenant_id,
        "tenant_name": tenant.name if tenant else problema.tenant_id,
        "usuario_id": problema.usuario_id,
        "usuario_email": usuario.email if usuario else "",
        "usuario_name": usuario.name if usuario else "",
        "titulo": problema.titulo,
        "descricao": problema.descricao,
        "passos": problema.passos,
        "origem": problema.origem,
        "status": problema.status,
        "url": problema.url,
        "correlation_id": problema.correlation_id,
        "contexto_json": ctx if include_context else _contexto_summary(ctx),
        "notas_internas": problema.notas_internas,
        "criado_em": problema.criado_em.isoformat() if problema.criado_em else "",
        "atualizado_em": problema.atualizado_em.isoformat() if problema.atualizado_em else "",
        "tem_screenshot": bool(ctx.get("screenshot")),
        "tem_gravacao": bool(ctx.get("screen_recording")),
    }


def _contexto_summary(ctx: dict) -> dict:
    """Versão resumida sem data URLs gigantes (listagem)."""
    out = dict(ctx)
    if isinstance(out.get("screenshot"), dict):
        out["screenshot"] = {"mime": out["screenshot"].get("mime"), "truncated": True}
    if isinstance(out.get("screen_recording"), dict):
        out["screen_recording"] = {
            "mime": out["screen_recording"].get("mime"),
            "duration_ms": out["screen_recording"].get("duration_ms"),
            "truncated": True,
        }
    return out


def list_problemas(
    db: Session,
    *,
    tenant_id: str | None = None,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    query = db.query(Problema)
    if tenant_id:
        query = query.filter(Problema.tenant_id == tenant_id)
    if status_filter and status_filter in VALID_STATUS:
        query = query.filter(Problema.status == status_filter)

    total = query.count()
    items = (
        query.order_by(Problema.criado_em.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_problema_to_dict(db, p, include_context=False) for p in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_problema(db: Session, problema_id: str) -> dict | None:
    problema = db.query(Problema).filter(Problema.id == problema_id).first()
    if not problema:
        return None
    return _problema_to_dict(db, problema, include_context=True)


def update_problema(db: Session, problema_id: str, body: ProblemaUpdate) -> dict | None:
    problema = db.query(Problema).filter(Problema.id == problema_id).first()
    if not problema:
        return None

    if body.status is not None:
        if body.status not in VALID_STATUS:
            raise HTTPException(status_code=400, detail=f"Status inválido. Use: {sorted(VALID_STATUS)}")
        problema.status = body.status

    if body.notas_internas is not None:
        problema.notas_internas = body.notas_internas[:8000]

    problema.atualizado_em = datetime.now(UTC)
    db.commit()
    db.refresh(problema)
    return _problema_to_dict(db, problema, include_context=True)


def delete_problema(db: Session, problema_id: str) -> dict | None:
    problema = db.query(Problema).filter(Problema.id == problema_id).first()
    if not problema:
        return None
    snapshot = {
        "id": problema.id,
        "tenant_id": problema.tenant_id,
        "titulo": problema.titulo,
    }
    db.delete(problema)
    db.commit()
    return snapshot

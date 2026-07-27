import mimetypes
import os
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from harness_platform.models import TenantSendableFile

_MAX_BYTES = 15 * 1024 * 1024
_DATA_DIR = Path(os.getenv("HARNESS_DATA_DIR", "data"))


def sendable_files_dir(tenant_id: str) -> Path:
    path = _DATA_DIR / "sendable_files" / tenant_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def file_to_dict(row: TenantSendableFile) -> dict:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "filename": row.filename,
        "original_name": row.original_name,
        "description": row.description or "",
        "mime_type": row.mime_type,
        "size_bytes": row.size_bytes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def list_sendable_files(db: Session, tenant_id: str) -> list[dict]:
    rows = (
        db.query(TenantSendableFile)
        .filter(TenantSendableFile.tenant_id == tenant_id)
        .order_by(TenantSendableFile.id.desc())
        .all()
    )
    return [file_to_dict(r) for r in rows]


def save_sendable_file(
    db: Session,
    tenant_id: str,
    *,
    original_name: str,
    content: bytes,
    description: str = "",
    mime_type: str | None = None,
) -> dict:
    if len(content) > _MAX_BYTES:
        raise ValueError("Arquivo excede 15MB")
    safe_original = Path(original_name).name
    if not safe_original:
        raise ValueError("Nome de arquivo inválido")
    ext = Path(safe_original).suffix.lower()
    stored = f"{uuid.uuid4().hex}{ext}"
    dest = sendable_files_dir(tenant_id) / stored
    dest.write_bytes(content)
    guessed = mime_type or mimetypes.guess_type(safe_original)[0] or "application/octet-stream"
    row = TenantSendableFile(
        tenant_id=tenant_id,
        filename=stored,
        original_name=safe_original,
        description=(description or "").strip(),
        mime_type=guessed,
        size_bytes=len(content),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return file_to_dict(row)


def update_sendable_file(db: Session, tenant_id: str, file_id: int, description: str) -> dict:
    row = (
        db.query(TenantSendableFile)
        .filter(TenantSendableFile.tenant_id == tenant_id, TenantSendableFile.id == file_id)
        .first()
    )
    if not row:
        raise LookupError("Arquivo não encontrado")
    row.description = (description or "").strip()
    db.commit()
    db.refresh(row)
    return file_to_dict(row)


def delete_sendable_file(db: Session, tenant_id: str, file_id: int) -> None:
    row = (
        db.query(TenantSendableFile)
        .filter(TenantSendableFile.tenant_id == tenant_id, TenantSendableFile.id == file_id)
        .first()
    )
    if not row:
        raise LookupError("Arquivo não encontrado")
    path = sendable_files_dir(tenant_id) / row.filename
    if path.is_file():
        path.unlink()
    db.delete(row)
    db.commit()


def resolve_sendable_file(db: Session, tenant_id: str, ref: str) -> tuple[TenantSendableFile, Path] | None:
    """Resolve por id, filename ou original_name."""
    query = db.query(TenantSendableFile).filter(TenantSendableFile.tenant_id == tenant_id)
    row = None
    if str(ref).isdigit():
        row = query.filter(TenantSendableFile.id == int(ref)).first()
    if not row:
        row = query.filter(
            (TenantSendableFile.filename == ref) | (TenantSendableFile.original_name == ref)
        ).first()
    if not row:
        # match parcial por nome
        like = f"%{ref}%"
        row = query.filter(TenantSendableFile.original_name.ilike(like)).first()
    if not row:
        return None
    path = sendable_files_dir(tenant_id) / row.filename
    if not path.is_file():
        return None
    return row, path


def files_prompt_block(files: list[dict]) -> str:
    if not files:
        return ""
    lines = ["Arquivos disponíveis para envio (use files_to_send com o nome original):"]
    for f in files:
        desc = f.get("description") or "sem descrição"
        lines.append(f"- {f['original_name']}: {desc}")
    return "\n".join(lines)

"""Banco de imagens por cliente: upload, listagem e arquivo público."""

import os
import struct
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from harness_platform.models import TenantMedia

MAX_BYTES = 5 * 1024 * 1024  # limite da Meta para imagem de cabeçalho
_DATA_DIR = Path(os.getenv("HARNESS_DATA_DIR", "data"))

# tipo -> (extensão, mime)
_ALLOWED = {
    "jpeg": (".jpg", "image/jpeg"),
    "png": (".png", "image/png"),
    "webp": (".webp", "image/webp"),
    "gif": (".gif", "image/gif"),
}


def media_dir(tenant_id: str) -> Path:
    path = _DATA_DIR / "media" / tenant_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _detect(content: bytes) -> str | None:
    if content[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if content[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    return None


def _dimensions(kind: str, c: bytes) -> tuple[int | None, int | None]:
    try:
        if kind == "png":
            return struct.unpack(">II", c[16:24])
        if kind == "gif":
            return struct.unpack("<HH", c[6:10])
        if kind == "jpeg":
            i = 2
            while i + 9 < len(c):
                if c[i] != 0xFF:
                    i += 1
                    continue
                marker = c[i + 1]
                if marker in (0xC0, 0xC1, 0xC2):
                    h, w = struct.unpack(">HH", c[i + 5 : i + 9])
                    return w, h
                i += 2 + struct.unpack(">H", c[i + 2 : i + 4])[0]
    except Exception:
        pass
    return None, None


def media_to_dict(row: TenantMedia) -> dict:
    base = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    path = f"/media/{row.tenant_id}/{row.filename}"
    return {
        "id": row.id,
        "original_name": row.original_name,
        "filename": row.filename,
        "mime_type": row.mime_type,
        "size_bytes": row.size_bytes,
        "width": row.width,
        "height": row.height,
        "path": path,
        # None quando PUBLIC_BASE_URL não está definido: o painel monta pela própria origem.
        "url": f"{base}{path}" if base else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def list_media(db: Session, tenant_id: str) -> list[dict]:
    rows = (
        db.query(TenantMedia)
        .filter(TenantMedia.tenant_id == tenant_id)
        .order_by(TenantMedia.id.desc())
        .all()
    )
    return [media_to_dict(r) for r in rows]


def save_media(db: Session, tenant_id: str, *, original_name: str, content: bytes) -> dict:
    if not content:
        raise ValueError("Arquivo vazio")
    if len(content) > MAX_BYTES:
        raise ValueError("Imagem excede 5 MB (limite da Meta para cabeçalho)")
    kind = _detect(content)
    if not kind:
        raise ValueError("Formato não suportado. Envie JPG, PNG, WEBP ou GIF.")
    ext, mime = _ALLOWED[kind]
    width, height = _dimensions(kind, content)
    stored = f"{uuid.uuid4().hex}{ext}"
    (media_dir(tenant_id) / stored).write_bytes(content)
    row = TenantMedia(
        tenant_id=tenant_id,
        filename=stored,
        original_name=(Path(original_name).name or "imagem")[:255],
        mime_type=mime,
        size_bytes=len(content),
        width=width,
        height=height,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return media_to_dict(row)


def delete_media(db: Session, tenant_id: str, media_id: int) -> None:
    row = (
        db.query(TenantMedia)
        .filter(TenantMedia.tenant_id == tenant_id, TenantMedia.id == media_id)
        .first()
    )
    if not row:
        raise LookupError("Imagem não encontrada")
    path = media_dir(tenant_id) / row.filename
    if path.is_file():
        path.unlink()
    db.delete(row)
    db.commit()


def resolve_public_media(db: Session, tenant_id: str, filename: str) -> tuple[TenantMedia, Path] | None:
    row = (
        db.query(TenantMedia)
        .filter(TenantMedia.tenant_id == tenant_id, TenantMedia.filename == filename)
        .first()
    )
    if not row:
        return None
    path = media_dir(tenant_id) / row.filename
    return (row, path) if path.is_file() else None

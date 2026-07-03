import os
from pathlib import Path

from tenants.config import TenantConfig

_SUPPORTED = {".md", ".txt"}
_MAX_BYTES = 5 * 1024 * 1024


def knowledge_base_dir(tenant: TenantConfig) -> Path:
    path = Path(tenant.knowledge_dir())
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_knowledge_files(tenant: TenantConfig) -> list[dict]:
    base = knowledge_base_dir(tenant)
    files = []
    for path in sorted(base.rglob("*")):
        if path.is_file() and path.suffix.lower() in _SUPPORTED:
            rel = path.relative_to(base).as_posix()
            stat = path.stat()
            files.append(
                {
                    "name": rel,
                    "size": stat.st_size,
                    "updated_at": stat.st_mtime,
                }
            )
    return files


def save_knowledge_file(tenant: TenantConfig, filename: str, content: bytes) -> str:
    if len(content) > _MAX_BYTES:
        raise ValueError("Arquivo excede 5MB")

    safe_name = Path(filename).name
    if Path(safe_name).suffix.lower() not in _SUPPORTED:
        raise ValueError("Formato não suportado. Use .md ou .txt")

    dest = knowledge_base_dir(tenant) / safe_name
    dest.write_bytes(content)
    return safe_name


def delete_knowledge_file(tenant: TenantConfig, filename: str) -> None:
    base = knowledge_base_dir(tenant)
    target = (base / filename).resolve()
    if not str(target).startswith(str(base.resolve())):
        raise ValueError("Caminho inválido")
    if target.is_file():
        target.unlink()

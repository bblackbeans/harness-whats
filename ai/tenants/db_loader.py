import logging

from harness_platform.cache import get_cached, set_cached
from harness_platform.db import SessionLocal, is_db_configured
from tenants.config import TenantConfig
from tenants.loader import load_all_tenants, load_default_tenant, load_prompt

logger = logging.getLogger(__name__)


def _db_available() -> bool:
    if not is_db_configured():
        return False
    try:
        with SessionLocal() as db:
            db.connection()
        return True
    except Exception:
        logger.warning("PostgreSQL indisponível; usando filesystem", exc_info=True)
        return False


def load_all_tenants_db() -> dict[str, TenantConfig]:
    if not _db_available():
        return load_all_tenants()

    from harness_platform.tenant_service import list_tenants_db, tenant_to_config

    configs: dict[str, TenantConfig] = {}
    with SessionLocal() as db:
        for tenant in list_tenants_db(db, active_only=False):
            if not tenant.active:
                continue
            cached = get_cached(tenant.id)
            if cached:
                configs[tenant.id] = cached
                continue
            config = tenant_to_config(tenant)
            set_cached(tenant.id, config)
            configs[tenant.id] = config

    if configs:
        return configs

    return load_all_tenants()


def get_tenant_db_or_fs(tenant_id: str) -> TenantConfig:
    cached = get_cached(tenant_id)
    if cached:
        return cached

    if _db_available():
        from harness_platform.tenant_service import get_tenant_db, tenant_to_config

        with SessionLocal() as db:
            tenant = get_tenant_db(db, tenant_id)
            if tenant and tenant.active:
                config = tenant_to_config(tenant)
                set_cached(tenant_id, config)
                return config

    fs_tenants = load_all_tenants()
    if tenant_id in fs_tenants:
        return fs_tenants[tenant_id]
    return load_default_tenant()


def load_prompt_db(tenant: TenantConfig, name: str, fallback: str) -> str:
    if tenant.root_dir:
        return load_prompt(tenant, name, fallback)

    if not _db_available():
        return fallback

    from harness_platform.models import TenantPrompt

    with SessionLocal() as db:
        row = (
            db.query(TenantPrompt)
            .filter(TenantPrompt.tenant_id == tenant.id, TenantPrompt.name == name)
            .first()
        )
        if row and row.content.strip():
            return row.content.strip()
    return fallback

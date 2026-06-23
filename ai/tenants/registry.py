import os

from ingress.models import InboundEvent
from tenants.config import TenantConfig
from tenants.loader import load_all_tenants, load_default_tenant

_tenants: dict[str, TenantConfig] | None = None


def _get_tenants() -> dict[str, TenantConfig]:
    global _tenants
    if _tenants is None:
        loaded = load_all_tenants()
        default = load_default_tenant()
        loaded.setdefault(default.id, default)
        _tenants = loaded
    return _tenants


def reload_tenants() -> dict[str, TenantConfig]:
    global _tenants
    _tenants = None
    return _get_tenants()


def list_tenants() -> list[TenantConfig]:
    return list(_get_tenants().values())


def get_tenant(tenant_id: str) -> TenantConfig:
    tenants = _get_tenants()
    if tenant_id in tenants:
        return tenants[tenant_id]
    return load_default_tenant()


def resolve_tenant(event: InboundEvent) -> TenantConfig:
    forced = os.getenv("TENANT_ID", "").strip()
    if forced:
        return get_tenant(forced)

    tenants = list_tenants()
    if len(tenants) == 1:
        return tenants[0]

    inbox_id = event.inbox_id
    if inbox_id is not None:
        for tenant in tenants:
            if inbox_id in tenant.routing.chatwoot_inbox_ids:
                return tenant

    account_id = event.account_id
    for tenant in tenants:
        if account_id in tenant.routing.chatwoot_account_ids:
            return tenant

    return load_default_tenant()

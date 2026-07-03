from tenants.config import TenantConfig


def load_prompt(tenant: TenantConfig, name: str, fallback: str) -> str:
    if tenant.root_dir:
        from tenants.loader import load_prompt as load_prompt_fs

        return load_prompt_fs(tenant, name, fallback)
    from tenants.db_loader import load_prompt_db

    return load_prompt_db(tenant, name, fallback)


def get_tenant(tenant_id: str):
    from tenants.registry import get_tenant as _get

    return _get(tenant_id)


def list_tenants():
    from tenants.registry import list_tenants as _list

    return _list()


def reload_tenants():
    from tenants.registry import reload_tenants as _reload

    return _reload()


def resolve_tenant(event):
    from tenants.registry import resolve_tenant as _resolve

    return _resolve(event)


__all__ = [
    "TenantConfig",
    "get_tenant",
    "list_tenants",
    "load_prompt",
    "reload_tenants",
    "resolve_tenant",
]

#!/usr/bin/env python3
"""Migra tenant do filesystem para PostgreSQL."""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_REPO = Path(__file__).resolve().parents[1]
_AI = _REPO / "ai"
sys.path.insert(0, str(_AI))
load_dotenv(_REPO / ".env")

from harness_platform.db import SessionLocal  # noqa: E402
from harness_platform.schemas import TenantCreate, TenantSettings  # noqa: E402
from harness_platform.tenant_service import create_tenant, get_tenant_db  # noqa: E402
from tenants.loader import _parse_tenant_dir  # noqa: E402

TENANTS_DIR = Path(os.getenv("TENANTS_DIR", str(_REPO / "tenants")))


def migrate_tenant_dir(tenant_dir: Path) -> None:
    parsed = _parse_tenant_dir(tenant_dir)
    if not parsed:
        print(f"skip {tenant_dir.name}")
        return

    with SessionLocal() as db:
        if get_tenant_db(db, parsed.id):
            print(f"exists {parsed.id}")
            return

    raw_path = tenant_dir / "tenant.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))

    settings = TenantSettings.model_validate(
        {
            "routing": raw.get("routing", {}),
            "model": raw.get("model", {}),
            "context": raw.get("context", {}),
            "rag": raw.get("rag", {}),
            "handoff": raw.get("handoff", {}),
        }
    )

    prompts = {}
    prompts_dir = tenant_dir / "prompts"
    if prompts_dir.is_dir():
        for path in prompts_dir.glob("*.txt"):
            prompts[path.stem] = path.read_text(encoding="utf-8").strip()

    payload = TenantCreate(
        id=parsed.id,
        name=parsed.name,
        language=parsed.language,
        active=True,
        settings=settings,
        prompts=prompts,
    )

    with SessionLocal() as db:
        create_tenant(db, payload)
    print(f"migrated {parsed.id}")


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else None
    if target:
        migrate_tenant_dir(TENANTS_DIR / target)
        return
    for entry in sorted(TENANTS_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        migrate_tenant_dir(entry)


if __name__ == "__main__":
    main()

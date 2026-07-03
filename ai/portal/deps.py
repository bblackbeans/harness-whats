from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from admin.auth import decode_token
from harness_platform.db import get_db
from harness_platform.models import TenantUser

security = HTTPBearer(auto_error=False)


def get_current_tenant_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> TenantUser:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado")
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access" or payload.get("role") != "tenant_admin":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
        email = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        if not email or not tenant_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    except JWTError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido") from error

    user = (
        db.query(TenantUser)
        .filter(
            TenantUser.email == email,
            TenantUser.tenant_id == tenant_id,
            TenantUser.active.is_(True),
        )
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado")
    return user

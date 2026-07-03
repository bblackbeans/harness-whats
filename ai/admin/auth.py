import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from harness_platform.models import AdminUser

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, role: str, tenant_id: str | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict = {"sub": subject, "role": role, "type": "access", "exp": expire}
    if tenant_id:
        payload["tenant_id"] = tenant_id
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_tenant_access_token(email: str, tenant_id: str) -> str:
    return create_access_token(email, "tenant_admin", tenant_id=tenant_id)


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": subject, "type": "refresh", "exp": expire},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def authenticate_admin(db: Session, email: str, password: str) -> AdminUser | None:
    user = db.query(AdminUser).filter(AdminUser.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def ensure_seed_admin(db: Session) -> None:
    email = os.getenv("ADMIN_EMAIL", "admin@harness.local")
    password = os.getenv("ADMIN_PASSWORD", "admin123")
    existing = db.query(AdminUser).filter(AdminUser.email == email).first()
    if existing:
        return
    db.add(
        AdminUser(
            email=email,
            password_hash=hash_password(password),
            role="super_admin",
        )
    )
    db.commit()

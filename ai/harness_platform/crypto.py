"""Fernet encryption for API keys at rest."""

import base64
import hashlib
import os

from cryptography.fernet import Fernet


def _fernet() -> Fernet:
    raw = os.getenv("ENCRYPTION_KEY") or os.getenv("JWT_SECRET", "change-me-in-production")
    key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    return Fernet(key)


def encrypt_value(plain: str) -> str:
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    if not encrypted:
        return ""
    return _fernet().decrypt(encrypted.encode()).decode()

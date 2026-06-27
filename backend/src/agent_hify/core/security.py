from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from cryptography.fernet import Fernet

from agent_hify.core.config import get_settings

_settings = get_settings()
_fernet = Fernet(_settings.encryption_key.encode("ascii"))
_ALGORITHM = "HS256"


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(p: str, hashed: str) -> bool:
    return bcrypt.checkpw(p.encode("utf-8"), hashed.encode("ascii"))


def encrypt(plaintext: str) -> bytes:
    return _fernet.encrypt(plaintext.encode("utf-8"))


def decrypt(token: bytes) -> str:
    return _fernet.decrypt(token).decode("utf-8")


def create_access_token(*, user_id: int, role: str, workspace_id: int) -> str:
    expire = datetime.now(UTC) + timedelta(
        minutes=_settings.access_token_expire_minutes
    )
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "workspace_id": workspace_id,
        "exp": expire,
    }
    return jwt.encode(claims, _settings.secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict[str, object]:
    return jwt.decode(token, _settings.secret_key, algorithms=[_ALGORITHM])

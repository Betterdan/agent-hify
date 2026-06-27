from __future__ import annotations

from agent_hify.core.security import (
    create_access_token,
    decode_access_token,
    decrypt,
    encrypt,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    h = hash_password("s3cret")
    assert h != "s3cret"
    assert verify_password("s3cret", h) is True
    assert verify_password("wrong", h) is False


def test_credential_encrypt_roundtrip() -> None:
    token = encrypt("sk-abc-123")
    assert isinstance(token, bytes)
    assert decrypt(token) == "sk-abc-123"


def test_jwt_roundtrip() -> None:
    token = create_access_token(user_id=7, role="admin", workspace_id=1)
    claims = decode_access_token(token)
    assert claims["sub"] == "7"
    assert claims["role"] == "admin"
    assert claims["workspace_id"] == 1

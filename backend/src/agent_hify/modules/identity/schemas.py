from __future__ import annotations

from pydantic import BaseModel


class LoginIn(BaseModel):
    # Login 端点只需按用户输入查库，无需 DNS 投递校验，用 str 避免 email-validator
    # 对 .local / 非公网域名的误拒（注册端点再用 EmailStr）。
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    workspace_id: int
